"""Una llamada real y aislada de Seguridad exclusivamente para HU-010."""

import json
import os
import sys
import tempfile
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_remote_agents import _load_local_env

_load_local_env()
os.environ.update({
    "ENABLE_REMOTE_LLM": "true",
    "ENABLE_LOCAL_FALLBACK": "false",
    "LLM_PROVIDER_SECURITY": "groq",
    "GROQ_MODEL_SECURITY": "openai/gpt-oss-120b",
    "REMOTE_SECURITY_BATCH_SIZE": "1",
    "REMOTE_SECURITY_MAX_COMPLETION_TOKENS": "2048",
    "REMOTE_REASONING_EFFORT": "low",
    "REMOTE_REASONING_FORMAT": "hidden",
    "REMOTE_LLM_MAX_RETRIES": "0",
})

from agents.llm_invocation import obtener_ultimos_metadatos
from agents.security_agent import analizar_seguridad
from core.batch_contract import (
    calcular_metricas_agente, obtener_universo_datos_seguridad,
    resumir_seguridad_post_python,
)
from core.execution_summary import persist_sanitized_execution_summary
from core.graph import _ejecutar_sublotes_remotos
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import reiniciar_pacing_remoto
from scripts.test_hybrid_flow import HU010


def _central_payload():
    payload = {
        "agente": "central",
        "resultados": [{
            "issue_iid": 10,
            "historia_id": "HU-010",
            "titulo": "Cancelar cita médica",
            "actor": "Paciente",
            "objetivo": "Liberar el horario reservado",
            "prioridad": "Alta",
            "requerimientos": [{
                "temp_id": "RF-TEMP-01",
                "nombre": "Permitir cancelar una cita",
                "descripcion_formal": "El sistema deberá permitir cancelar una cita médica.",
                "tipo": "RF",
                "origen": "Cancelar una cita",
                "justificacion": "Funcionalidad explícita.",
                "prioridad": "Alta",
                "procedencia": "explícita — funcionalidad",
            }, {
                "temp_id": "RF-TEMP-02",
                "nombre": "Restringir la cancelación con menos de 24 horas",
                "descripcion_formal": (
                    "El sistema deberá impedir la cancelación de una cita cuando falten "
                    "menos de 24 horas para su realización."
                ),
                "tipo": "RF",
                "origen": "No se podrá cancelar cuando falten menos de 24 horas.",
                "justificacion": "Regla funcional explícita.",
                "prioridad": "Alta",
                "procedencia": "explícita — restricción",
            }],
            "restricciones": ["No se podrá cancelar cuando falten menos de 24 horas."],
            "ambiguedades": [],
            "informacion_faltante": [],
            "observaciones": [],
            "evidencia_seguridad": deepcopy(HU010["seguridad"]),
        }],
    }
    item = payload["resultados"][0]
    item["datos_canonicos_identificados"] = obtener_universo_datos_seguridad(
        item, item["evidencia_seguridad"],
    )
    return payload


def _metric_summary(parsed):
    if not parsed or not parsed.get("resultados"):
        return {}
    item = parsed["resultados"][0]
    metrics = item.get("metricas", {})
    ms01 = metrics.get("cobertura_seguridad", {})
    ms02 = metrics.get("clasificacion_datos", {})
    indicator = item.get("indicador", {})
    return {
        "aspectos_aplicables": len(ms01.get("aspectos_aplicables", [])),
        "aspectos_documentados": len(ms01.get("aspectos_documentados", [])),
        "aspectos_parciales": len(ms01.get("aspectos_parciales", [])),
        "aspectos_faltantes": len(ms01.get("aspectos_faltantes", [])),
        "datos_identificados": len(ms02.get("datos_identificados", [])),
        "datos_clasificados_explicitos": len(ms02.get("datos_clasificados", [])),
        "datos_sin_clasificacion": len(ms02.get("datos_sin_clasificacion", [])),
        "clasificaciones_inferidas": len(ms02.get("clasificaciones_inferidas", [])),
        "ms01": ms01.get("valor"),
        "ms02": ms02.get("valor"),
        "indice_seguridad": indicator.get("valor"),
        "lot": item.get("lot_recomendado"),
        "meta": indicator.get("meta"),
        "estado": indicator.get("estado"),
        "recomendacion_resumida": (
            "Clasificar explícitamente los datos canónicos sin clasificación."
            if ms02.get("datos_sin_clasificacion") else None
        ),
        "riesgos": len(item.get("riesgos", [])) if isinstance(item.get("riesgos"), list) else 0,
    }


