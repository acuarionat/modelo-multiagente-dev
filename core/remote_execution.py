"""Controles técnicos localizados para llamadas remotas secuenciales."""

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable

from core.performance_audit import registrar_evento_grafo

logger = logging.getLogger(__name__)


def _env_int_tolerante(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    try:
        value = int(str(raw).strip())
        if value < minimum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        if raw not in (None, ""):
            logger.warning("REMOTE_CONFIG_DEFAULT name=%s default=%s", name, default)
        return default


def _env_float_tolerante(name: str, default: float, minimum: float = 0) -> float:
    raw = os.getenv(name)
    try:
        value = float(str(raw).strip())
        if value < minimum:
            raise ValueError
        return value
    except (TypeError, ValueError):
        if raw not in (None, ""):
            logger.warning("REMOTE_CONFIG_DEFAULT name=%s default=%s", name, default)
        return default


def remote_batch_size(agent: str) -> int:
    return _env_int_tolerante(f"REMOTE_{agent.upper()}_BATCH_SIZE", 2)


def remote_inter_call_delay(provider: str | None = None) -> float:
    if provider:
        suffix = provider.upper()
        env_name = f"REMOTE_INTER_CALL_DELAY_SECONDS_{suffix}"
        raw = os.getenv(env_name)
        if raw is not None:
            return _env_float_tolerante(env_name, 60.0)
    return _env_float_tolerante("REMOTE_INTER_CALL_DELAY_SECONDS", 60.0)


def remote_enabled_for(agent: str) -> bool:
    enabled = os.getenv("ENABLE_REMOTE_LLM", "false").strip().casefold() in {"1", "true", "yes", "si", "sí"}
    provider = os.getenv(f"LLM_PROVIDER_{agent.upper()}", "ollama").strip().casefold()
    return enabled and provider == "groq"


@contextmanager
def remote_single_attempt():
    """Fuerza una sola llamada remota, sin reintento interno ni fallback."""
    forced = {
        "REMOTE_LLM_MAX_RETRIES": "0",
        "ENABLE_LOCAL_FALLBACK": "false",
    }
    previous = {name: os.environ.get(name) for name in forced}
    os.environ.update(forced)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def dividir_payload_en_sublotes(payload: dict[str, Any], batch_size: int) -> list[dict[str, Any]]:
    results = payload.get("resultados") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ValueError("El payload remoto no contiene resultados.")
    return [
        {**{key: value for key, value in payload.items() if key != "resultados"}, "resultados": results[index:index + batch_size]}
        for index in range(0, len(results), batch_size)
    ]


class RemoteBatchError(RuntimeError):
    def __init__(
        self, category: str, *, agent: str, sub_batch: int, issue_ids: list[int],
        received: list[int] | None = None, contract_diagnostic: dict[str, Any] | None = None,
        semantic_diagnostic: dict[str, Any] | None = None,
    ):
        super().__init__(category)
        self.category = category
        self.agent = agent
        self.sub_batch = sub_batch
        self.issue_ids = list(issue_ids)
        self.received = list(received or [])
        self.contract_diagnostic = dict(contract_diagnostic or {})
        self.semantic_diagnostic = dict(semantic_diagnostic or {})


def validar_sublote_estricto(
    parsed: dict[str, Any], expected: list[int], *, agent: str, sub_batch: int,
) -> list[dict[str, Any]]:
    results = parsed.get("resultados") if isinstance(parsed, dict) else None
    if not isinstance(results, list):
        raise RemoteBatchError("REMOTE_CONTRACT_ERROR", agent=agent, sub_batch=sub_batch, issue_ids=expected)
    received: list[int] = []
    indexed: dict[int, dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict):
            raise RemoteBatchError("REMOTE_CONTRACT_ERROR", agent=agent, sub_batch=sub_batch, issue_ids=expected)
        try:
            iid = int(item.get("issue_iid"))
        except (TypeError, ValueError) as exc:
            raise RemoteBatchError("REMOTE_CONTRACT_ERROR", agent=agent, sub_batch=sub_batch, issue_ids=expected) from exc
        if iid in indexed:
            raise RemoteBatchError("REMOTE_DUPLICATE_ISSUE", agent=agent, sub_batch=sub_batch, issue_ids=expected)
        if iid not in expected:
            raise RemoteBatchError("REMOTE_UNEXPECTED_ISSUE", agent=agent, sub_batch=sub_batch, issue_ids=expected)
        received.append(iid)
        indexed[iid] = item
    if set(received) != set(expected):
        raise RemoteBatchError("REMOTE_INCOMPLETE_BATCH", agent=agent, sub_batch=sub_batch, issue_ids=expected)
    return [indexed[iid] for iid in expected]


@dataclass
class RemotePacer:
    clock: Callable[[], float] = time.monotonic
    sleeper: Callable[[float], None] = time.sleep
    last_end: float | None = None
    last_agent: str | None = None
    last_provider: str | None = None

    def reset(self) -> None:
        self.last_end = None
        self.last_agent = None
        self.last_provider = None

    def before_call(self, provider: str, agent: str) -> float:
        waited = 0.0
        if self.last_end is not None and self.last_provider == provider:
            configured = remote_inter_call_delay(provider)
            elapsed = max(0.0, self.clock() - self.last_end)
            waited = max(0.0, configured - elapsed)
            registrar_evento_grafo(
                "remote_rate_pacing", agent,
                provider=provider, previous_agent=self.last_agent, next_agent=agent,
                configured_seconds=configured, elapsed_seconds=round(elapsed, 4),
                waited_seconds=round(waited, 4), reason="remote_rate_pacing",
            )
            if waited > 0:
                self.sleeper(waited)
        return waited

    def after_call(self, provider: str, agent: str) -> None:
        self.last_end = self.clock()
        self.last_agent = agent
        self.last_provider = provider


REMOTE_PACER = RemotePacer()


def reiniciar_pacing_remoto() -> None:
    REMOTE_PACER.reset()


def _is_rate_limit_error(exc: Exception) -> bool:
    for attr in ("status_code", "http_status"):
        status = getattr(exc, attr, None)
        if status == 429:
            return True
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    name = type(exc).__name__.casefold()
    category = getattr(exc, "category", "")
    return "ratelimit" in name or "rate_limit" in name or category == "REMOTE_RATE_LIMIT"




def _rate_limit_retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        value = float(raw)
        return value if 0 < value <= 300 else None
    except (TypeError, ValueError):
        return None


def reintentar_con_backoff(
    fn: Callable[[], Any],
    *,
    agent: str,
    max_retries: int = 3,
    base_delay: float = 30.0,
    max_delay: float = 120.0,
) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= max_retries:
                raise
            retry_after = _rate_limit_retry_after(exc)
            delay = retry_after or min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "RATE_LIMIT_RETRY agent=%s attempt=%d/%d delay=%.1fs",
                agent, attempt + 1, max_retries, delay,
            )
            registrar_evento_grafo(
                "rate_limit_retry", agent,
                attempt=attempt + 1, max_retries=max_retries,
                delay_seconds=round(delay, 1),
                retry_after_header=retry_after,
            )
            time.sleep(delay)
