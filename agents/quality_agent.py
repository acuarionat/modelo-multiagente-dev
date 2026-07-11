from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
from core.performance_audit import audit_agent_call
import json

def analyze_quality(requirements_text: str) -> str:
    """
    Agente de Calidad: Evalúa el texto de requerimientos según ISO 25023.
    """
    # Para esta etapa, usamos el LLM en modo JSON directamente sobre el texto
    llm = get_llm(json_mode=True)
    prompt_template = load_prompt("quality_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    prompt_text = prompt.format(requirements_text=requirements_text)
    
    with audit_agent_call(
        "Quality",
        prompt_text=prompt_text,
        context_text=requirements_text,
        input_json_text=requirements_text,
        json_mode=True,
    ) as audit:
        response = chain.invoke({"requirements_text": requirements_text})
        audit["response"] = response.content
    
    # Nos aseguramos de devolver el JSON como string (el output de Ollama format="json" ya es un string JSON)
    return response.content
