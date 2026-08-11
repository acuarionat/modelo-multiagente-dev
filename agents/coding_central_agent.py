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


def procesar_codificacion_central(
    project_name: str,
    coding_context_json_str: str,
    sprint_context: str,
) -> str:
    """
    Agente Central de Codificación: valida semánticamente la implementación
    declarada en un Issue COD-xxx contra el código real localizado y la
    evidencia técnica ya normalizada (Radon/Semgrep/pip-audit/Gitleaks),
    relaciona el COD con los Elementos de Diseño (ED) y reconstruye la
    trazabilidad heredada de la matriz de Diseño.

    No calcula MC-05, MS-05, MS-06 ni MS-07, no evalúa Calidad ni
    Seguridad, y no inventa archivos, ED ni resultados de herramientas.
    """
    parsed_input = json.loads(coding_context_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input]
    num_predict = calcular_num_predict("Central_Init", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "coding_central", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("coding_central_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "project_name": project_name,
        "sprint_context": sprint_context,
        "coding_context_json_str": coding_context_json_str,
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
        "Coding_Central_Batch",
        prompt_text=prompt_text,
        context_text=coding_context_json_str,
        input_json_text=coding_context_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        try:
            result = invocar_con_fallback(
                "Coding_Central", selection,
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
        metadata = registrar_resumen_respuesta("Coding_Central", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Coding_Central", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
