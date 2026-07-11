from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call

def evaluate_reports(quality_report: str, security_report: str) -> str:
    """
    Agente Evaluador: Lee reportes de calidad y seguridad (JSON strings) y emite un veredicto en JSON.
    """
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("evaluator_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(
        quality_report=quality_report,
        security_report=security_report
    )
    context_text = "\n".join([quality_report, security_report])
    
    with audit_agent_call(
        "Evaluator",
        prompt_text=prompt_text,
        context_text=context_text,
        input_json_text=context_text,
        json_mode=True,
    ) as audit:
        response = chain.invoke({
            "quality_report": quality_report,
            "security_report": security_report
        })
        audit["response"] = response.content
    return response.content
