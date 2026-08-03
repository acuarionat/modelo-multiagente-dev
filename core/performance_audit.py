import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger("performance_audit")
_CONTADORES = {
    "llamadas_ollama": 0,
    "llamadas_remotas": 0,
    "fallbacks_locales": 0,
    "reintentos": 0,
    "por_agente": {},
    "duraciones_por_agente": {},
    "duraciones_llamadas_por_agente": {},
    "duraciones_nodos": {},
    "motivos_reparacion": {},
    "sublotes_central": [],
    "eventos_sublotes_central": [],
    "resumen_parcial_central": {},
    "eventos_sublotes_remotos": [],
    "resumen_parcial_remoto": {},
    "quality_input_prepared": {},
    "consolidacion_documental": {},
    "pipeline_downstream_agents": {},
}


def reiniciar_contadores() -> None:
    _CONTADORES["llamadas_ollama"] = 0
    _CONTADORES["llamadas_remotas"] = 0
    _CONTADORES["fallbacks_locales"] = 0
    _CONTADORES["reintentos"] = 0
    _CONTADORES["por_agente"] = {}
    _CONTADORES["duraciones_por_agente"] = {}
    _CONTADORES["duraciones_llamadas_por_agente"] = {}
    _CONTADORES["duraciones_nodos"] = {}
    _CONTADORES["motivos_reparacion"] = {}
    _CONTADORES["sublotes_central"] = []
    _CONTADORES["eventos_sublotes_central"] = []
    _CONTADORES["resumen_parcial_central"] = {}
    _CONTADORES["eventos_sublotes_remotos"] = []
    _CONTADORES["resumen_parcial_remoto"] = {}
    _CONTADORES["quality_input_prepared"] = {}
    _CONTADORES["consolidacion_documental"] = {}
    _CONTADORES["pipeline_downstream_agents"] = {}


def obtener_contadores() -> Dict[str, Any]:
    return {
        "llamadas_ollama": _CONTADORES["llamadas_ollama"],
        "llamadas_remotas": _CONTADORES["llamadas_remotas"],
        "fallbacks_locales": _CONTADORES["fallbacks_locales"],
        "reintentos": _CONTADORES["reintentos"],
        "por_agente": dict(_CONTADORES["por_agente"]),
        "duraciones_por_agente": dict(_CONTADORES["duraciones_por_agente"]),
        "duraciones_llamadas_por_agente": {
            agent: list(values)
            for agent, values in _CONTADORES["duraciones_llamadas_por_agente"].items()
        },
        "duraciones_nodos": dict(_CONTADORES["duraciones_nodos"]),
        "motivos_reparacion": {
            agent: list(values) for agent, values in _CONTADORES["motivos_reparacion"].items()
        },
        "sublotes_central": list(_CONTADORES["sublotes_central"]),
        "eventos_sublotes_central": list(_CONTADORES["eventos_sublotes_central"]),
        "resumen_parcial_central": dict(_CONTADORES["resumen_parcial_central"]),
        "eventos_sublotes_remotos": list(_CONTADORES["eventos_sublotes_remotos"]),
        "resumen_parcial_remoto": dict(_CONTADORES["resumen_parcial_remoto"]),
        "quality_input_prepared": dict(_CONTADORES["quality_input_prepared"]),
        "consolidacion_documental": {
            iid: dict(value) for iid, value in _CONTADORES["consolidacion_documental"].items()
        },
        "central_downstream_snapshot": bool(
            _CONTADORES["resumen_parcial_central"].get("downstream_agents_executed", False)
        ),
        "pipeline_downstream_agents": dict(_CONTADORES["pipeline_downstream_agents"]),
        "pipeline_downstream_agents_executed": all(
            _CONTADORES["pipeline_downstream_agents"].get(agent, False)
            for agent in ("Quality", "Security", "Evaluator")
        ),
    }


def _tamano_texto(value: Any) -> Dict[str, int]:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)

    return {
        "chars": len(text),
        "bytes_utf8": len(text.encode("utf-8")),
        "tokens_aprox": round(len(text) / 4) if text else 0,
    }


def _tamano_json(value: Any) -> Dict[str, Optional[int]]:
    if not isinstance(value, str):
        return {"json_chars": None, "json_bytes_utf8": None}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"json_chars": None, "json_bytes_utf8": None}

    normalized = json.dumps(parsed, ensure_ascii=False)
    return {
        "json_chars": len(normalized),
        "json_bytes_utf8": len(normalized.encode("utf-8")),
    }


def parametros_ollama(json_mode: bool = True, num_predict: int = 500, num_ctx: int = 4096, temperature: float = 0.1, keep_alive: str = "30m") -> Dict[str, Any]:
    params = {
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
        "keep_alive": keep_alive
    }
    if json_mode:
        params["format"] = "json"
    return params


