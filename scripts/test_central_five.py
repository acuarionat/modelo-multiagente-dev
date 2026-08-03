"""Prueba real aislada del Central con cinco historias ficticias."""

import json
import os
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agents.central_agent as central
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
    expected = {
        6: ("HU-006", "Paciente", "Programar una cita médica sin conflictos de horario."),
        7: ("HU-007", "Recepcionista", "Permitir la programación de citas."),
        8: ("HU-008", "Médico", "Organizar la atención de pacientes."),
        9: ("HU-009", "Administrador", "Analizar la actividad del sistema."),
        10: ("HU-010", "Paciente", "Liberar el horario reservado"),
    }
    expected_ids = set(expected)
    reiniciar_contadores()
    started = datetime.now()
    client_metrics = {"requests": 0, "constructions": 0, "reuses": 0, "events": []}
    original_factory = central.crear_cliente_ollama_central

    def audited_factory(cache, **configuration):
        client_metrics["requests"] += 1
        before = len(cache)
        client = original_factory(cache, **configuration)
        constructed = len(cache) > before
        client_metrics["constructions"] += int(constructed)
        client_metrics["reuses"] += int(not constructed)
        client_metrics["events"].append({
            "request": client_metrics["requests"],
            "constructed": constructed,
            "reused": not constructed,
            "configuration": {
                "model": OLLAMA_MODEL,
                "num_predict": configuration.get("num_predict"),
                "num_ctx": configuration.get("num_ctx", 8192),
                "temperature": configuration.get("temperature", 0.1),
                "format": "json" if configuration.get("json_mode", True) else None,
            },
        })
        return client

    central.crear_cliente_ollama_central = audited_factory
    try:
        parsed, central_audit = central.procesar_central_en_sublotes(
            "Proyecto ficticio", ISSUES,
            "Prueba controlada del Central con HU-006 a HU-010.", batch_size=2,
        )
    except Exception as error:
        elapsed = (datetime.now() - started).total_seconds()
        audit = obtener_contadores()
        print(json.dumps({
            "estado": "error", "error_category": (
                "OLLAMA_CLIENT_CONFIGURATION_ERROR"
                if isinstance(error, FileNotFoundError) else type(error).__name__
            ),
            "duracion_total_segundos": round(elapsed, 4),
            "clientes": client_metrics,
            "auditoria_durable": audit.get("resumen_parcial_central", {}),
            "eventos_durables": audit.get("eventos_sublotes_central", []),
            "timeout_alcanzado": False, "groq_ejecutado": False,
            "otros_agentes_ejecutados": False, "gitlab_usado": False,
            "documentos_generados": False,
        }, ensure_ascii=False))
        raise SystemExit(1)
    finally:
        central.crear_cliente_ollama_central = original_factory
    elapsed = (datetime.now() - started).total_seconds()
    _attach_security_evidence(parsed, ISSUES)
    structural_errors = validar_respuesta_lote(parsed, expected_ids, "Central")
    content_warnings = validar_contenido_agente(parsed, "Central")
    by_iid = {
        item.get("issue_iid"): item for item in parsed.get("resultados", [])
        if isinstance(item, dict)
    }
    identity = {}
    for iid, (story_id, actor, objective) in expected.items():
        item = by_iid.get(iid, {})
        requirements = [
            {
                "nombre": requirement.get("nombre"),
                "tipo": requirement.get("tipo"),
                "descripcion": requirement.get("descripcion_formal"),
                "procedencia": requirement.get("procedencia"),
            }
            for requirement in item.get("requerimientos", [])
            if isinstance(requirement, dict)
        ]
        identity[iid] = {
            "historia_id": item.get("historia_id"),
            "actor": item.get("actor"),
            "objetivo": item.get("objetivo"),
            "identidad_correcta": (
                item.get("historia_id") == story_id
                and item.get("actor") == actor
                and str(item.get("objetivo") or "").rstrip(".") == objective.rstrip(".")
            ),
            "evidencia_seguridad_adjunta": isinstance(item.get("evidencia_seguridad"), dict),
            "cantidad_requerimientos": len(requirements),
            "requerimientos": requirements,
        }
    audit = obtener_contadores()
    order = [item.get("issue_iid") for item in parsed.get("resultados", []) if isinstance(item, dict)]
    success = (
        not structural_errors and set(by_iid) == expected_ids
        and order == [6, 7, 8, 9, 10]
        and all(value["identidad_correcta"] for value in identity.values())
        and all(value["cantidad_requerimientos"] for value in identity.values())
        and not central_audit["summary"]["incomplete_issue_ids"]
    )
    print(json.dumps({
        "rama_objetivo": "feature/hybrid-llm-quality-security",
        "central_batch_size": 2,
        "historias": [6, 7, 8, 9, 10],
        "proveedor": "ollama",
        "modelo": OLLAMA_MODEL,
        "duracion_total_segundos": round(elapsed, 4),
        "contrato_central_init": set(parsed) == {"agente", "milestone", "resultados"},
        "milestone_presente": bool(parsed.get("milestone")),
        "auditoria": {
            "llamadas_central": audit["por_agente"].get("Central_Init_Batch", 0),
            "duraciones_individuales": audit["duraciones_llamadas_por_agente"].get("Central_Init_Batch", []),
            "duracion_acumulada": audit["duraciones_por_agente"].get("Central_Init_Batch", 0),
            "reintentos": audit["reintentos"],
            "motivos_reparacion": audit["motivos_reparacion"].get("Central_Init_Batch", []),
            "sublotes": central_audit["records"],
            "resumen": central_audit["summary"],
            "resumen_durable": audit["resumen_parcial_central"],
            "eventos_durables": audit["eventos_sublotes_central"],
        },
        "clientes": client_metrics,
        "resultados_recibidos": sorted(by_iid),
        "historias_faltantes": central_audit["summary"]["incomplete_issue_ids"],
        "identidad": identity,
        "errores_estructurales": structural_errors,
        "advertencias_contenido": content_warnings,
        "sin_mezcla": all(value["identidad_correcta"] for value in identity.values()),
        "orden_final": order,
        "estado": "success" if success else "error",
        "timeout_alcanzado": False,
        "groq_ejecutado": False,
        "otros_agentes_ejecutados": False,
        "gitlab_usado": False,
        "documentos_generados": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
