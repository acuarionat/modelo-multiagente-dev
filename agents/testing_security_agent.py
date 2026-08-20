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


def parametros_auditoria_seguridad_pruebas(selection, num_predict: int) -> dict:
    if selection.provider == "groq":
        return {
            "provider": "groq",
            "model": selection.model,
            "temperature": 0.1,
            "max_completion_tokens": int(os.getenv("REMOTE_SECURITY_MAX_COMPLETION_TOKENS", "2048")),
            "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
            "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden"),
        }
    return parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)


def analizar_seguridad_pruebas(entrada_json_str: str) -> str:
    """
    Agente de Seguridad de Pruebas: interpreta exclusivamente MS-08
    (Cobertura de Verificación de Controles) y MS-09 (Pruebas de
    Seguridad Satisfactorias), ya calculadas por Python a partir de la
    evidencia real registrada en el Issue PRU.

    Reutiliza la configuración existente del rol Seguridad (Groq): mismo
    LLM_PROVIDER_SECURITY, GROQ_MODEL_SECURITY y REMOTE_SECURITY_MAX_COMPLETION_TOKENS
    que Seguridad de Requerimientos, Diseño y Codificación.

    No calcula ni recalcula MS-08 ni MS-09, no decide el estado final, no
    inventa controles ni pruebas de seguridad.
    """
    parsed_input = json.loads(entrada_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input]
    num_predict = calcular_num_predict("Security", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "security", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("testing_security_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "entrada_json_str": entrada_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)

    params = parametros_auditoria_seguridad_pruebas(selection, num_predict)

    with auditar_llamada_agente(
        "Testing_Security_Batch",
        prompt_text=prompt_text,
        context_text=entrada_json_str,
        input_json_text=entrada_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        from core.remote_execution import REMOTE_PACER
        if selection.provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(selection.provider, "TestingSecurity")
        try:
            result = invocar_con_fallback(
                "Testing_Security", selection,
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
                REMOTE_PACER.after_call(selection.provider, "TestingSecurity")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Testing_Security", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Testing_Security", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
