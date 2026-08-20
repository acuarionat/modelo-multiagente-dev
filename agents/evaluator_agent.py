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


def parametros_auditoria_evaluador(selection, num_predict: int) -> dict:
    if selection.provider == "nvidia":
        return {
            "provider": "nvidia",
            "model": selection.model,
            "temperature": float(os.getenv("NVIDIA_CENTRAL_TEMPERATURE", "0.1")),
            "max_completion_tokens": int(os.getenv("NVIDIA_CENTRAL_MAX_COMPLETION_TOKENS", "4096")),
            "top_p": float(os.getenv("NVIDIA_CENTRAL_TOP_P", "1")),
        }
    return parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)


def evaluar_reportes(quality_reports: str, security_reports: str, num_predict_override: int | None = None) -> str:
    """
    Agente Evaluador: Lee reportes de calidad y seguridad (JSON Array strings) y emite un veredicto en JSON Array.
    """
    quality = json.loads(quality_reports)
    security = json.loads(security_reports)
    quality_by_iid = {item["issue_iid"]: item for item in quality["resultados"]}
    security_by_iid = {item["issue_iid"]: item for item in security["resultados"]}
    common_ids = sorted(set(quality_by_iid) & set(security_by_iid))
    num_predict = num_predict_override or calcular_num_predict("Evaluator", len(common_ids))

    selection = obtener_llm_para_agente(
        "evaluator", json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
    )
    prompt_template = cargar_prompt("evaluator_prompt.txt")
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | selection.llm

    reduced_input = {
        "resultados": [
            {
                "issue_iid": iid,
                "historia_id": quality_by_iid[iid].get("historia_id", f"HU-{iid:03d}"),
                "calidad": quality_by_iid[iid],
                "seguridad": security_by_iid[iid],
            }
            for iid in common_ids
        ]
    }
    evaluation_input_str = json.dumps(reduced_input, ensure_ascii=False)
    prompt_values = {"evaluation_input": evaluation_input_str, "expected_issue_ids": json.dumps(common_ids)}
    prompt_text = prompt.format(**prompt_values)

    params = parametros_auditoria_evaluador(selection, num_predict)

    with auditar_llamada_agente(
        "Evaluator_Batch",
        prompt_text=prompt_text,
        context_text=evaluation_input_str,
        input_json_text=evaluation_input_str,
        model_params=params,
        provider=selection.provider,
    ) as audit:
        from core.remote_execution import REMOTE_PACER, reintentar_con_backoff
        if selection.provider in ("groq", "nvidia"):
            REMOTE_PACER.before_call(selection.provider, "Evaluator")
        try:
            invoke_fn = lambda: invocar_con_fallback(
                "Evaluator", selection,
                lambda: chain.invoke(prompt_values),
                lambda: ((prompt | crear_llm_local(
                    json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1,
                )).invoke(prompt_values), OLLAMA_MODEL),
            )
            if selection.provider == "nvidia":
                result = reintentar_con_backoff(invoke_fn, agent="Evaluator")
            else:
                result = invoke_fn()
        except RemoteLLMError as exc:
            exc.issue_ids = list(common_ids)
            raise
        finally:
            if selection.provider in ("groq", "nvidia"):
                REMOTE_PACER.after_call(selection.provider, "Evaluator")
        response = result.response
        audit["response"] = response.content
        audit["provider_used"] = result.provider
        audit["model_used"] = result.model
        metadata = registrar_resumen_respuesta("Evaluator", result, response.content)
        rechazar_respuesta_remota_truncada(
            agent_name="Evaluator", result=result, metadata=metadata,
            sub_batch=None, issue_ids=common_ids,
            max_completion_tokens=params.get("max_completion_tokens", num_predict),
        )

    return response.content
