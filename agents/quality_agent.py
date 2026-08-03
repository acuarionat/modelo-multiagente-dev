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

def analizar_calidad(
    issues_json_str: str, num_predict_override: int | None = None,
    sub_batch: int | None = None,
) -> str:
    """
    Agente de Calidad: Evalúa el lote de requerimientos estructurados.
    Devuelve un JSON Array.
    """
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input["resultados"]]
    num_predict = num_predict_override or calcular_num_predict("Quality", len(expected_issue_ids))
    selection = obtener_llm_para_agente(
        "quality", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("quality_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_text = prompt.format(issues_json_str=issues_json_str, expected_issue_ids=json.dumps(expected_issue_ids))
    
    from core.performance_audit import parametros_ollama
    params = (
        parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
        if selection.provider == "ollama" else
        {"provider": "groq", "model": selection.model, "temperature": 0.1,
         "max_completion_tokens": int(os.getenv("REMOTE_QUALITY_MAX_COMPLETION_TOKENS", "2048")),
         "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
         "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden")}
    )
    
    with auditar_llamada_agente(
        "Quality_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        prompt_values = {"issues_json_str": issues_json_str, "expected_issue_ids": json.dumps(expected_issue_ids)}
        from core.remote_execution import REMOTE_PACER
        if selection.provider == "groq":
            REMOTE_PACER.before_call("groq", "Quality")
        try:
            result = invocar_con_fallback(
                "Quality", selection,
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
            if selection.provider == "groq":
                REMOTE_PACER.after_call("groq", "Quality")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Quality", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Quality", result=result, metadata=metadata,
            sub_batch=sub_batch, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )
    
    return response.content
