from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call
from core.batch_contract import calculate_num_predict

def evaluate_reports(quality_reports: str, security_reports: str, num_predict_override: int | None = None) -> str:
    """
    Agente Evaluador: Lee reportes de calidad y seguridad (JSON Array strings) y emite un veredicto en JSON Array.
    """
    import json
    prompt_template = load_prompt("evaluator_prompt.txt")
    
    quality = json.loads(quality_reports)
    security = json.loads(security_reports)
    quality_by_iid = {item["issue_iid"]: item for item in quality["resultados"]}
    security_by_iid = {item["issue_iid"]: item for item in security["resultados"]}
    common_ids = sorted(set(quality_by_iid) & set(security_by_iid))
    num_predict = num_predict_override or calculate_num_predict("Evaluator", len(common_ids))
    llm = get_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.0)
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
    
    from core.performance_audit import ollama_params
    params = ollama_params(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.0)
    
    with audit_agent_call(
        "Evaluator_Batch",
        prompt_text=prompt_text,
        context_text=evaluation_input_str,
        input_json_text=evaluation_input_str,
        model_params=params,
    ) as audit:
        response = chain.invoke({"evaluation_input": evaluation_input_str, "expected_issue_ids": json.dumps(common_ids)})
        audit["response"] = response.content
    return response.content
