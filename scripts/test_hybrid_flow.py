"""Ejecución integral controlada con una única historia ficticia."""

import csv
import json
import os
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.test_remote_agents import _load_local_env

_load_local_env()
os.environ["REMOTE_LLM_MAX_RETRIES"] = "0"


HU010 = {
    "id": 10,
    "titulo": "Cancelar cita médica",
    "descripcion_original": (
        "Como Paciente, quiero cancelar una cita para liberar el horario reservado. "
        "La cancelación no estará permitida cuando falten menos de 24 horas."
    ),
    "actor": "Paciente",
    "funcionalidad": "Cancelar una cita",
    "objetivo": "Liberar el horario reservado",
    "criterios_aceptacion": [
        "El paciente puede cancelar una cita.",
        "No se podrá cancelar cuando falten menos de 24 horas.",
    ],
    "restricciones": ["No se podrá cancelar cuando falten menos de 24 horas."],
    "seguridad": {
        "descripcion": "Datos personales de una cita ficticia.",
        "maneja_datos_sensibles": "Sí: nombre y documento ficticios.",
        "tipos_datos_sensibles": ["Nombre ficticio", "Documento ficticio"],
        "autenticacion": "Usuario y contraseña ficticios.",
        "autorizacion_roles": "Rol Paciente.",
        "auditoria": "Registro de cancelación ficticio.",
    },
    "observaciones": "",
    "prioridad": "Alta",
    "validacion_entrada": {"estado": "entrada_valida", "campos_faltantes": [], "advertencias": []},
}


def controlled_parser(original_parser, raw, agent_name, retry_call):
    if agent_name in {"Calidad", "Seguridad"}:
        from core.batch_contract import analizar_respuesta_lote
        return analizar_respuesta_lote(raw, agent_name), raw
    return original_parser(raw, agent_name, retry_call)


def _require_configuration():
    expected = {
        "ENABLE_REMOTE_LLM": "true",
        "ENABLE_LOCAL_FALLBACK": "false",
        "LLM_PROVIDER_QUALITY": "groq",
        "LLM_PROVIDER_SECURITY": "groq",
        "GROQ_MODEL_QUALITY": "openai/gpt-oss-120b",
        "GROQ_MODEL_SECURITY": "openai/gpt-oss-120b",
    }
    invalid = [key for key, value in expected.items() if os.getenv(key, "").casefold() != value]
    if invalid or not os.getenv("GROQ_API_KEY", "").strip():
        raise SystemExit("Configuración híbrida incompleta o inválida.")


def _write_artifacts(final, output_dir):
    from core.utils import (
        construir_filas_trazabilidad, construir_resultado_lote,
        generar_documento_formal_lote_docx, generar_reporte_lote_pdf,
    )
    batch = construir_resultado_lote("Proyecto ficticio", "Diagnóstico HU-010", final["resultados"])
    rows = construir_filas_trazabilidad(batch["issues"], batch["generated_at"])
    paths, errors = {}, {}
    csv_path = output_dir / "matriz_trazabilidad.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    paths["csv"] = str(csv_path)
    for kind, filename, generator in (
        ("docx", "requerimientos.docx", generar_documento_formal_lote_docx),
        ("pdf", "reporte.pdf", generar_reporte_lote_pdf),
    ):
        try:
            artifact = generator(batch).getvalue()
            path = output_dir / filename
            path.write_bytes(artifact)
            paths[kind] = str(path)
        except (ImportError, ModuleNotFoundError) as exc:
            errors[kind] = f"dependencia ausente: {type(exc).__name__}"
    return batch, paths, errors


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
        "sprint_context": "Diagnóstico controlado de una historia ficticia.",
        "issues_data": [HU010],
        "validation_errors": [],
        "content_validation_errors": {},
    }
    final_state = construir_grafo().invoke(state)
    final = json.loads(final_state["final_report"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(os.getenv("TEMP", "C:/tmp")) / f"hybrid-hu010-{stamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    batch, paths, artifact_errors = _write_artifacts(final, output_dir)
    result = final["resultados"][0]
    q, s, e, c = result["quality"], result["security"], result["evaluation"], result["central"]
    mc01, mc02 = q["metricas"]["cobertura_funcional"], q["metricas"]["adecuacion_funcional"]
    ms01, ms02 = s["metricas"]["cobertura_seguridad"], s["metricas"]["clasificacion_datos"]
    print(json.dumps({
        "rama_objetivo": "feature/hybrid-llm-quality-security",
        "proveedores": {
            "Central_Init": {"provider": "ollama", "model": OLLAMA_MODEL},
            "Quality": {"provider": "groq", "model": os.getenv("GROQ_MODEL_QUALITY")},
            "Security": {"provider": "groq", "model": os.getenv("GROQ_MODEL_SECURITY")},
            "Evaluator": {"provider": "ollama", "model": OLLAMA_MODEL},
            "Central_Final": {"provider": "python", "model": None},
        },
        "auditoria": obtener_contadores(),
        "status": result["status"],
        "identificadores_conservados": result["issue_iid"] == 10 and c.get("historia_id") == "HU-010",
        "actor": c.get("actor"), "objetivo": c.get("objetivo"),
        "mc01": {"A_faltantes": len(mc01["funciones_faltantes"]), "B_especificadas": len(mc01["funciones_especificadas"]), "valor": mc01.get("valor")},
        "mc02": {"alineadas": len(mc02["funciones_alineadas"]), "evaluables": len(mc02["funciones_evaluables"]), "valor": mc02.get("valor")},
        "indice_calidad": q.get("indice"), "estado_calidad": q.get("indicador", {}).get("estado"),
        "ms01": {"documentados": len(ms01["aspectos_documentados"]), "aplicables": len(ms01["aspectos_aplicables"]), "valor": ms01.get("valor")},
        "ms02": {"clasificados": len(ms02["datos_clasificados"]), "identificados": len(ms02["datos_identificados"]), "sin_clasificacion": len(ms02["datos_sin_clasificacion"]), "valor": ms02.get("valor")},
        "indice_seguridad": s.get("indice"), "lot": s.get("lot_recomendado"), "estado_seguridad": s.get("indicador", {}).get("estado"),
        "veredicto": e.get("veredicto"), "riesgos": e.get("riesgos_criticos", []),
        "recomendaciones": result.get("recommendations", []),
        "requerimientos": [{"tipo": x.get("tipo"), "descripcion": x.get("descripcion_formal"), "procedencia": x.get("procedencia")} for x in c.get("requerimientos", [])],
        "revision_humana": result.get("estado_revision_humana"),
        "resumen_documental": batch["summary"], "artefactos": paths,
        "errores_artefactos": artifact_errors, "gitlab_usado": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
