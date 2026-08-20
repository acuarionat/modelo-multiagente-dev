from langchain_core.prompts import PromptTemplate
from agents import cargar_prompt
from agents.llm_invocation import (
    RemoteLLMError, invocar_con_fallback, rechazar_respuesta_remota_truncada,
    registrar_resumen_respuesta,
)
from core.llm_factory import crear_llm_local, obtener_llm_para_agente
from core.config import OLLAMA_MODEL
from core.performance_audit import auditar_llamada_agente
from core.batch_contract import calcular_num_predict
import json
import logging
import os

logger = logging.getLogger(__name__)


def parametros_auditoria_seguridad(selection, num_predict):
    from core.performance_audit import parametros_ollama
    if selection.provider == "ollama":
        return parametros_ollama(
            json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
        )
    return {
        "provider": "groq", "model": selection.model, "temperature": 0.1,
        "max_completion_tokens": int(os.getenv("REMOTE_SECURITY_MAX_COMPLETION_TOKENS", "2048")),
        "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
        "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden"),
    }

def analizar_seguridad(
    issues_json_str: str,
    num_predict_override: int | None = None,
    sub_batch: int | None = None,
) -> str:
    """
    Agente de Seguridad: Evalúa el lote de requerimientos estructurados.
    Devuelve un JSON Array.
    """
    # Evaluamos el texto en modo JSON
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input["resultados"]]
    num_predict = num_predict_override or calcular_num_predict("Security", len(expected_issue_ids))
    selection = obtener_llm_para_agente(
        "security", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("security_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "issues_json_str": issues_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)
    
    params = parametros_auditoria_seguridad(selection, num_predict)
    
    with auditar_llamada_agente(
        "Security_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        from core.remote_execution import REMOTE_PACER
        if selection.provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(selection.provider, "Security")
        try:
            result = invocar_con_fallback(
                "Security", selection,
                lambda: chain.invoke(prompt_values),
                lambda: ((prompt | crear_llm_local(
                    json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
                )).invoke(prompt_values), OLLAMA_MODEL),
            )
        except RemoteLLMError as exc:
            exc.sub_batch = sub_batch
            exc.issue_ids = list(expected_issue_ids)
            raise
        finally:
            if selection.provider in ("groq", "nvidia"):
                REMOTE_PACER.after_call(selection.provider, "Security")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Security", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Security", result=result, metadata=metadata,
            sub_batch=sub_batch, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )
    
    return response.content
