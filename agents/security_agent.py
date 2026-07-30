from langchain_core.prompts import PromptTemplate
from agents import obtener_llm, cargar_prompt
from core.performance_audit import auditar_llamada_agente
from core.batch_contract import calcular_num_predict
import json
import logging

logger = logging.getLogger(__name__)

def analizar_seguridad(
    issues_json_str: str,
    num_predict_override: int | None = None,
) -> str:
    """
    Agente de Seguridad: Evalúa el lote de requerimientos estructurados.
    Devuelve un JSON Array.
    """
    # Evaluamos el texto en modo JSON
    parsed_input = json.loads(issues_json_str)
    expected_issue_ids = [item["issue_iid"] for item in parsed_input["resultados"]]
    num_predict = num_predict_override or calcular_num_predict("Security", len(expected_issue_ids))
    llm = obtener_llm(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    prompt_template = cargar_prompt("security_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_values = {
        "issues_json_str": issues_json_str,
        "expected_issue_ids": json.dumps(expected_issue_ids),
    }
    prompt_text = prompt.format(**prompt_values)
    
    from core.performance_audit import parametros_ollama
    params = parametros_ollama(json_mode=True, num_predict=num_predict, num_ctx=8192, temperature=0.1)
    
    with auditar_llamada_agente(
        "Security_Batch",
        prompt_text=prompt_text,
        context_text=issues_json_str,
        input_json_text=issues_json_str,
        model_params=params,
    ) as audit:
        response = chain.invoke(prompt_values)
        logger.info("PHI4_RAW Security:\n%s", response.content)
        audit["response"] = response.content
    
    return response.content
