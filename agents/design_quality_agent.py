from langchain_core.prompts import PromptTemplate
from agents import cargar_prompt
from agents.llm_invocation import (
    RemoteLLMError, invocar_con_fallback, rechazar_respuesta_remota_truncada,
    registrar_resumen_respuesta,
)
from core.llm_factory import crear_llm_local, obtener_llm_para_agente
from core.config import OLLAMA_MODEL
from core.performance_audit import auditar_llamada_agente, parametros_ollama
from core.batch_contract import calcular_num_predict
import json
import logging
import os

logger = logging.getLogger(__name__)


def parametros_auditoria_calidad_diseno(selection, num_predict: int) -> dict:
    if selection.provider == "groq":
        return {
            "provider": "groq",
            "model": selection.model,
            "temperature": 0.1,
            "max_completion_tokens": int(os.getenv("REMOTE_QUALITY_MAX_COMPLETION_TOKENS", "2048")),
            "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
            "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden"),
        }
    return parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)


def analizar_calidad_diseno(
    resultado_central_json_str: str,
    contexto_json_str: str,
) -> str:
    """
    Agente de Calidad de Diseño: evalúa exclusivamente MC-03 (Completitud de
    la Descripción) y MC-04 (Acoplamiento de Componentes) a partir de la
    salida del Central de Diseño y la evidencia original del Issue.

    Reutiliza la configuración existente del rol Calidad (Groq): mismo
    LLM_PROVIDER_QUALITY, GROQ_MODEL_QUALITY y REMOTE_QUALITY_MAX_COMPLETION_TOKENS
    que Calidad de Requerimientos.

    No calcula porcentajes, no evalúa Seguridad, no modifica RF/RNF ni IDs ED.
    """
    parsed_central = json.loads(resultado_central_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_central["resultados"]]
    num_predict = calcular_num_predict("Quality", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "quality", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("design_quality_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "resultado_central_json_str": resultado_central_json_str,
        "contexto_json_str": contexto_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)

    params = parametros_auditoria_calidad_diseno(selection, num_predict)

    with auditar_llamada_agente(
        "Design_Quality_Batch",
        prompt_text=prompt_text,
        context_text=contexto_json_str,
        input_json_text=resultado_central_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        from core.remote_execution import REMOTE_PACER
        if selection.provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(selection.provider, "Quality")
        try:
            result = invocar_con_fallback(
                "Design_Quality", selection,
                lambda: chain.invoke(prompt_values),
                lambda: ((prompt | crear_llm_local(
                    json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
                )).invoke(prompt_values), OLLAMA_MODEL),
            )
        except RemoteLLMError as exc:
            exc.issue_ids = list(expected_issue_ids)
            raise
        finally:
            if selection.provider in ("groq", "nvidia"):
                REMOTE_PACER.after_call(selection.provider, "Quality")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Design_Quality", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Design_Quality", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
