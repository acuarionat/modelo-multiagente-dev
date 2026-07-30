from langchain_core.prompts import PromptTemplate
from agents import obtener_llm, cargar_prompt
from core.performance_audit import auditar_llamada_agente
from core.batch_contract import calcular_num_predict
import json
import logging

logger = logging.getLogger(__name__)

def procesar_ticket(project_name: str, issues_json_str: str, sprint_context: str, num_predict_override: int | None = None) -> str:
    """
    Agente Central: Orquesta el inicio procesando un lote de historias.
    Analiza el texto de los requerimientos de múltiples historias y confirma la recepción generando un JSON estructurado (Array).
    """
    expected_issue_ids = [int(item["id"]) for item in json.loads(issues_json_str)]
    num_predict = num_predict_override or calcular_num_predict("Central_Init", len(expected_issue_ids))
    llm = obtener_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    prompt_template = cargar_prompt("central_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        issues_json_str=issues_json_str,
        sprint_context=sprint_context,
        expected_issue_ids=json.dumps(expected_issue_ids),
    )
    
    from core.performance_audit import parametros_ollama
    params = parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    
    with auditar_llamada_agente(
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
        logger.info("PHI4_RAW Central:\n%s", response.content)
        audit["response"] = response.content
    return response.content
