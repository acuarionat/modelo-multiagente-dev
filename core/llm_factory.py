import logging
import os
from dataclasses import dataclass
from typing import Any

from langchain_ollama import ChatOllama

from core.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from core.performance_audit import registrar_evento_grafo, registrar_fallback_local

logger = logging.getLogger(__name__)


class LLMConfigurationError(RuntimeError):
    """Configuración inválida sin exponer valores sensibles."""


@dataclass(frozen=True)
class LLMSelection:
    llm: Any
    provider: str
    model: str
    fallback_enabled: bool


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "si", "sí"}


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} debe ser un entero positivo.") from exc
    if value <= 0:
        raise LLMConfigurationError(f"{name} debe ser un entero positivo.")
    return value


def crear_llm_local(
    json_mode: bool = False, num_predict: int = 500, num_ctx: int = 4096,
    temperature: float = 0.1, keep_alive: str = "30m",
) -> ChatOllama:
    kwargs = {
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
        "keep_alive": keep_alive,
    }
    if json_mode:
        kwargs["format"] = "json"
    return ChatOllama(**kwargs)


def crear_llm_groq(
    model_name: str, max_completion_tokens: int, json_mode: bool = False,
):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise LLMConfigurationError("GROQ_API_KEY no está configurada.")
    if not model_name:
        raise LLMConfigurationError("No se configuró el modelo remoto.")
    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise LLMConfigurationError("langchain-groq no está instalado.") from exc
    kwargs = {
        "api_key": api_key,
        "model": model_name,
        "temperature": 0,
        "timeout": float(os.getenv("REMOTE_LLM_TIMEOUT_SECONDS", "120")),
        "max_retries": int(os.getenv("REMOTE_LLM_MAX_RETRIES", "1")),
        "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low").strip() or "low",
        "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden").strip() or "hidden",
        "model_kwargs": {"max_completion_tokens": max_completion_tokens},
    }
    if json_mode:
        kwargs["model_kwargs"]["response_format"] = {"type": "json_object"}
    return ChatGroq(**kwargs)



def crear_llm_nvidia(
    model_name: str,
    max_completion_tokens: int,
    json_mode: bool = False,
):
    """
    Crea un cliente LangChain para NVIDIA NIM mediante su API
    compatible con OpenAI.

    No expone la API key en logs ni excepciones.
    """
    api_key = os.getenv("NVIDIA_API_KEY", "").strip()

    if not api_key:
        raise LLMConfigurationError(
            "NVIDIA_API_KEY no está configurada."
        )

    if not model_name:
        raise LLMConfigurationError(
            "No se configuró el modelo NVIDIA."
        )

    base_url = os.getenv(
        "NVIDIA_BASE_URL",
        "https://integrate.api.nvidia.com/v1",
    ).strip()

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise LLMConfigurationError(
            "langchain-openai no está instalado."
        ) from exc

    try:
        timeout = float(
            os.getenv(
                "NVIDIA_LLM_TIMEOUT_SECONDS",
                "180",
            )
        )
    except ValueError:
        timeout = 180.0

    try:
        max_retries = int(
            os.getenv(
                "NVIDIA_LLM_MAX_RETRIES",
                "0",
            )
        )
    except ValueError:
        max_retries = 0

    if max_retries < 0:
        max_retries = 0

    try:
        temperature = float(
            os.getenv(
                "NVIDIA_CENTRAL_TEMPERATURE",
                "0.1",
            )
        )
    except ValueError:
        temperature = 0.1

    try:
        top_p = float(
            os.getenv(
                "NVIDIA_CENTRAL_TOP_P",
                "1",
            )
        )
    except ValueError:
        top_p = 1.0

    kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model_name,
        "temperature": temperature,
        "top_p": top_p,
        "timeout": timeout,
        "max_retries": max_retries,
        "max_tokens": max_completion_tokens,
    }

    return ChatOpenAI(**kwargs)

