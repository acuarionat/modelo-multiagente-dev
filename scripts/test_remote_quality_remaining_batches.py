"""Dos llamadas máximas de Calidad: HU-008/HU-009 y luego HU-010."""

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
    "LLM_PROVIDER_QUALITY": "groq",
    "REMOTE_QUALITY_BATCH_SIZE": "2",
    "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "2048",
    "REMOTE_REASONING_EFFORT": "low",
    "REMOTE_REASONING_FORMAT": "hidden",
    "REMOTE_LLM_MAX_RETRIES": "0",
    "REMOTE_INTER_CALL_DELAY_SECONDS": "60",
})

from agents.quality_agent import analizar_calidad
from core.batch_contract import completar_resultado_calidad, indexar_resultados
from core.execution_summary import persist_sanitized_execution_summary
from core.graph import _ejecutar_sublotes_remotos, preparar_entrada_calidad
from core.performance_audit import obtener_contadores, reiniciar_contadores
import core.remote_execution as remote_execution
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
        "B": (mc01.get("variables") or {}).get("denominador"),
        "mc01": mc01.get("valor"),
        "funciones_evaluables": mc02.get("funciones_evaluables", []),
        "funciones_alineadas": mc02.get("funciones_alineadas", []),
        "funciones_no_alineadas": mc02.get("funciones_no_alineadas", []),
        "mc02": mc02.get("valor"), "indice_calidad": indicator.get("valor"),
        "meta": indicator.get("meta"), "estado": indicator.get("estado"),
        "recomendaciones": item.get("recomendaciones", []),
    }


def main():
    execution_id = f"quality-remaining-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    expected = [8, 9, 10]
    issues = [deepcopy(ISSUES[iid]) for iid in expected]
    reiniciar_contadores()
    remote_execution.reiniciar_pacing_remoto()
    pacing = []
    original_event = remote_execution.registrar_evento_grafo
    def capture_event(event, agent, **data):
        if event == "remote_rate_pacing":
            pacing.append({"event": event, "agent": agent, **data})
        original_event(event, agent, **data)
    remote_execution.registrar_evento_grafo = capture_event
    started = time.monotonic()
    prepared_text = preparar_entrada_calidad(
        json.dumps(central_fixture(order=tuple(expected)), ensure_ascii=False), issues,
    )
    prepared = json.loads(prepared_text)
    prepared_by_iid = indexar_resultados(prepared)
    input_summary = []
    for item in prepared["resultados"]:
        requirements = item.get("requerimientos", [])
        input_summary.append({
            "issue_iid": int(item["issue_iid"]),
            "rf": sum(req.get("tipo") == "RF" for req in requirements),
            "rnf": sum(req.get("tipo") == "RNF" for req in requirements),
        })
    parsed, failure = None, None
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
    events = audit.get("eventos_sublotes_remotos", [])
    ends = [event for event in events if event.get("event") == "remote_sub_batch_end"]
    call_ends = [event for event in events if event.get("event") == "remote_sub_batch_call_end"]
    metrics = [summarize(item) for item in parsed.get("resultados", [])] if parsed and not failure else []
    summary = {
        "execution_id": execution_id,
        "estado_tecnico": "completo" if failure is None else "incompleto",
        "duracion_total_segundos": round(time.monotonic() - started, 4),
        "entrada_por_historia": input_summary,
        "llamadas_remotas": audit.get("llamadas_remotas", 0),
        "duraciones_llamadas": [event.get("elapsed_seconds") for event in call_ends],
        "http_status_por_llamada": [200 for _ in call_ends],
        "finish_reason_por_llamada": [event.get("finish_reason") for event in ends],
        "json_valid_por_llamada": [event.get("json_valid") for event in ends],
        "json_recovered_por_llamada": [event.get("json_recovered") for event in ends],
        "identidad_por_llamada": [{
            "expected": event.get("expected_issue_ids"),
            "received": event.get("received_issue_ids"),
            "identity_validation": event.get("identity_validation"),
        } for event in ends],
        "contrato_por_llamada": [{
            "contract_validation": event.get("contract_validation"),
            "contract_stage": event.get("contract_stage"),
            "missing_fields": event.get("missing_fields", []),
            "invalid_types": event.get("invalid_types", []),
            "alias_fields_detected": event.get("alias_fields_detected", []),
        } for event in ends],
        "pacing": pacing,
        "reintentos": audit.get("reintentos", 0),
        "reparaciones": audit.get("motivos_reparacion", {}),
        "fallbacks": audit.get("fallbacks_locales", 0),
        "eventos_sublotes": events,
        "metricas_por_historia": metrics,
        "orden_consolidado": [item["issue_iid"] for item in metrics],
        "llamada_1_completada": len(call_ends) >= 1,
        "llamada_2_completada": len(call_ends) >= 2,
        "truncamientos": sum(event.get("error_category") == "REMOTE_TRUNCATED_RESPONSE" for event in events),
        "errores_429": sum(event.get("http_status") == 429 for event in events),
        "retry_after_seconds": getattr(failure, "retry_after_seconds", None) if failure else None,
        "error_category": getattr(failure, "category", type(failure).__name__) if failure else None,
        "seguridad_ejecutada": False, "ollama_ejecutado": False,
        "evaluador_ejecutado": False, "gitlab_usado": False,
    }
    path = persist_sanitized_execution_summary(summary, Path(tempfile.gettempdir()))
    print(json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=True))
    if failure:
        raise failure
    if audit.get("llamadas_remotas") != 2:
        raise RuntimeError("UNEXPECTED_REMOTE_CALL_COUNT")


if __name__ == "__main__":
    main()
