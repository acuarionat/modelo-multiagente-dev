"""Diagnóstico real y aislado de reutilización del cliente Central local."""

import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.test_remote_agents import _load_local_env

_load_local_env()

import agents.central_agent as central
from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.performance_audit import (
    obtener_contadores, registrar_evento_sublote_central, reiniciar_contadores,
)


NUM_PREDICT = 500
NUM_CTX = 8192
TEMPERATURE = 0.1

HISTORIES = [
    {
        "id": 9001, "historia_id": "DIAG-001", "actor": "Usuario",
        "funcionalidad": "Consultar un registro",
        "objetivo": "Obtener información actualizada.",
        "criterios_aceptacion": ["Mostrar el registro solicitado."],
        "restricciones": [], "observaciones": "", "prioridad": "Media",
    },
    {
        "id": 9002, "historia_id": "DIAG-002", "actor": "Administrador",
        "funcionalidad": "Registrar un elemento",
        "objetivo": "Mantener la información disponible.",
        "criterios_aceptacion": ["Confirmar el registro del elemento."],
        "restricciones": [], "observaciones": "", "prioridad": "Media",
    },
]


def _ssl_status():
    names = (
        "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE", "HTTPX_CA_BUNDLE",
    )
    return {
        name: {
            "defined": bool(os.getenv(name)),
            "path_valid": os.path.exists(os.getenv(name)) if os.getenv(name) else None,
        }
        for name in names
    }


def main():
    if OLLAMA_MODEL != "phi4-mini" or OLLAMA_BASE_URL != "http://localhost:11434":
        raise SystemExit("Configuración local distinta de phi4-mini/http://localhost:11434")

    reiniciar_contadores()
    cache = {}
    requests = 0
    constructions = 0
    original_constructor = central.obtener_llm

    def counted_constructor(**kwargs):
        nonlocal constructions
        constructions += 1
        return original_constructor(**kwargs)

    central.obtener_llm = counted_constructor
    calls = []
    client_ids = []
    try:
        for number, story in enumerate(HISTORIES, 1):
            requests += 1
            client = central.crear_cliente_ollama_central(
                cache, num_predict=NUM_PREDICT, num_ctx=NUM_CTX,
                temperature=TEMPERATURE, json_mode=True,
            )
            client_ids.append(id(client))
            reused = number > 1 and client is previous_client
            started = time.perf_counter()
            registrar_evento_sublote_central(
                "central_sub_batch_start", sub_batch=number, split_level=0,
                issue_ids=[story["id"]], call_type="diagnostic",
                attempt=1, num_predict=NUM_PREDICT, status="started",
                received=[], missing=[story["id"]],
            )
            registrar_evento_sublote_central(
                "central_sub_batch_call_start", sub_batch=number, split_level=0,
                issue_ids=[story["id"]], call_type="diagnostic",
                attempt=1, num_predict=NUM_PREDICT, status="started",
                received=[], missing=[story["id"]],
            )
            status = "failed"
            call = {
                "number": number, "client_reused": reused,
                "json_valid": False, "json_recovered": False,
                "error_category": None,
            }
            try:
                raw = central.procesar_ticket(
                    "Proyecto diagnóstico ficticio",
                    json.dumps([story], ensure_ascii=False),
                    "Contexto ficticio aislado.",
                    num_predict_override=NUM_PREDICT,
                    llm_override=client,
                )
                _, metadata = central._normalizar_respuesta_central(raw)
                call["json_valid"] = metadata["json_valid"]
                call["json_recovered"] = metadata["json_recovered"]
                call["response_category"] = metadata["response_category"]
                status = "success"
                registrar_evento_sublote_central(
                    "central_sub_batch_call_end", sub_batch=number, split_level=0,
                    issue_ids=[story["id"]], call_type="diagnostic",
                    attempt=1, num_predict=NUM_PREDICT,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    status=status, received=[story["id"]], missing=[],
                )
            except Exception as error:
                call["error_category"] = (
                    "OLLAMA_CLIENT_CONFIGURATION_ERROR"
                    if isinstance(error, FileNotFoundError) else type(error).__name__
                )
                registrar_evento_sublote_central(
                    "central_sub_batch_error", sub_batch=number, split_level=0,
                    issue_ids=[story["id"]], call_type="diagnostic",
                    attempt=1, num_predict=NUM_PREDICT,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    status="failed", error_category=call["error_category"],
                    received=[], missing=[story["id"]],
                )
            finally:
                call["duration_seconds"] = round(time.perf_counter() - started, 4)
                calls.append(call)
                registrar_evento_sublote_central(
                    "central_sub_batch_end", sub_batch=number, split_level=0,
                    issue_ids=[story["id"]], call_type="diagnostic",
                    num_predict=NUM_PREDICT, elapsed_seconds=call["duration_seconds"],
                    status=status, received=[story["id"]] if status == "success" else [],
                    missing=[] if status == "success" else [story["id"]],
                )
            if status != "success":
                break
            previous_client = client
    finally:
        central.obtener_llm = original_constructor

    audit = obtener_contadores()
    completed = sum(call["error_category"] is None for call in calls)
    print(json.dumps({
        "provider": "ollama", "model": OLLAMA_MODEL, "base_url": OLLAMA_BASE_URL,
        "configuration": {
            "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX,
            "temperature": TEMPERATURE, "format": "json",
        },
        "ssl": _ssl_status(),
        "client_requests": requests, "client_constructions": constructions,
        "invocations_started": len(calls), "invocations_completed": completed,
        "same_instance": len(client_ids) == 2 and client_ids[0] == client_ids[1],
        "calls": calls,
        "total_duration_seconds": round(sum(call["duration_seconds"] for call in calls), 4),
        "audit_events": [event["event"] for event in audit["eventos_sublotes_central"]],
        "partial_summary": audit["resumen_parcial_central"],
        "groq_calls": audit["llamadas_remotas"],
        "other_agents_executed": False, "gitlab_used": False,
        "documents_generated": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