def obtener_llm_para_agente(
    agent_name: str,
    json_mode: bool = False,
    num_predict: int = 500,
    num_ctx: int = 4096,
    temperature: float = 0.1,
    keep_alive: str = "30m",
) -> LLMSelection:

    agent = agent_name.strip().casefold()
    if agent in {"design_central", "coding_central"}:
        # Arranca mapeado al mismo provider/modelo del Central de Requerimientos.
        agent = "central"

    fallback_enabled = _env_bool(
        "ENABLE_LOCAL_FALLBACK",
        True,
    )

    remote_enabled = _env_bool(
        "ENABLE_REMOTE_LLM",
        False,
    )

    provider = os.getenv(
        f"LLM_PROVIDER_{agent.upper()}",
        "ollama",
    ).strip().casefold()

    # =====================================================
    # NVIDIA
    # =====================================================

    if (
        agent in {"central", "evaluator"}
        and remote_enabled
        and provider == "nvidia"
    ):
        model = os.getenv(
            "NVIDIA_MODEL_CENTRAL",
            "z-ai/glm-5.2",
        ).strip()

        max_completion_tokens = _env_positive_int(
            "NVIDIA_CENTRAL_MAX_COMPLETION_TOKENS",
            4096,
        )

        try:
            llm = crear_llm_nvidia(
                model,
                max_completion_tokens,
                json_mode,
            )

        except LLMConfigurationError as exc:
            if not fallback_enabled:
                raise

            logger.warning(
                "REMOTE_CONFIG_ERROR "
                "agent=%s provider=nvidia "
                "fallback=ollama error=%s",
                agent_name,
                type(exc).__name__,
            )

            registrar_fallback_local(
                agent_name,
                "REMOTE_CONFIG_ERROR",
                count_local_call=False,
            )

        else:
            registrar_evento_grafo(
                "LLM_PROVIDER_SELECTED",
                agent_name,
                provider="nvidia",
                model=model,
            )

            return LLMSelection(
                llm=llm,
                provider="nvidia",
                model=model,
                fallback_enabled=fallback_enabled,
            )

    # =====================================================
    # GROQ
    # =====================================================

    if (
        agent in {"quality", "security"}
        and remote_enabled
        and provider == "groq"
    ):
        model = os.getenv(
            f"GROQ_MODEL_{agent.upper()}",
            "",
        ).strip()

        max_completion_tokens = _env_positive_int(
            f"REMOTE_{agent.upper()}_MAX_COMPLETION_TOKENS",
            2048,
        )

        try:
            llm = crear_llm_groq(
                model,
                max_completion_tokens,
                json_mode,
            )

        except LLMConfigurationError as exc:
            if not fallback_enabled:
                raise

            logger.warning(
                "REMOTE_CONFIG_ERROR "
                "agent=%s provider=groq "
                "fallback=ollama error=%s",
                agent_name,
                type(exc).__name__,
            )

            registrar_fallback_local(
                agent_name,
                "REMOTE_CONFIG_ERROR",
                count_local_call=False,
            )

        else:
            registrar_evento_grafo(
                "LLM_PROVIDER_SELECTED",
                agent_name,
                provider="groq",
                model=model,
            )

            return LLMSelection(
                llm=llm,
                provider="groq",
                model=model,
                fallback_enabled=fallback_enabled,
            )

    # =====================================================
    # OLLAMA
    # =====================================================

    llm = crear_llm_local(
        json_mode,
        num_predict,
        num_ctx,
        temperature,
        keep_alive,
    )

    registrar_evento_grafo(
        "LLM_PROVIDER_SELECTED",
        agent_name,
        provider="ollama",
        model=OLLAMA_MODEL,
    )

    return LLMSelection(
        llm=llm,
        provider="ollama",
        model=OLLAMA_MODEL,
        fallback_enabled=fallback_enabled,
    )
