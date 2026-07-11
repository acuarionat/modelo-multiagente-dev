from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call

def analyze_security(requirements_text: str) -> str:
    """
    Agente de Seguridad: Evalúa el texto de requerimientos según ISO 27034.
    """
    # Evaluamos el texto en modo JSON
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("security_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(requirements_text=requirements_text)
    
    with audit_agent_call(
        "Security",
        prompt_text=prompt_text,
        context_text=requirements_text,
        input_json_text=requirements_text,
        json_mode=True,
    ) as audit:
        response = chain.invoke({"requirements_text": requirements_text})
        audit["response"] = response.content
    
    return response.content
