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


def procesar_pruebas_central(
    project_name: str,
    testing_context_json_str: str,
    sprint_context: str,
) -> str:
    """
    Agente Central de Pruebas: contextualiza el Issue PRU-xxx ya mapeado
    junto con la trazabilidad heredada ya resuelta contra la Matriz de
    Trazabilidad — Etapa Codificación, y la evidencia y métricas
    MC-07/MC-08/MS-08/MS-09 ya calculadas por Python.

    No calcula MC-07, MC-08, MS-08 ni MS-09, no evalúa Calidad ni
    Seguridad, y no inventa pruebas, fallos, controles, ED, RF/RNF ni
    historias.
    """
    parsed_input = json.loads(testing_context_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input]
    num_predict = calcular_num_predict("Central_Init", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "testing_central", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("testing_central_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "project_name": project_name,
        "sprint_context": sprint_context,
        "testing_context_json_str": testing_context_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)

    from core.performance_audit import parametros_ollama
    params = (
        parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
        if selection.provider == "ollama" else
        {"provider": selection.provider, "model": selection.model, "temperature": 0.1,
         "max_completion_tokens": int(os.getenv("NVIDIA_CENTRAL_MAX_COMPLETION_TOKENS", "4096"))}
    )

    with auditar_llamada_agente(
        "Testing_Central_Batch",
        prompt_text=prompt_text,
        context_text=testing_context_json_str,
        input_json_text=testing_context_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        try:
            result = invocar_con_fallback(
                "Testing_Central", selection,
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
        metadata = registrar_resumen_respuesta("Testing_Central", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Testing_Central", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
