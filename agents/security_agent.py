from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt

def analyze_security(requirements_text: str) -> str:
    """
    Agente de Seguridad: Evalúa el texto de requerimientos según ISO 27034.
    """
    # Evaluamos el texto en modo JSON
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("security_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    
    response = chain.invoke({"requirements_text": requirements_text})
    
    return response.content
