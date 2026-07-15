from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call
from core.batch_contract import calculate_num_predict
import json

def process_ticket(project_name: str, issues_json_str: str, sprint_context: str, num_predict_override: int | None = None) -> str:
    """
    Agente Central: Orquesta el inicio procesando un lote de historias.
    Analiza el texto de los requerimientos de múltiples historias y confirma la recepción generando un JSON estructurado (Array).
    """
    expected_issue_ids = [int(item["id"]) for item in json.loads(issues_json_str)]
    num_predict = num_predict_override or calculate_num_predict("Central_Init", len(expected_issue_ids))
    llm = get_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    prompt_template = load_prompt("central_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        issues_json_str=issues_json_str,
        sprint_context=sprint_context,
        expected_issue_ids=json.dumps(expected_issue_ids),
    )
    
    from core.performance_audit import ollama_params
    params = ollama_params(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    
    with audit_agent_call(
        "Central_Init_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        model_params=params,
    ) as audit:
        response = chain.invoke({
            "project_name": project_name,
            "issues_json_str": issues_json_str,
            "sprint_context": sprint_context,
            "expected_issue_ids": json.dumps(expected_issue_ids),
        })
        audit["response"] = response.content
    return response.content
