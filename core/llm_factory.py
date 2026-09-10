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

    # Modelos de razonamiento (p. ej. deepseek-v4-flash) generan tokens de "thinking"
    # que disparan la latencia hasta el timeout con prompts reales (~190 s → timeout).
    # Desactivarlo entrega JSON directo y baja la latencia a ~10 s. Es un campo no
    # estándar que NVIDIA NIM acepta en el cuerpo de la petición vía extra_body.
    if _env_bool("NVIDIA_DISABLE_THINKING", False):
        kwargs["extra_body"] = {"chat_template_kwargs": {"thinking": False}}

    # nemotron (etapa de Codificación) solo emite JSON estructuralmente válido de forma
    # fiable con decodificación guiada (response_format); sin ella devuelve JSON roto de
    # vez en cuando. Se aplica SOLO a nemotron: deepseek ya entrega JSON limpio y con
    # response_format su latencia supera el timeout del gateway gratuito.
    if json_mode and "nemotron" in model_name.lower():
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

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
    original_agent = agent
    if agent in {"design_central", "coding_central", "testing_central"}:
        # Arranca mapeado al mismo provider/modelo del Central de Requerimientos.
        agent = "central"
    elif agent == "coding_evaluator":
        # Comparte gate/provider con "evaluator", pero puede usar un modelo propio
        # (el de la etapa de Codificación) para evitar los timeouts de deepseek.
        agent = "evaluator"

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
            "deepseek-ai/deepseek-v4-flash-0731",
        ).strip()

        # Override por etapa: Coding_Central usa un modelo propio (más rápido) porque
        # su prompt incluye el código fuente (~20k tokens) y el endpoint gratuito de
        # NVIDIA agota su gateway (~300 s) generando con modelos grandes. Si no se
        # define NVIDIA_MODEL_CODING_CENTRAL, hereda NVIDIA_MODEL_CENTRAL.
        if original_agent == "coding_central":
            model = os.getenv("NVIDIA_MODEL_CODING_CENTRAL", model).strip() or model

        # El Evaluador de Codificación hereda el modelo de la etapa de Codificación
        # (NVIDIA_MODEL_CODING_CENTRAL, p. ej. nemotron) porque deepseek se atasca en el
        # gateway gratuito incluso con prompts pequeños. Se puede fijar aparte con
        # NVIDIA_MODEL_CODING_EVALUATOR si algún día se quiere un modelo distinto.
        elif original_agent == "coding_evaluator":
            model = os.getenv(
                "NVIDIA_MODEL_CODING_EVALUATOR",
                os.getenv("NVIDIA_MODEL_CODING_CENTRAL", model),
            ).strip() or model

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
