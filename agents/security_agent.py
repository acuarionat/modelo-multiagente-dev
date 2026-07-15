from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call
from core.batch_contract import calculate_num_predict
import json

def analyze_security(issues_json_str: str, num_predict_override: int | None = None) -> str:
    """
    Agente de Seguridad: Evalúa el lote de requerimientos estructurados.
    Devuelve un JSON Array.
    """
    # Evaluamos el texto en modo JSON
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input["resultados"]]
    num_predict = num_predict_override or calculate_num_predict("Security", len(expected_issue_ids))
    llm = get_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    prompt_template = load_prompt("security_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(issues_json_str=issues_json_str, expected_issue_ids=json.dumps(expected_issue_ids))
    
    from core.performance_audit import ollama_params
    params = ollama_params(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    
    with audit_agent_call(
        "Security_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
    ) as audit:
        response = chain.invoke({"issues_json_str": issues_json_str, "expected_issue_ids": json.dumps(expected_issue_ids)})
        audit["response"] = response.content
    
    return response.content