def main():
    if not os.getenv("GROQ_API_KEY", "").strip():
        raise SystemExit("Configuración remota incompleta: GROQ_API_KEY ausente.")

    execution_id = f"security-010-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    summary_dir = Path(tempfile.gettempdir())
    initial = {
        "execution_id": execution_id,
        "estado_tecnico": "preparado",
        "expected_issue_ids": [10],
        "calidad_ejecutada": False,
        "ollama_ejecutado": False,
        "evaluador_ejecutado": False,
        "gitlab_usado": False,
    }
    summary_path = persist_sanitized_execution_summary(initial, summary_dir)
    reiniciar_contadores()
    reiniciar_pacing_remoto()
    started = time.monotonic()
    payload = _central_payload()
    canonical_data_count = len(payload["resultados"][0]["datos_canonicos_identificados"])
    parsed = None
    failure = None
    try:
        parsed = _ejecutar_sublotes_remotos(
            json.dumps(payload, ensure_ascii=False),
            "Seguridad",
            1,
            lambda raw, sub_batch: analizar_seguridad(raw, sub_batch=sub_batch),
        )
        calcular_metricas_agente(parsed, "Seguridad", {10: deepcopy(HU010)})
    except Exception as exc:
        failure = exc

    audit = obtener_contadores()
    events = audit.get("eventos_sublotes_remotos", [])
    final_event = next(
        (event for event in reversed(events) if event.get("event") == "remote_sub_batch_end"),
        {},
    )
    call_event = next(
        (event for event in events if event.get("event") == "remote_sub_batch_call_end"),
        {},
    )
    metadata = obtener_ultimos_metadatos("Security")
    result_summary = _metric_summary(parsed) if failure is None else {}
    received = final_event.get("received_issue_ids", final_event.get("received", []))
    summary = {
        "execution_id": execution_id,
        "estado_tecnico": "completo" if failure is None else "incompleto",
        "duracion_total_segundos": round(time.monotonic() - started, 4),
        "duracion_remota_segundos": call_event.get("elapsed_seconds") or final_event.get("elapsed_seconds"),
        "http_status": getattr(failure, "http_status", None) if failure else 200,
        "finish_reason": metadata.get("finish_reason"),
        "json_valido": final_event.get("json_valid"),
        "json_recuperado": final_event.get("json_recovered", False),
        "expected_issue_ids": [10],
        "received_issue_ids": received,
        "identity_validation": final_event.get("identity_validation"),
        "contract_validation": final_event.get("contract_validation"),
        "semantic_validation": final_event.get("semantic_validation"),
        "failed_semantic_rule": final_event.get("failed_semantic_rule"),
        "semantic_subcategory": final_event.get("semantic_subcategory"),
        "affected_section": next((x.get("affected_section") for x in final_event.get("semantic_by_issue", []) if x.get("affected_section")), None),
        "affected_field": next((x.get("affected_field") for x in final_event.get("semantic_by_issue", []) if x.get("affected_field")), None),
        "security_llm_raw_diagnostic": final_event.get("security_llm_raw_diagnostic", []),
        "security_normalized_summary": final_event.get("security_normalized_summary", []),
        "security_post_python_summary": resumir_seguridad_post_python(parsed) if parsed and failure is None else [],
        "canonical_data_count": canonical_data_count,
        "resultado_seguridad": result_summary,
        "llamadas_remotas": audit.get("llamadas_remotas", 0),
        "reintentos": audit.get("reintentos", 0),
        "reparaciones": audit.get("motivos_reparacion", {}),
        "fallbacks": audit.get("fallbacks_locales", 0),
        "remote_rate_pacing_applied": any(event.get("event") == "remote_rate_pacing" for event in events),
        "calidad_ejecutada": False,
        "ollama_ejecutado": audit.get("llamadas_ollama", 0) > 0,
        "evaluador_ejecutado": False,
        "gitlab_usado": False,
        "error_category": getattr(failure, "category", type(failure).__name__) if failure else None,
    }
    summary_path.write_text(json.dumps({**summary, "resumen_json_temporal": str(summary_path)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(json.loads(summary_path.read_text(encoding="utf-8")), ensure_ascii=True))
    if failure is not None:
        raise failure
    if audit.get("llamadas_remotas") != 1:
        raise RuntimeError("UNEXPECTED_REMOTE_CALL_COUNT")


if __name__ == "__main__":
    main()
