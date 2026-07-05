from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt
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
    
    response = chain.invoke({"requirements_text": requirements_text})
    
    # Nos aseguramos de devolver el JSON como string (el output de Ollama format="json" ya es un string JSON)
    return response.content
