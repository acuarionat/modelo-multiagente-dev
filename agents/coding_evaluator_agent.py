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


def parametros_auditoria_evaluador_codificacion(selection, num_predict: int) -> dict:
    if selection.provider == "nvidia":
        return {
            "provider": "nvidia",
            "model": selection.model,
            "temperature": float(os.getenv("NVIDIA_CENTRAL_TEMPERATURE", "0.1")),
            "max_completion_tokens": int(os.getenv("NVIDIA_CENTRAL_MAX_COMPLETION_TOKENS", "4096")),
            "top_p": float(os.getenv("NVIDIA_CENTRAL_TOP_P", "1")),
        }
    return parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)


def analizar_evaluador_codificacion(issues_json_str: str) -> str:
    """
    Agente Evaluador de Codificación: recibe las métricas ya calculadas de
    MC-05, MS-05, MS-06 y MS-07 (solo lectura) junto con las
    interpretaciones ya producidas por Calidad y Seguridad de Codificación,
    y produce hallazgos consolidados por Issue COD.

    Reutiliza la configuración existente del rol Evaluador (NVIDIA): mismo
    LLM_PROVIDER_EVALUATOR, NVIDIA_MODEL_CENTRAL y NVIDIA_CENTRAL_MAX_COMPLETION_TOKENS
    que el Evaluador de Requerimientos y de Diseño.

    No recalcula ni modifica MC-05/MS-05/MS-06/MS-07, no inventa ED, COD
    ni RF/RNF, no decide el estado orientativo final.
    """
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input]
    num_predict = calcular_num_predict("Evaluator", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "evaluator", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("coding_evaluator_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "issues_json_str": issues_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)

    params = parametros_auditoria_evaluador_codificacion(selection, num_predict)

    with auditar_llamada_agente(
        "Coding_Evaluator_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        try:
            result = invocar_con_fallback(
                "Coding_Evaluator", selection,
                lambda: chain.invoke(prompt_values),
                lambda: ((prompt | crear_llm_local(
                    json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
                )).invoke(prompt_values), OLLAMA_MODEL),
            )
        except RemoteLLMError as exc:
            exc.issue_ids = list(expected_issue_ids)
            raise
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Coding_Evaluator", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Coding_Evaluator", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
