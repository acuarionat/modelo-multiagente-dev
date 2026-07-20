import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger("performance_audit")


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
    payload = {
        "event": event,
        "agent": agent,
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        **extra,
    }
    logger.info("PERF_AUDIT %s", json.dumps(payload, ensure_ascii=False))


@contextmanager
def auditar_llamada_agente(
    agent: str,
    prompt_text: str,
    context_text: str,
    input_json_text: Optional[str] = None,
    model_params: Optional[Dict[str, Any]] = None,
):
    start = time.perf_counter()
    started_at = datetime.now().isoformat(timespec="milliseconds")
    params = model_params or parametros_ollama()
    effective_json_text = input_json_text if input_json_text is not None else context_text

    registrar_evento_grafo(
        "agent_start",
        agent,
        started_at=started_at,
        model=params.get("model"),
        model_params=params,
        prompt_size=_tamano_texto(prompt_text),
        context_size=_tamano_texto(context_text),
        input_json_size=_tamano_json(effective_json_text),
    )

    response_holder: Dict[str, Any] = {"response": ""}
    try:
        yield response_holder
    finally:
        elapsed = time.perf_counter() - start
        finished_at = datetime.now().isoformat(timespec="milliseconds")
        response_text = response_holder.get("response", "")
        registrar_evento_grafo(
            "agent_end",
            agent,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(elapsed, 4),
            model=params.get("model"),
            model_params=params,
            prompt_size=_tamano_texto(prompt_text),
            context_size=_tamano_texto(context_text),
            input_json_size=_tamano_json(effective_json_text),
            response_size=_tamano_texto(response_text),
            response_json_size=_tamano_json(response_text),
        )
