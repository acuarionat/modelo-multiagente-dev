"""Ejecución integral controlada con cinco historias completamente ficticias."""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.test_hybrid_flow import HU010, controlled_parser
from scripts.test_remote_agents import _load_local_env


_load_local_env()
os.environ["REMOTE_LLM_MAX_RETRIES"] = "0"


def _persist_and_print_summary(payload, *, prefix="hybrid-summary", stream=None):
    """Persiste UTF-8 antes de imprimir una representación segura para CP1252."""
    from core.execution_summary import persist_sanitized_execution_summary
    persisted = dict(payload)
    persisted.setdefault("execution_id", f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}")
    path = persist_sanitized_execution_summary(persisted, os.getenv("TEMP") or None)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    printable = json.dumps(persisted, ensure_ascii=True)
    print(printable, file=stream or sys.stdout)
    return path


def _security(actor, data, *, sensitive="Sí", audit="Registro de operación ficticio."):
    return {
        "descripcion": "Evidencia de seguridad completamente ficticia.",
        "maneja_datos_sensibles": sensitive,
        "tipos_datos_sensibles": data,
        "autenticacion": "Usuario y contraseña ficticios.",
        "autorizacion_roles": f"Rol {actor}.",
        "auditoria": audit,
    }


ISSUES = [
    {
        "id": 6, "historia_id": "HU-006", "titulo": "Consultar horarios médicos",
        "descripcion_original": "Historia ficticia para consultar horarios y programar una cita sin conflictos.",
        "actor": "Paciente", "funcionalidad": "Consultar horarios disponibles",
        "objetivo": "Programar una cita médica sin conflictos de horario.",
        "criterios_aceptacion": [
            "Mostrar únicamente horarios disponibles.",
            "Mostrar nombre y especialidad del médico.",
            "Actualizar la disponibilidad después de programar la cita.",
        ],
        "restricciones": ["El tiempo de respuesta deberá ser menor a tres segundos."],
        "observaciones": "La información de disponibilidad deberá mostrarse en tiempo real.",
        "seguridad": _security("Paciente", ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"]),
        "prioridad": "Alta",
    },
    {
        "id": 7, "historia_id": "HU-007", "titulo": "Registrar pacientes",
        "descripcion_original": "Historia ficticia para registrar pacientes y permitir programar citas.",
        "actor": "Recepcionista", "funcionalidad": "Registrar pacientes",
        "objetivo": "Permitir la programación de citas.",
        "criterios_aceptacion": [
            "Validar el documento del paciente.",
            "Registrar la información del paciente.",
            "Impedir registros duplicados por documento.",
        ],
        "restricciones": [],
        "observaciones": "Permitir editar la información del paciente.",
        "seguridad": _security("Recepcionista", ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"]),
        "prioridad": "Alta",
    },
    {
        "id": 8, "historia_id": "HU-008", "titulo": "Consultar agenda médica",
        "descripcion_original": "Historia ficticia para consultar la agenda y organizar la atención diaria.",
        "actor": "Médico", "funcionalidad": "Consultar agenda médica",
        "objetivo": "Organizar la atención de pacientes.",
        "criterios_aceptacion": [
            "Mostrar las citas del día.",
            "Mostrar el nombre del paciente en cada cita.",
        ],
        "restricciones": [],
        "observaciones": "La agenda deberá actualizarse en tiempo real.",
        "seguridad": _security("Médico", ["Nombre ficticio: PERSONAL", "Motivo clínico ficticio: CLÍNICO"]),
        "prioridad": "Alta",
    },
    {
        "id": 9, "historia_id": "HU-009", "titulo": "Generar reportes de citas",
        "descripcion_original": "Historia ficticia para generar reportes y analizar la actividad del sistema.",
        "actor": "Administrador", "funcionalidad": "Generar reportes de citas",
        "objetivo": "Analizar la actividad del sistema.",
        "criterios_aceptacion": [
            "Filtrar los reportes por fecha.",
            "Exportar los reportes en PDF.",
            "Mostrar estadísticas de citas.",
        ],
        "restricciones": [],
        "observaciones": "Los reportes deben poder imprimirse.",
        "seguridad": _security("Administrador", [] , sensitive="No"),
        "prioridad": "Media",
    },
    {**HU010, "historia_id": "HU-010"},
]

for issue in ISSUES:
    issue["validacion_entrada"] = {
        "estado": "entrada_valida", "campos_faltantes": [], "advertencias": [],
    }


def _require_configuration():
    expected = {
        "ENABLE_REMOTE_LLM": "true",
        "ENABLE_LOCAL_FALLBACK": "false",
        "LLM_PROVIDER_QUALITY": "groq",
        "LLM_PROVIDER_SECURITY": "groq",
        "GROQ_MODEL_QUALITY": "openai/gpt-oss-120b",
        "GROQ_MODEL_SECURITY": "openai/gpt-oss-120b",
        "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "2048",
        "REMOTE_SECURITY_MAX_COMPLETION_TOKENS": "2048",
        "REMOTE_REASONING_EFFORT": "low",
        "REMOTE_REASONING_FORMAT": "hidden",
        "REMOTE_LLM_MAX_RETRIES": "0",
    }
    invalid = [key for key, value in expected.items() if os.getenv(key, "").casefold() != value]
    if invalid or not os.getenv("GROQ_API_KEY", "").strip():
        raise SystemExit("Configuración híbrida incompleta o inválida: " + ", ".join(invalid))


def _write_artifacts(final, output_dir, execution_id, summary_base):
    from core.utils import (
        construir_resultado_lote, generar_artefactos_atomicos,
    )
    batch = construir_resultado_lote(
        "Proyecto ficticio", "Prueba híbrida controlada HU-006 a HU-010", final["resultados"],
    )
    model, paths, summary_path = generar_artefactos_atomicos(
        batch, output_dir, execution_id, summary_base,
        expected_issue_ids=[6, 7, 8, 9, 10], expected_rf=17, expected_rnf=3,
    )
    return model, paths, {}, 7, summary_path


def _story_summary(result):
    central = result["central"]
    quality = result["quality"]
    security = result["security"]
    evaluation = result["evaluation"]
    mc01 = quality["metricas"]["cobertura_funcional"]
    mc02 = quality["metricas"]["adecuacion_funcional"]
    ms01 = security["metricas"]["cobertura_seguridad"]
    ms02 = security["metricas"]["clasificacion_datos"]
    return {
        "issue_iid": result["issue_iid"], "historia_id": central.get("historia_id"),
        "status": result["status"], "actor": central.get("actor"), "objetivo": central.get("objetivo"),
        "calidad": {
            "funciones_especificadas": mc01["funciones_especificadas"],
            "funciones_incluidas": mc01["funciones_incluidas"],
            "funciones_faltantes": mc01["funciones_faltantes"],
            "A": len(mc01["funciones_faltantes"]), "B": len(mc01["funciones_especificadas"]),
            "MC-01": mc01.get("valor"),
            "funciones_evaluables": mc02["funciones_evaluables"],
            "funciones_alineadas": mc02["funciones_alineadas"],
            "funciones_no_alineadas": mc02["funciones_no_alineadas"],
            "MC-02": mc02.get("valor"), "indice": quality.get("indice"),
            "meta": quality.get("indicador", {}).get("meta"),
            "estado": quality.get("indicador", {}).get("estado"),
        },
        "seguridad": {
            "aspectos_aplicables": ms01["aspectos_aplicables"],
            "aspectos_documentados": ms01["aspectos_documentados"],
            "aspectos_parciales": ms01["aspectos_parciales"],
            "aspectos_faltantes": ms01["aspectos_faltantes"],
            "datos_identificados": ms02["datos_identificados"],
            "datos_clasificados_explicitos": ms02["datos_clasificados"],
            "datos_sin_clasificacion": ms02["datos_sin_clasificacion"],
            "clasificaciones_sugeridas": ms02["clasificaciones_inferidas"],
            "MS-01": ms01.get("valor"), "MS-02": ms02.get("valor"),
            "indice": security.get("indice"), "lot": security.get("lot_recomendado"),
            "meta": security.get("indicador", {}).get("meta"),
            "estado": security.get("indicador", {}).get("estado"),
        },
        "veredicto": evaluation.get("veredicto"),
        "requerimientos": [{
            "id": item.get("id"), "nombre": item.get("nombre"), "tipo": item.get("tipo"),
            "descripcion": item.get("descripcion_formal"), "procedencia": item.get("procedencia"),
        } for item in central.get("requerimientos", [])],
        "recomendaciones": result.get("recommendations", []),
        "riesgos": evaluation.get("riesgos_criticos", []),
    }


def main():
    _require_configuration()
    from core.config import OLLAMA_MODEL
    if OLLAMA_MODEL != "phi4-mini":
        raise SystemExit("Central y Evaluador deben usar phi4-mini.")
    from core.graph import construir_grafo
    import core.graph as graph_module
    from core.performance_audit import obtener_contadores, reiniciar_contadores

    reiniciar_contadores()
    original_parser = graph_module._analizar_con_un_reintento
    graph_module._analizar_con_un_reintento = lambda raw, agent_name, retry_call: controlled_parser(
        original_parser, raw, agent_name, retry_call,
    )
    state = {
        "project_name": "Proyecto ficticio",
        "sprint_context": "Prueba integral controlada con cinco historias ficticias.",
        "issues_data": ISSUES,
        "validation_errors": [], "content_validation_errors": {},
    }
    execution_id = datetime.now().strftime("hybrid-five-%Y%m%d-%H%M%S-%f")
    from core.execution_summary import persist_sanitized_execution_summary
    persist_sanitized_execution_summary({
        "execution_id": execution_id, "status": "running",
        "estado_tecnico": "running", "etapa_alcanzada": "inicio",
        "artefactos": {}, "documents_generated": False, "gitlab_usado": False,
    }, os.getenv("TEMP") or None)
    started = datetime.now()
    try:
        final_state = construir_grafo().invoke(state)
    except Exception as exc:
        from core.execution_summary import (
            build_sanitized_execution_summary, persist_sanitized_execution_summary,
        )
        audit = obtener_contadores()
        completed = audit.get("resumen_parcial_remoto", {}).get("completed_issue_ids", [])
        if not completed:
            completed = audit.get("resumen_parcial_central", {}).get("received", [])
        partial = build_sanitized_execution_summary(
            execution_id=execution_id, estado="incompleto",
            etapa_alcanzada=(getattr(exc, "agent", None) or "flujo"),
            auditoria=audit, historias_esperadas=[int(item["id"]) for item in ISSUES],
            historias_completas=completed, error=exc, artefactos={}, gitlab_usado=False,
        )
        path = persist_sanitized_execution_summary(partial, os.getenv("TEMP") or None)
        print(path.read_text(encoding="utf-8").encode("ascii", "backslashreplace").decode("ascii"))
        exc.summary_path = str(path)
        raise
    elapsed = (datetime.now() - started).total_seconds()
    final = json.loads(final_state["final_report"])
    summaries = [_story_summary(result) for result in final["resultados"]]
    expected_identity = {
        int(issue["id"]): (issue.get("historia_id"), issue.get("actor")) for issue in ISSUES
    }
    identity_ok = len(summaries) == len(expected_identity) and all(
        expected_identity.get(item["issue_iid"]) == (item["historia_id"], item["actor"])
        for item in summaries
    )
    audit = obtener_contadores()
    semantic_ok = all(
        item["issue_iid"] != 6 or (
            len(item["requerimientos"]) == 5
            and sum(req["tipo"] == "RF" for req in item["requerimientos"]) == 3
            and sum(req["tipo"] == "RNF" for req in item["requerimientos"]) == 2
            and item["calidad"]["B"] == 3
            and item["calidad"]["A"] == 0
            and item["calidad"]["MC-01"] == 1.0
            and len(item["calidad"]["funciones_evaluables"]) == 3
            and len(item["calidad"]["funciones_alineadas"]) == 3
            and item["calidad"]["MC-02"] == 1.0
        ) for item in summaries
    )
    complete = identity_ok and semantic_ok and all(item["status"] == "ok" for item in summaries)
    safe = audit["fallbacks_locales"] == 0
    paths, artifact_errors, columns, batch_summary = {}, {}, 0, {}
    summary_path = None
    summary_base = {
        "execution_id": execution_id,
        "rama_objetivo": "feature/hybrid-llm-quality-security",
        "duracion_total_segundos": round(elapsed, 4),
        "auditoria": audit,
        "identidad_correcta": identity_ok,
        "resultados": summaries,
        "gitlab_usado": False,
    }
    if complete and safe:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path(os.getenv("TEMP", "C:/tmp")) / f"hybrid-five-{stamp}"
        batch, paths, artifact_errors, columns, summary_path = _write_artifacts(
            final, output_dir, execution_id, summary_base,
        )
        batch_summary = batch["summary"]
    summary = {
        "execution_id": execution_id,
        "status": "success" if complete and safe and paths and not artifact_errors else "error",
        "documents_generated": bool(paths) and not artifact_errors,
        "rama_objetivo": "feature/hybrid-llm-quality-security",
        "duracion_total_segundos": round(elapsed, 4),
        "proveedores": {
            "Central_Init": {"provider": "ollama", "model": OLLAMA_MODEL},
            "Quality": {"provider": "groq", "model": os.getenv("GROQ_MODEL_QUALITY")},
            "Security": {"provider": "groq", "model": os.getenv("GROQ_MODEL_SECURITY")},
            "Evaluator": {"provider": "ollama", "model": OLLAMA_MODEL},
            "Central_Final": {"provider": "python", "model": None},
        },
        "auditoria": audit, "identidad_correcta": identity_ok,
        "estado_tecnico": "ok" if complete and safe else "error",
        "validacion_semantica": semantic_ok,
        "resultados": summaries, "resumen_documental": batch_summary,
        "auditoria_documental": batch.get("documentary_audit", {}) if complete and safe else {},
        "artefactos": paths, "errores_artefactos": artifact_errors,
        "columnas_matriz": columns, "gitlab_usado": False,
    }
    if summary_path:
        summary["resumen_json_temporal"] = str(summary_path)
    _persist_and_print_summary(summary, prefix="hybrid-five-summary")


if __name__ == "__main__":
    main()
