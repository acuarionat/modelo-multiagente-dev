"""Prueba real controlada de un único sublote local del Agente Central."""

import json
import os
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.central_agent import procesar_central_en_sublotes
from core.batch_contract import validar_contenido_agente, validar_respuesta_lote
from core.performance_audit import obtener_contadores, reiniciar_contadores
from scripts.test_hybrid_flow_five import ISSUES
from scripts.test_remote_agents import _load_local_env


_load_local_env()
os.environ["CENTRAL_BATCH_SIZE"] = "2"


def _attach_security_evidence(parsed, issues):
    evidence = {int(issue["id"]): dict(issue.get("seguridad") or {}) for issue in issues}
    for item in parsed.get("resultados", []):
        if isinstance(item, dict) and item.get("issue_iid") in evidence:
            item["evidencia_seguridad"] = evidence[item["issue_iid"]]


def main():
    from core.config import OLLAMA_MODEL
    if OLLAMA_MODEL != "phi4-mini":
        raise SystemExit("El Central debe usar phi4-mini.")
    issues = ISSUES[:2]
    reiniciar_contadores()
    started = datetime.now()
    parsed, central_audit = procesar_central_en_sublotes(
        "Proyecto ficticio", issues,
        "Prueba controlada del Central con HU-006 y HU-007.", batch_size=2,
    )
    elapsed = (datetime.now() - started).total_seconds()
    _attach_security_evidence(parsed, issues)
    structural_errors = validar_respuesta_lote(parsed, {6, 7}, "Central")
    content_errors = validar_contenido_agente(parsed, "Central")
    by_iid = {
        item.get("issue_iid"): item for item in parsed.get("resultados", [])
        if isinstance(item, dict)
    }
    expected = {
        6: ("HU-006", "Paciente", "Programar una cita médica sin conflictos de horario."),
        7: ("HU-007", "Recepcionista", "Permitir la programación de citas."),
    }
    identity = {}
    for iid, (story_id, actor, objective) in expected.items():
        item = by_iid.get(iid, {})
        identity[iid] = {
            "historia_id": item.get("historia_id"), "actor": item.get("actor"),
            "objetivo": item.get("objetivo"),
            "identidad_correcta": (
                item.get("historia_id") == story_id
                and item.get("actor") == actor
                and item.get("objetivo") == objective
            ),
            "evidencia_seguridad_adjunta": isinstance(item.get("evidencia_seguridad"), dict),
            "requerimientos": [{
                "nombre": requirement.get("nombre"),
                "tipo": requirement.get("tipo"),
                "descripcion": requirement.get("descripcion_formal"),
            } for requirement in item.get("requerimientos", []) if isinstance(requirement, dict)],
        }
    audit = obtener_contadores()
    records = central_audit["records"]
    success = (
        not structural_errors and set(by_iid) == {6, 7}
        and all(value["identidad_correcta"] for value in identity.values())
        and all(value["requerimientos"] for value in identity.values())
        and central_audit["summary"]["incomplete_issue_ids"] == []
    )
    print(json.dumps({
        "rama_objetivo": "feature/hybrid-llm-quality-security",
        "central_batch_size": 2, "historias": [6, 7],
        "proveedor": "ollama", "modelo": OLLAMA_MODEL,
        "duracion_total_segundos": round(elapsed, 4),
        "contrato_central_init": set(parsed) == {"agente", "milestone", "resultados"},
        "auditoria": {
            "llamadas_central": audit["por_agente"].get("Central_Init_Batch", 0),
            "duraciones_individuales": audit["duraciones_llamadas_por_agente"].get("Central_Init_Batch", []),
            "duracion_acumulada": audit["duraciones_por_agente"].get("Central_Init_Batch", 0),
            "reintentos": audit["reintentos"],
            "reparaciones": audit["motivos_reparacion"].get("Central_Init_Batch", []),
            "sublotes": records,
            "resumen": central_audit["summary"],
        },
        "resultados_recibidos": sorted(by_iid),
        "historias_faltantes": central_audit["summary"]["incomplete_issue_ids"],
        "identidad": identity,
        "errores_estructurales": structural_errors,
        "advertencias_contenido": content_errors,
        "sin_mezcla": all(value["identidad_correcta"] for value in identity.values()),
        "estado": "success" if success else "error",
        "otros_agentes_ejecutados": False,
        "gitlab_usado": False, "documentos_generados": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
