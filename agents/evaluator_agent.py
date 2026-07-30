from langchain_core.prompts import PromptTemplate
from agents import obtener_llm, cargar_prompt
from core.performance_audit import auditar_llamada_agente
from core.batch_contract import calcular_num_predict
import logging

logger = logging.getLogger(__name__)

def evaluar_reportes(quality_reports: str, security_reports: str, num_predict_override: int | None = None) -> str:
    """
    Agente Evaluador: Lee reportes de calidad y seguridad (JSON Array strings) y emite un veredicto en JSON Array.
    """
    import json
    prompt_template = cargar_prompt("evaluator_prompt.txt")
    
    quality = json.loads(quality_reports)
    security = json.loads(security_reports)
    quality_by_iid = {item["issue_iid"]: item for item in quality["resultados"]}
    security_by_iid = {item["issue_iid"]: item for item in security["resultados"]}
    common_ids = sorted(set(quality_by_iid) & set(security_by_iid))
    num_predict = num_predict_override or calcular_num_predict("Evaluator", len(common_ids))
    llm = obtener_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.0)
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
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(evaluation_input=evaluation_input_str, expected_issue_ids=json.dumps(common_ids))
    
    from core.performance_audit import parametros_ollama
    params = parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.0)
    
    with auditar_llamada_agente(
        "Evaluator_Batch",
        prompt_text=prompt_text,
        context_text=evaluation_input_str,
        input_json_text=evaluation_input_str,
        model_params=params,
    ) as audit:
        response = chain.invoke({"evaluation_input": evaluation_input_str, "expected_issue_ids": json.dumps(common_ids)})
        logger.info("PHI4_RAW Evaluator:\n%s", response.content)
        audit["response"] = response.content
    return response.content
