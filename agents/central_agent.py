from langchain_core.prompts import PromptTemplate
from agents import get_llm, load_prompt

def process_ticket(project_name: str, requirements_text: str) -> str:
    """
    Agente Central: Orquesta el inicio.
    Analiza el texto de los requerimientos y confirma la recepción.
    """
    llm = get_llm()
    prompt_template = load_prompt("central_prompt.txt")
    
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    
    response = chain.invoke({
        "project_name": project_name,
        "requirements_text": requirements_text
    })
    return response.content

def synthesize_final_report(evaluation: str, project_name: str) -> str:
    """
    Agente Central: Consolida el reporte final.
    """
    llm = get_llm()
    prompt = PromptTemplate.from_template(
        "Como Agente Central, consolida el siguiente reporte de evaluación para el proyecto '{project_name}'.\n"
        "Veredicto del evaluador (en JSON):\n{evaluation}\n"
        "Genera un reporte final en formato Markdown, amigable para el equipo humano, resumiendo la decisión, los riesgos y los próximos pasos."
    )
    chain = prompt | llm
    
    response = chain.invoke({"project_name": project_name, "evaluation": evaluation})
    return response.content
