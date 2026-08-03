"""Una llamada real y aislada de Calidad exclusivamente para HU-010."""

import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
os.environ.update({
    "ENABLE_REMOTE_LLM": "true", "ENABLE_LOCAL_FALLBACK": "false",
    "LLM_PROVIDER_QUALITY": "groq", "GROQ_MODEL_QUALITY": "openai/gpt-oss-120b",
    "REMOTE_QUALITY_BATCH_SIZE": "2", "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "2048",
    "REMOTE_REASONING_EFFORT": "low", "REMOTE_REASONING_FORMAT": "hidden",
    "REMOTE_LLM_MAX_RETRIES": "0", "REMOTE_INTER_CALL_DELAY_SECONDS": "60",
})

from agents.llm_invocation import obtener_ultimos_metadatos
from agents.quality_agent import analizar_calidad
from core.batch_contract import (
    completar_resultado_calidad, es_funcion_principal_evaluable, indexar_resultados,
    normalizar_tipo_requerimiento,
)
from core.execution_summary import persist_sanitized_execution_summary
from core.graph import _ejecutar_sublotes_remotos, preparar_entrada_calidad
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import reiniciar_pacing_remoto
from tests.test_quality_input_preparation import ISSUES, central_fixture


def summarize(item):
    mc01 = item["metricas"]["cobertura_funcional"]
    mc02 = item["metricas"]["adecuacion_funcional"]
    indicator = item.get("indicador", {})
    return {
        "issue_iid": int(item["issue_iid"]), "historia_id": item.get("historia_id"),
        "funciones_especificadas": mc01.get("funciones_especificadas", []),
        "funciones_incluidas": mc01.get("funciones_incluidas", []),
        "funciones_faltantes": mc01.get("funciones_faltantes", []),
        "A": (mc01.get("variables") or {}).get("numerador"),
        "B": (mc01.get("variables") or {}).get("denominador"), "mc01": mc01.get("valor"),
        "funciones_evaluables": mc02.get("funciones_evaluables", []),
        "funciones_alineadas": mc02.get("funciones_alineadas", []),
        "funciones_no_alineadas": mc02.get("funciones_no_alineadas", []),
        "mc02": mc02.get("valor"), "indice_calidad": indicator.get("valor"),
        "meta": indicator.get("meta"), "estado": indicator.get("estado"),
        "recomendaciones": item.get("recomendaciones", []),
    }


def main():
    execution_id = f"quality-010-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    summary_dir = Path(tempfile.gettempdir())
    summary_path = summary_dir / f"{execution_id}-summary.json"
    expected = [10]
    issues = [deepcopy(ISSUES[10])]
    reiniciar_contadores()
    reiniciar_pacing_remoto()
    started = time.monotonic()
    prepared_text = preparar_entrada_calidad(
        json.dumps(central_fixture(order=(10,)), ensure_ascii=False), issues,
    )
    prepared = json.loads(prepared_text)
    prepared_by_iid = indexar_resultados(prepared)
    prepared_result = prepared_by_iid[10]
    requirements = [item for item in prepared_result.get("requerimientos", []) if isinstance(item, dict)]
    input_summary = {
        "rf_documentales": sum(normalizar_tipo_requerimiento(item) == "RF" for item in requirements),
        "rnf_documentales": sum(normalizar_tipo_requerimiento(item) == "RNF" for item in requirements),
        "universo_mc01": sum(es_funcion_principal_evaluable(item, ISSUES[10].get("funcionalidad")) for item in requirements),
        "universo_mc02": sum(es_funcion_principal_evaluable(item, ISSUES[10].get("funcionalidad")) for item in requirements),
        "regla_24_horas_presente": any("24 horas" in json.dumps(item, ensure_ascii=False) for item in requirements),
        "regla_24_horas_tipo": next((normalizar_tipo_requerimiento(item) for item in requirements if "24 horas" in json.dumps(item, ensure_ascii=False)), None),
    }
    parsed = None
    failure = None
    try:
        parsed = _ejecutar_sublotes_remotos(
            prepared_text, "Calidad", 2,
            lambda raw, sub_batch: analizar_calidad(raw, sub_batch=sub_batch),
        )
        for item in parsed["resultados"]:
            context = deepcopy(ISSUES[10])
            context["requerimientos_preparados"] = deepcopy(requirements)
            completar_resultado_calidad(item, context)
    except Exception as exc:
        failure = exc

    audit = obtener_contadores()
    metadata = obtener_ultimos_metadatos("Quality")
    events = audit.get("eventos_sublotes_remotos", [])
    final_event = next((event for event in reversed(events) if event.get("event") == "remote_sub_batch_end"), {})
    call_event = next((event for event in events if event.get("event") == "remote_sub_batch_call_end"), {})
    metrics = [summarize(item) for item in parsed.get("resultados", [])] if parsed and failure is None else []
    summary = {
        "execution_id": execution_id, "resumen_json_temporal": str(summary_path),
        "estado_tecnico": "completo" if failure is None else "incompleto",
        "duracion_total_segundos": round(time.monotonic() - started, 4),
        "duracion_remota_segundos": call_event.get("elapsed_seconds"),
        "provider": metadata.get("provider", "groq"),
        "model": metadata.get("model", os.getenv("GROQ_MODEL_QUALITY")),
        "http_status": getattr(failure, "http_status", None) if failure else 200,
        "finish_reason": metadata.get("finish_reason"),
        "json_valid": final_event.get("json_valid"),
        "json_recovered": final_event.get("json_recovered", False),
        "expected_issue_ids": expected,
        "received_issue_ids": final_event.get("received_issue_ids", final_event.get("received", [])),
        "identity_validation": final_event.get("identity_validation"),
        "contract_validation": final_event.get("contract_validation"),
        "contract_stage": final_event.get("contract_stage"),
        "semantic_validation": final_event.get("semantic_validation"),
        "semantic_error_category": final_event.get("semantic_error_category"),
        "failed_validator": final_event.get("failed_validator"),
        "semantic_by_issue": final_event.get("semantic_by_issue", []),
        "entrada_preparada": input_summary, "metricas_por_historia": metrics,
        "llamadas_remotas": audit.get("llamadas_remotas", 0),
        "reintentos": audit.get("reintentos", 0),
        "reparaciones": audit.get("motivos_reparacion", {}),
        "fallbacks": audit.get("fallbacks_locales", 0),
        "remote_rate_pacing_applied": any(event.get("event") == "remote_rate_pacing" for event in events),
        "seguridad_ejecutada": False, "ollama_ejecutado": False,
        "evaluador_ejecutado": False, "gitlab_usado": False,
        "error_category": getattr(failure, "category", type(failure).__name__) if failure else None,
    }
    persisted = persist_sanitized_execution_summary(summary, summary_dir)
    print(json.dumps(json.loads(persisted.read_text(encoding="utf-8")), ensure_ascii=True))
    if failure:
        raise failure
    if audit.get("llamadas_remotas") != 1:
        raise RuntimeError("UNEXPECTED_REMOTE_CALL_COUNT")


if __name__ == "__main__":
    main()
