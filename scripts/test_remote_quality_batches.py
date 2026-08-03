"""Prueba real aislada de Calidad con cinco fixtures y sublotes 2+2+1."""

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

# Configuración autorizada únicamente para este proceso diagnóstico.
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

from agents.quality_agent import analizar_calidad
from core.batch_contract import (
    calcular_metricas_agente,
    conciliar_ids_issues,
    indexar_resultados,
    validar_contenido_agente,
    validar_respuesta_lote,
)
from core.execution_summary import persist_sanitized_execution_summary
from core.graph import _ejecutar_sublotes_remotos, preparar_entrada_calidad
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import reiniciar_pacing_remoto
import core.remote_execution as remote_execution
from tests.test_quality_input_preparation import ISSUES, central_fixture


def metric_summary(item):
    metrics = item.get("metricas", {})
    mc01 = metrics.get("cobertura_funcional", {})
    mc02 = metrics.get("adecuacion_funcional", {})
    indicator = item.get("indicador_calidad", {})
    return {
        "issue_iid": int(item["issue_iid"]),
        "historia_id": item.get("historia_id"),
        "rf": len(mc01.get("funciones_especificadas") or []),
        "rnf_excluidos": item.get("_rnf_excluidos", 0),
        "universo_mc01": len(mc01.get("funciones_especificadas") or []),
        "funciones_incluidas": mc01.get("funciones_incluidas", []),
        "funciones_faltantes": mc01.get("funciones_faltantes", []),
        "A": mc01.get("A"),
        "B": mc01.get("B"),
        "mc01": mc01.get("valor"),
        "universo_mc02": len(mc02.get("funciones_evaluables") or []),
        "funciones_alineadas": mc02.get("funciones_alineadas", []),
        "funciones_no_alineadas": mc02.get("funciones_no_alineadas", []),
        "mc02": mc02.get("valor"),
        "indice_calidad": indicator.get("valor"),
        "meta": indicator.get("meta"),
        "estado": indicator.get("estado"),
        "recomendaciones": item.get("recomendaciones", []),
    }


def main():
    execution_id = f"quality-isolated-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    summary_path = Path(tempfile.gettempdir()) / f"{execution_id}-summary.json"
    issues = [deepcopy(ISSUES[iid]) for iid in (6, 7, 8, 9, 10)]
    expected = [6, 7, 8, 9, 10]
    reiniciar_contadores()
    reiniciar_pacing_remoto()
    pacing_events = []
    original_graph_event = remote_execution.registrar_evento_grafo
    def capture_graph_event(event, agent, **data):
        if event == "remote_rate_pacing":
            pacing_events.append({"event": event, "agent": agent, **data})
        original_graph_event(event, agent, **data)
    remote_execution.registrar_evento_grafo = capture_graph_event
    started = time.monotonic()
    prepared_text = preparar_entrada_calidad(
        json.dumps(central_fixture(), ensure_ascii=False), issues,
    )
    prepared = json.loads(prepared_text)
    prepared_index = indexar_resultados(prepared)
    input_by_issue = []
    for item in prepared["resultados"]:
        requirements = item.get("requerimientos", [])
        input_by_issue.append({
            "issue_iid": int(item["issue_iid"]),
            "historia_id": item.get("historia_id"),
            "rf": sum(req.get("tipo") == "RF" for req in requirements),
            "rnf": sum(req.get("tipo") == "RNF" for req in requirements),
        })
    failure = None
    parsed = None
    try:
        parsed = _ejecutar_sublotes_remotos(
            prepared_text, "Calidad", 2,
            lambda payload, sub_batch: analizar_calidad(payload, sub_batch=sub_batch),
        )
        for note in conciliar_ids_issues(parsed, expected, "Calidad"):
            pass
        context = {}
        for issue in issues:
            iid = int(issue["id"])
            value = deepcopy(issue)
            value["requerimientos_preparados"] = deepcopy(
                prepared_index.get(iid, {}).get("requerimientos", [])
            )
            context[iid] = value
        calcular_metricas_agente(parsed, "Calidad", context)
        for item in parsed["resultados"]:
            requirements = prepared_index[int(item["issue_iid"])].get("requerimientos", [])
            item["_rnf_excluidos"] = sum(req.get("tipo") == "RNF" for req in requirements)
        structural = validar_respuesta_lote(parsed, set(expected), "Calidad")
        content = validar_contenido_agente(parsed, "Calidad")
        if structural or content:
            raise RuntimeError("REMOTE_CONTRACT_ERROR")
    except Exception as exc:
        failure = exc
    audit = obtener_contadores()
    events = audit.get("eventos_sublotes_remotos", [])
    call_ends = [e for e in events if e.get("event") == "remote_sub_batch_call_end"]
    pacing = pacing_events
    summaries = [metric_summary(item) for item in parsed.get("resultados", [])] if parsed else []
    technical_ok = (
        failure is None
        and audit.get("llamadas_remotas") == 3
        and len(call_ends) == 3
        and all(e.get("finish_reason") == "stop" for e in call_ends)
        and [iid for e in call_ends for iid in e.get("received", [])] == expected
    )
    summary = {
        "execution_id": execution_id,
        "estado_tecnico": "completo" if technical_ok else "incompleto",
        "duracion_total_segundos": round(time.monotonic() - started, 4),
        "configuracion": {
            "provider": "groq", "model": os.environ["GROQ_MODEL_QUALITY"],
            "batch_size": 2, "max_completion_tokens": 2048,
            "reasoning_effort": "low", "reasoning_format": "hidden",
            "retries": 0, "fallback": False, "delay_seconds": 60,
        },
        "entrada_por_historia": input_by_issue,
        "llamadas_remotas": audit.get("llamadas_remotas", 0),
        "reintentos": audit.get("reintentos", 0),
        "reparaciones": audit.get("motivos_reparacion", {}),
        "fallbacks": audit.get("fallbacks_locales", 0),
        "sublotes": events,
        "pacing": pacing,
        "metricas_por_historia": summaries,
        "orden_consolidado": [x["issue_iid"] for x in summaries],
        "truncamientos": sum(e.get("error_category") == "REMOTE_TRUNCATED_RESPONSE" for e in events),
        "errores_429": sum(e.get("http_status") == 429 for e in events),
        "error_category": getattr(failure, "category", type(failure).__name__) if failure else None,
        "http_status": getattr(failure, "http_status", None) if failure else None,
        "retry_after_seconds": getattr(failure, "retry_after_seconds", None) if failure else None,
        "seguridad_ejecutada": False,
        "ollama_ejecutado": False,
        "evaluador_ejecutado": False,
        "gitlab_usado": False,
        "artefactos": {},
    }
    path = persist_sanitized_execution_summary(summary, summary_path.parent)
    print(json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=True))
    if failure:
        raise failure
    if not technical_ok:
        raise RuntimeError("QUALITY_ISOLATED_ACCEPTANCE_FAILED")


if __name__ == "__main__":
    main()