def registrar_evento_grafo(event: str, agent: str, **extra: Any) -> None:
    if event == "agent_retry":
        _CONTADORES["reintentos"] += 1
    if event == "node_end" and isinstance(extra.get("elapsed_seconds"), (int, float)):
        _CONTADORES["duraciones_nodos"][agent] = round(float(extra["elapsed_seconds"]), 4)
    if event == "quality_input_prepared":
        _CONTADORES["quality_input_prepared"] = dict(extra)
    if event == "node_end" and agent in {"Quality", "Security", "Evaluator"}:
        _CONTADORES["pipeline_downstream_agents"][agent] = True
    payload = {
        "event": event,
        "agent": agent,
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        **extra,
    }
    logger.info("PERF_AUDIT %s", json.dumps(payload, ensure_ascii=False))


def registrar_evento_sublote_remoto(event: str, agent: str, **data: Any) -> None:
    allowed = {
        "sub_batch", "issue_ids", "expected", "received", "missing",
        "max_completion_tokens", "started_at", "elapsed_seconds", "finish_reason",
        "json_valid", "json_recovered", "status", "error_category", "http_status",
        "retry_after_seconds",
        "expected_issue_ids", "received_issue_ids", "failed_validator",
        "missing_fields", "invalid_types", "premature_fields",
        "empty_but_valid_fields", "alias_fields_detected", "contract_stage",
        "identity_validation", "contract_validation",
        "semantic_validation", "semantic_error_category", "semantic_by_issue",
        "failed_semantic_rule", "semantic_subcategory", "failed_issue_iid",
        "pending_semantic_validation", "stage_reached",
        "security_llm_raw_diagnostic", "security_normalized_summary",
    }
    payload = {key: value for key, value in data.items() if key in allowed}
    entry = {"event": event, "agent": agent, **payload}
    _CONTADORES["eventos_sublotes_remotos"].append(entry)
    partial = _CONTADORES["resumen_parcial_remoto"]
    partial["active_agent"] = agent
    partial["active_sub_batch"] = payload.get("sub_batch")
    partial["completed_issue_ids"] = list(dict.fromkeys(
        iid for item in _CONTADORES["eventos_sublotes_remotos"]
        if item["event"] == "remote_sub_batch_call_end" and item.get("status") == "success"
        for iid in item.get("received", [])
    ))
    if event == "remote_sub_batch_end" and payload.get("status") == "success":
        partial["active_sub_batch"] = None
    if event in {"remote_sub_batch_error", "remote_sub_batch_end"} and payload.get("status") in {"failed", "interrupted"}:
        partial.update({
            "last_error": payload.get("error_category"),
            "http_status": payload.get("http_status"),
            "retry_after_seconds": payload.get("retry_after_seconds"),
            "finish_reason": payload.get("finish_reason"),
        })
    registrar_evento_grafo(event, agent, **payload)


def registrar_motivo_reparacion(
    agent: str, issue_ids: list[int], reason: str,
) -> None:
    """Registra sólo identidad y motivo técnico; nunca la respuesta del modelo."""
    entry = {"issue_ids": list(issue_ids), "motivo": reason}
    entries = _CONTADORES["motivos_reparacion"].setdefault(agent, [])
    if entry not in entries:
        entries.append(entry)
    registrar_evento_grafo("selective_repair", agent, **entry)


def registrar_integridad_central(
    expected_issue_ids: list[int], received_issue_ids: list[int],
    *, failed_sub_batches: list[int] | None = None,
    selective_repairs_attempted: int = 0,
    selective_repairs_completed: int = 0,
) -> None:
    """Cierra la auditoría de Central usando exclusivamente expected - received."""
    expected = list(dict.fromkeys(int(iid) for iid in expected_issue_ids))
    received_set = {int(iid) for iid in received_issue_ids}
    received = [iid for iid in expected if iid in received_set]
    missing = [iid for iid in expected if iid not in received_set]
    _CONTADORES["resumen_parcial_central"].update({
        "expected": expected,
        "received": received,
        "missing": missing,
        "incomplete": list(missing),
        "failed_sub_batches": list(failed_sub_batches or []),
        "selective_repairs_attempted": int(selective_repairs_attempted),
        "selective_repairs_completed": int(selective_repairs_completed),
        "status": "failed" if missing else "success",
        "stage_reached": "central_validation",
        "downstream_agents_executed": False,
        "documents_generated": False,
        "active_sub_batch": None,
    })


def registrar_consolidacion_documental(issue_iid: int, diagnostic: Dict[str, Any]) -> None:
    """Registra sólo cantidades de consolidación; nunca textos documentales."""
    allowed = {
        "requirements_before_document_dedup", "requirements_after_document_dedup",
        "rf_before", "rf_after", "rnf_before", "rnf_after",
        "equivalent_rf_merged", "equivalent_rnf_merged",
    }
    _CONTADORES["consolidacion_documental"][int(issue_iid)] = {
        key: diagnostic.get(key) for key in allowed
    }


def registrar_sublote_central(record: Dict[str, Any]) -> None:
    """Conserva auditoría estructural del sublote sin prompts ni respuestas."""
    sanitized = dict(record)
    _CONTADORES["sublotes_central"].append(sanitized)


