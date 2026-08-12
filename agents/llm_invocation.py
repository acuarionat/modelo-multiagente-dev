import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from core.llm_factory import LLMSelection
from core.performance_audit import registrar_fallback_local

logger = logging.getLogger(__name__)
_LAST_RESPONSE_METADATA: dict[str, dict[str, Any]] = {}


class RemoteLLMError(RuntimeError):
    """Error remoto controlado sin detalles potencialmente sensibles."""

    def __init__(
        self, category: str, *, http_status: int | None = None,
        retry_after_seconds: float | None = None, provider: str = "groq",
        agent: str | None = None, sub_batch: int | None = None,
        issue_ids: list[int] | None = None, finish_reason: str | None = None,
        max_completion_tokens: int | None = None, response_chars: int | None = None,
        model: str | None = None,
    ):
        super().__init__(category)
        self.category = category
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds
        self.provider = provider
        self.agent = agent
        self.sub_batch = sub_batch
        self.issue_ids = list(issue_ids or [])
        self.finish_reason = finish_reason
        self.max_completion_tokens = max_completion_tokens
        self.response_chars = response_chars
        self.model = model


@dataclass(frozen=True)
class InvocationResult:
    response: Any
    provider: str
    model: str
    used_fallback: bool = False


def normalizar_json_llm(texto: str) -> str:
    """
    Normalización sintáctica MÍNIMA de una respuesta de LLM antes de
    json.loads(): solo quita fences Markdown (```json ... ``` o ``` ... ```)
    que no forman parte del JSON. NO repara JSON roto, NO agrega llaves,
    NO elimina comas: si el contenido no es JSON válido después de esto,
    debe seguir fallando en json.loads().
    """
    valor = str(texto or "").strip()
    if valor.startswith("```json"):
        valor = valor[len("```json"):].strip()
    elif valor.startswith("```"):
        valor = valor[3:].strip()
    if valor.endswith("```"):
        valor = valor[:-3].strip()
    return valor


def registrar_resumen_respuesta(
    agent_name: str, result: InvocationResult, content: str,
) -> dict[str, Any]:
    valid_json = False
    keys = []
    try:
        parsed = json.loads(normalizar_json_llm(content))
        valid_json = True
        keys = sorted(parsed) if isinstance(parsed, dict) else []
    except (TypeError, json.JSONDecodeError):
        pass
    response_metadata = getattr(result.response, "response_metadata", {})
    response_metadata = response_metadata if isinstance(response_metadata, dict) else {}
    finish_reason = response_metadata.get("finish_reason")
    reported_model = response_metadata.get("model_name") or result.model
    _LAST_RESPONSE_METADATA[agent_name.casefold()] = {
        "provider": result.provider,
        "model": reported_model,
        "finish_reason": finish_reason,
        "fallback": result.used_fallback,
        "response_chars": len(content) if isinstance(content, str) else 0,
    }
    logger.info(
        "LLM_RESPONSE_METADATA agent=%s provider=%s model=%s fallback=%s "
        "chars=%s json_valid=%s keys=%s finish_reason=%s",
        agent_name, result.provider, reported_model, result.used_fallback,
        len(content) if isinstance(content, str) else 0, valid_json, keys,
        finish_reason,
    )
    return dict(_LAST_RESPONSE_METADATA[agent_name.casefold()])


def rechazar_respuesta_remota_truncada(
    *, agent_name: str, result: InvocationResult, metadata: dict[str, Any],
    sub_batch: int | None, issue_ids: list[int], max_completion_tokens: int,
) -> None:
    if result.provider == "groq" and metadata.get("finish_reason") == "length":
        raise RemoteLLMError(
            "REMOTE_TRUNCATED_RESPONSE", provider=result.provider, agent=agent_name,
            sub_batch=sub_batch, issue_ids=issue_ids, finish_reason="length",
            max_completion_tokens=max_completion_tokens,
            response_chars=metadata.get("response_chars"), model=result.model,
        )


def obtener_ultimos_metadatos(agent_name: str) -> dict[str, Any]:
    return dict(_LAST_RESPONSE_METADATA.get(agent_name.casefold(), {}))


def clasificar_error_remoto(exc: Exception) -> str | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    name = type(exc).__name__.casefold()
    if status in {401, 403} or "authentication" in name or "permission" in name:
        return "REMOTE_AUTH_ERROR"
    if status == 404 or "notfound" in name or "not_found" in name:
        return "REMOTE_CONFIG_ERROR"
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return "REMOTE_RATE_LIMIT"
    if status == 408 or "timeout" in name:
        return "REMOTE_TIMEOUT"
    if status in {498, 500, 502, 503} or any(marker in name for marker in (
        "connection", "serviceunavailable", "internalserver",
    )):
        return "REMOTE_SERVICE_ERROR"
    return None


def _retry_after_sanitizado(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        value = float(raw)
        return value if value >= 0 else None
    except (TypeError, ValueError):
        return None


def invocar_con_fallback(
    agent_name: str,
    selection: LLMSelection,
    invoke_selected: Callable[[], Any],
    invoke_local: Callable[[], tuple[Any, str]],
) -> InvocationResult:
    try:
        return InvocationResult(
            invoke_selected(), selection.provider, selection.model, False,
        )
    except Exception as exc:
        error_type = clasificar_error_remoto(exc)
        if selection.provider != "groq" or error_type is None:
            raise
        logger.warning(
            "REMOTE_LLM_ERROR agent=%s error=%s fallback=%s",
            agent_name, error_type, selection.fallback_enabled,
        )
        if not selection.fallback_enabled:
            status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
            raise RemoteLLMError(
                error_type, http_status=status, retry_after_seconds=_retry_after_sanitizado(exc),
                provider=selection.provider, agent=agent_name,
            ) from exc
        registrar_fallback_local(agent_name, error_type)
        response, local_model = invoke_local()
        return InvocationResult(response, "ollama", local_model, True)
