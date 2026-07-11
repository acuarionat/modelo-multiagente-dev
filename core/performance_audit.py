import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger("performance_audit")


def _text_size(value: Any) -> Dict[str, int]:
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


def _json_size(value: Any) -> Dict[str, Optional[int]]:
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


def ollama_params(json_mode: bool = True) -> Dict[str, Any]:
    params = {
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "temperature": 0.2,
    }
    if json_mode:
        params["format"] = "json"
    return params


def log_graph_event(event: str, agent: str, **extra: Any) -> None:
    payload = {
        "event": event,
        "agent": agent,
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        **extra,
    }
    logger.info("PERF_AUDIT %s", json.dumps(payload, ensure_ascii=False))


@contextmanager
def audit_agent_call(
    agent: str,
    prompt_text: str,
    context_text: str,
    input_json_text: Optional[str] = None,
    json_mode: bool = True,
):
    start = time.perf_counter()
    started_at = datetime.now().isoformat(timespec="milliseconds")
    params = ollama_params(json_mode=json_mode)
    effective_json_text = input_json_text if input_json_text is not None else context_text

    log_graph_event(
        "agent_start",
        agent,
        started_at=started_at,
        model=params.get("model"),
        model_params=params,
        prompt_size=_text_size(prompt_text),
        context_size=_text_size(context_text),
        input_json_size=_json_size(effective_json_text),
    )

    response_holder: Dict[str, Any] = {"response": ""}
    try:
        yield response_holder
    finally:
        elapsed = time.perf_counter() - start
        finished_at = datetime.now().isoformat(timespec="milliseconds")
        response_text = response_holder.get("response", "")
        log_graph_event(
            "agent_end",
            agent,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(elapsed, 4),
            model=params.get("model"),
            model_params=params,
            prompt_size=_text_size(prompt_text),
            context_size=_text_size(context_text),
            input_json_size=_json_size(effective_json_text),
            response_size=_text_size(response_text),
            response_json_size=_json_size(response_text),
        )
