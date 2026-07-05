from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt

def evaluate_reports(quality_report: str, security_report: str) -> str:
    """
    Agente Evaluador: Lee reportes de calidad y seguridad (JSON strings) y emite un veredicto en JSON.
    """
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("evaluator_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    
    response = chain.invoke({
        "quality_report": quality_report,
        "security_report": security_report
    })
    return response.content
