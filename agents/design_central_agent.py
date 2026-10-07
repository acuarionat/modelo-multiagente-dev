from langchain_core.prompts import PromptTemplate
from agents import cargar_prompt
from agents.llm_invocation import (
    RemoteLLMError, invocar_con_fallback, rechazar_respuesta_remota_truncada,
    registrar_resumen_respuesta,
)
from openai import LengthFinishReasonError
from core.llm_factory import crear_llm_local, crear_llm_nvidia, obtener_llm_para_agente
from core.config import OLLAMA_MODEL
from core.performance_audit import auditar_llamada_agente
from core.batch_contract import calcular_num_predict
import json
import logging
import os

logger = logging.getLogger(__name__)


def procesar_diseno_central(
    project_name: str,
    issues_json_str: str,
    sprint_context: str,
) -> str:
    """
    Agente Central de Diseño: organiza y relaciona la evidencia de Diseño ya
    estructurada (design_issue_mapper + design_context), estableciendo la
    trazabilidad Requisito -> Elemento de Diseño.

    No evalúa Calidad ni Seguridad, no calcula métricas y no inventa
    componentes para completar el diseño.
    """
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input]
    num_predict = calcular_num_predict("Central_Init", len(expected_issue_ids))

    selection = obtener_llm_para_agente(
        "design_central", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("design_central_prompt.txt")

    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm
    prompt_values = {
        "project_name": project_name,
        "sprint_context": sprint_context,
        "issues_json_str": issues_json_str,
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
        "Design_Central_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        from core.remote_execution import REMOTE_PACER, reintentar_con_backoff
        if selection.provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(selection.provider, "DesignCentral")
        def invoke_selected():
            try:
                return chain.invoke(prompt_values)
            except LengthFinishReasonError:
                # La decodificación guiada JSON de nemotron a veces entra en una
                # generación descontrolada hasta agotar max_tokens (salida normal ~1.5k).
                # Se reintenta una vez sin response_format; analizar_respuesta_lote
                # valida/repara el JSON resultante.
                if selection.provider != "nvidia":
                    raise
                logger.warning(
                    "Design_Central: respuesta agotó max_tokens con response_format; "
                    "reintentando sin decodificación guiada."
                )
                retry_llm = crear_llm_nvidia(selection.model, 4096, json_mode=False)
                return (prompt | retry_llm).invoke(prompt_values)

        try:
            invoke_fn = lambda: invocar_con_fallback(
                "Design_Central", selection,
                invoke_selected,
                lambda: ((prompt | crear_llm_local(
                    json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
                )).invoke(prompt_values), OLLAMA_MODEL),
            )
            if selection.provider == "nvidia":
                result = reintentar_con_backoff(invoke_fn, agent="DesignCentral")
            else:
                result = invoke_fn()
        except RemoteLLMError as exc:
            exc.issue_ids = list(expected_issue_ids)
            raise
        finally:
            if selection.provider in ("groq", "nvidia"):
                REMOTE_PACER.after_call(selection.provider, "DesignCentral")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Design_Central", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Design_Central", result=result, metadata=metadata,
            sub_batch=None, issue_ids=expected_issue_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