def registrar_evento_sublote_central(event: str, **data: Any) -> None:
    """Persiste de inmediato eventos sanitizados y actualiza el resumen parcial."""
    allowed = {
        "sub_batch", "split_level", "issue_ids", "call_type", "attempt",
        "num_predict", "started_at", "elapsed_seconds", "status",
        "error_category", "received", "missing",
    }
    payload = {key: value for key, value in data.items() if key in allowed}
    entry = {"event": event, **payload}
    _CONTADORES["eventos_sublotes_central"].append(entry)
    partial = _CONTADORES["resumen_parcial_central"]
    partial["sub_batches_started"] = sum(
        item["event"] == "central_sub_batch_start"
        for item in _CONTADORES["eventos_sublotes_central"]
    )
    partial["sub_batches_completed"] = sum(
        item["event"] == "central_sub_batch_end" and item.get("status") in {"success", "partial"}
        for item in _CONTADORES["eventos_sublotes_central"]
    )
    partial["calls_started"] = sum(
        item["event"] == "central_sub_batch_call_start"
        for item in _CONTADORES["eventos_sublotes_central"]
    )
    partial["calls_completed"] = sum(
        item["event"] == "central_sub_batch_call_end"
        for item in _CONTADORES["eventos_sublotes_central"]
    )
    ends = [
        item for item in _CONTADORES["eventos_sublotes_central"]
        if item["event"] == "central_sub_batch_end"
    ]
    starts = [
        item for item in _CONTADORES["eventos_sublotes_central"]
        if item["event"] == "central_sub_batch_start"
    ]
    partial["active_sub_batch"] = (
        starts[-1].get("sub_batch")
        if starts and (not ends or ends[-1].get("sub_batch") != starts[-1].get("sub_batch"))
        else None
    )
    timed_calls = [
        item for item in _CONTADORES["eventos_sublotes_central"]
        if item["event"] in {"central_sub_batch_call_end", "central_sub_batch_error"}
    ]
    partial["elapsed_seconds"] = round(
        sum(float(item.get("elapsed_seconds") or 0) for item in timed_calls), 4,
    )
    received = []
    for item in _CONTADORES["eventos_sublotes_central"]:
        if item["event"] == "central_sub_batch_call_end":
            received.extend(item.get("received") or [])
    partial["received"] = list(dict.fromkeys(received))
    if "missing" in payload:
        partial["missing"] = list(payload.get("missing") or [])
    if payload.get("error_category"):
        partial["last_error"] = payload["error_category"]
        partial["failed_sub_batch"] = payload.get("sub_batch")
        partial["active_sub_batch_at_failure"] = payload.get("sub_batch")
    registrar_evento_grafo(event, "Central_Init", **payload)


def registrar_fallback_local(agent: str, error_type: str, count_local_call: bool = True) -> None:
    _CONTADORES["fallbacks_locales"] += 1
    if count_local_call:
        _CONTADORES["llamadas_ollama"] += 1
    registrar_evento_grafo(
        "LLM_LOCAL_FALLBACK", agent, provider="ollama", error_type=error_type,
    )


@contextmanager
def auditar_llamada_agente(
    agent: str,
    prompt_text: str,
    context_text: str,
    input_json_text: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None,
    provider: str = "ollama",
):
    start = time.perf_counter()
    if provider == "groq":
        _CONTADORES["llamadas_remotas"] += 1
    else:
        _CONTADORES["llamadas_ollama"] += 1
    per_agent = _CONTADORES["por_agente"]
    per_agent[agent] = per_agent.get(agent, 0) + 1
    started_at = datetime.now().isoformat(timespec="milliseconds")
    params = model_params or parametros_ollama()
    effective_json_text = input_json_text if input_json_text is not None else context_text

    registrar_evento_grafo(
        "agent_start",
        agent,
        started_at=started_at,
        model=params.get("model"),
        provider=provider,
        model_params=params,
        prompt_size=_tamano_texto(prompt_text),
        context_size=_tamano_texto(context_text),
        input_json_size=_tamano_json(effective_json_text),
    )

    response_holder: Dict[str, Any] = {
        "response": "", "provider_used": provider, "model_used": params.get("model"),
    }
    try:
        yield response_holder
    finally:
        elapsed = time.perf_counter() - start
        rounded_elapsed = round(elapsed, 4)
        durations = _CONTADORES["duraciones_llamadas_por_agente"].setdefault(agent, [])
        durations.append(rounded_elapsed)
        _CONTADORES["duraciones_por_agente"][agent] = round(sum(durations), 4)
        finished_at = datetime.now().isoformat(timespec="milliseconds")
        response_text = response_holder.get("response", "")
        provider_used = response_holder.get("provider_used", provider)
        model_used = response_holder.get("model_used", params.get("model"))
        registrar_evento_grafo(
            "agent_end",
            agent,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(elapsed, 4),
            model=model_used,
            provider=provider_used,
            model_params=params,
            prompt_size=_tamano_texto(prompt_text),
            context_size=_tamano_texto(context_text),
            input_json_size=_tamano_json(effective_json_text),
            response_size=_tamano_texto(response_text),
            response_json_size=_tamano_json(response_text),
        )
