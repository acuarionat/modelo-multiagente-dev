"""Una única llamada real de Calidad para HU-006 y HU-007."""

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
    "ENABLE_REMOTE_LLM": "true",
    "ENABLE_LOCAL_FALLBACK": "false",
    "LLM_PROVIDER_QUALITY": "groq",
    "REMOTE_QUALITY_BATCH_SIZE": "2",
    "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "2048",
    "REMOTE_REASONING_EFFORT": "low",
    "REMOTE_REASONING_FORMAT": "hidden",
    "REMOTE_LLM_MAX_RETRIES": "0",
    "REMOTE_INTER_CALL_DELAY_SECONDS": "60",
})

from agents.llm_invocation import obtener_ultimos_metadatos
from agents.quality_agent import analizar_calidad
from core.batch_contract import completar_resultado_calidad, indexar_resultados
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
        "issue_iid": int(item["issue_iid"]),
        "historia_id": item.get("historia_id"),
        "funciones_especificadas": len(mc01.get("funciones_especificadas", [])),
        "funciones_incluidas": len(mc01.get("funciones_incluidas", [])),
        "funciones_faltantes": len(mc01.get("funciones_faltantes", [])),
        "A": (mc01.get("variables") or {}).get("numerador"),
        "B": (mc01.get("variables") or {}).get("denominador"),
        "mc01": mc01.get("valor"),
        "funciones_evaluables": len(mc02.get("funciones_evaluables", [])),
        "funciones_alineadas": len(mc02.get("funciones_alineadas", [])),
        "funciones_no_alineadas": len(mc02.get("funciones_no_alineadas", [])),
        "mc02": mc02.get("valor"),
        "indice_calidad": indicator.get("valor"),
        "meta": indicator.get("meta"),
        "estado": indicator.get("estado"),
        "recomendaciones": len(item.get("recomendaciones", [])),
    }


def realistic_central_fixture():
    central = central_fixture(order=(6, 7))
    story6 = next(item for item in central["resultados"] if int(item["issue_iid"]) == 6)
    story6["requerimientos"] = [{
        "temp_id": f"RF-HU006-{index:02d}", "nombre": name, "tipo": "RF",
        "descripcion_formal": f"El sistema deberá {name[:1].lower() + name[1:]}",
        "origen": name, "procedencia": "explícita — criterio de aceptación",
        "justificacion": "Evidencia ficticia controlada.", "prioridad": "Alta",
    } for index, name in enumerate((
        "Consultar horarios disponibles", "Mostrar únicamente horarios disponibles",
        "Mostrar nombre y especialidad del médico",
        "Actualizar disponibilidad después de programar la cita",
    ), 1)]
    return central


