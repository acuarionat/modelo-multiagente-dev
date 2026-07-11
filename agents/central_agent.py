from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call
import json

def process_ticket(project_name: str, requirements_text: str) -> str:
    """
    Agente Central: Orquesta el inicio.
    Analiza el texto de los requerimientos y confirma la recepción generando un JSON estructurado.
    """
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("central_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        requirements_text=requirements_text
    )
    
    with audit_agent_call(
        "Central_Init",
        prompt_text=prompt_text,
        context_text=requirements_text,
        json_mode=True,
    ) as audit:
        response = chain.invoke({
            "project_name": project_name,
            "requirements_text": requirements_text
        })
        audit["response"] = response.content
    return response.content

def synthesize_final_report(project_name: str, central_init: str, quality_report: str, security_report: str, evaluation: str) -> str:
    """
    Agente Central: Consolida el reporte final.
    """
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("central_output_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        project_name=project_name,
        central_init=central_init,
        quality_report=quality_report,
        security_report=security_report,
        evaluation=evaluation
    )
    context_text = "\n".join([central_init, quality_report, security_report, evaluation])
    
    with audit_agent_call(
        "Central_Final",
        prompt_text=prompt_text,
        context_text=context_text,
        input_json_text=context_text,
        json_mode=True,
    ) as audit:
        response = chain.invoke({
            "project_name": project_name,
            "central_init": central_init,
            "quality_report": quality_report,
            "security_report": security_report,
            "evaluation": evaluation
        })
        audit["response"] = response.content
    return response.content