def main():
    execution_id = f"quality-first-batch-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    summary_dir = Path(tempfile.gettempdir())
    issues = [deepcopy(ISSUES[iid]) for iid in (6, 7)]
    expected = [6, 7]
    reiniciar_contadores()
    reiniciar_pacing_remoto()
    started = time.monotonic()
    prepared_text = preparar_entrada_calidad(
        json.dumps(realistic_central_fixture(), ensure_ascii=False), issues,
    )
    prepared = json.loads(prepared_text)
    prepared_by_iid = indexar_resultados(prepared)
    summary_path = persist_sanitized_execution_summary({
        "execution_id": execution_id, "estado_tecnico": "preparado",
        "expected_issue_ids": expected, "seguridad_ejecutada": False,
        "ollama_ejecutado": False, "evaluador_ejecutado": False,
        "gitlab_usado": False,
    }, summary_dir)
    parsed = None
    failure = None
    try:
        parsed = _ejecutar_sublotes_remotos(
            prepared_text, "Calidad", 2,
            lambda raw, sub_batch: analizar_calidad(raw, sub_batch=sub_batch),
        )
        for item in parsed["resultados"]:
            iid = int(item["issue_iid"])
            context = deepcopy(ISSUES[iid])
            context["requerimientos_preparados"] = deepcopy(
                prepared_by_iid[iid].get("requerimientos", [])
            )
            completar_resultado_calidad(item, context)
    except Exception as exc:
        failure = exc
    audit = obtener_contadores()
    metadata = obtener_ultimos_metadatos("Quality")
    events = audit.get("eventos_sublotes_remotos", [])
    final_event = next((event for event in reversed(events) if event.get("event") == "remote_sub_batch_end"), {})
    metrics = [summarize(item) for item in parsed.get("resultados", [])] if parsed and failure is None else []
    summary = {
        "execution_id": execution_id,
        "estado_tecnico": "completo" if failure is None else "incompleto",
        "duracion_total_segundos": round(time.monotonic() - started, 4),
        "duracion_remota_segundos": next((event.get("elapsed_seconds") for event in events if event.get("event") == "remote_sub_batch_call_end"), None),
        "provider": metadata.get("provider", "groq"),
        "model": metadata.get("model", os.getenv("GROQ_MODEL_QUALITY")),
        "http_status": getattr(failure, "http_status", None) if failure else 200,
        "max_completion_tokens": 2048,
        "finish_reason": metadata.get("finish_reason"),
        "response_chars": metadata.get("response_chars"),
        "json_valid": final_event.get("json_valid"),
        "json_recovered": final_event.get("json_recovered", False),
        "expected_issue_ids": expected,
        "received_issue_ids": final_event.get("received_issue_ids", final_event.get("received", [])),
        "identity_validation": final_event.get("identity_validation"),
        "contract_validation": final_event.get("contract_validation"),
        "contract_stage": final_event.get("contract_stage"),
        "semantic_validation": final_event.get("semantic_validation"),
        "semantic_by_issue": final_event.get("semantic_by_issue", []),
        "failed_validator": final_event.get("failed_validator"),
        "missing_fields": final_event.get("missing_fields", []),
        "invalid_types": final_event.get("invalid_types", []),
        "alias_fields_detected": final_event.get("alias_fields_detected", []),
        "premature_fields": final_event.get("premature_fields", []),
        "empty_but_valid_fields": final_event.get("empty_but_valid_fields", []),
        "remote_rate_pacing_applied": False,
        "llamadas_remotas": audit.get("llamadas_remotas", 0),
        "reintentos": audit.get("reintentos", 0),
        "reparaciones": audit.get("motivos_reparacion", {}),
        "fallbacks": audit.get("fallbacks_locales", 0),
        "eventos_sublote": events,
        "preparacion_por_historia": audit.get("quality_input_prepared", {}).get("by_issue", []),
        "evidencia_equivalente": [{
            "issue_iid": iid,
            "canonical_groups": len(item.get("evidencias_funciones_equivalentes", [])),
            "merged_groups": sum(
                len(group.get("source_indices", [])) > 1
                for group in item.get("evidencias_funciones_equivalentes", [])
            ),
            "merged_source_count": sum(
                len(group.get("source_indices", []))
                for group in item.get("evidencias_funciones_equivalentes", [])
                if len(group.get("source_indices", [])) > 1
            ),
            "order_preserved": all(
                group.get("canonical_index") == index
                for index, group in enumerate(item.get("evidencias_funciones_equivalentes", []))
            ),
        } for iid, item in sorted(prepared_by_iid.items())],
        "metricas_por_historia": metrics,
        "sublote_1_ejecutado": True,
        "sublote_2_ejecutado": False,
        "sublote_3_ejecutado": False,
        "seguridad_ejecutada": False,
        "ollama_ejecutado": False,
        "evaluador_ejecutado": False,
        "gitlab_usado": False,
        "error_category": getattr(failure, "category", type(failure).__name__) if failure else None,
    }
    path = persist_sanitized_execution_summary(summary, summary_dir)
    if path != summary_path:
        raise RuntimeError("UNEXPECTED_SUMMARY_PATH")
    print(json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=True))
    if failure:
        raise failure
    if audit.get("llamadas_remotas") != 1:
        raise RuntimeError("UNEXPECTED_REMOTE_CALL_COUNT")


if __name__ == "__main__":
    main()
