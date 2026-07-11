import json
from agents import get_llm, load_prompt
from langchain_core.prompts import PromptTemplate

def map_issue_to_json(issue) -> dict:
    """
    Convierte una Historia de Usuario de GitLab en una representación estructurada.
    Utiliza un LLM para extraer la información estructurada desde el texto de la descripción.
    """
    llm = get_llm(json_mode=True)
    
    # Prompt ligero para el mapeo inicial de la historia de usuario
    prompt_template = """
Eres un analizador de Requerimientos y Historias de Usuario.
Tu objetivo es leer el título y la descripción de una Historia de Usuario proveniente de GitLab y extraer la información en el siguiente formato JSON estricto.

Formato JSON esperado:
{{
    "id": "Identificador de la historia (e.g. HU-001 o el IID)",
    "titulo": "Título de la historia",
    "actor": "Quién realiza la acción",
    "accion": "Qué acción se desea realizar",
    "objetivo": "Para qué se desea realizar la acción",
    "criterios": ["lista", "de", "criterios", "de", "aceptación"],
    "restricciones": ["lista", "de", "restricciones", "o", "reglas", "de", "negocio"],
    "prioridad": "Alta/Media/Baja",
    "labels": ["etiquetas", "extraidas"]
}}

Datos de entrada:
ID de GitLab: {issue_iid}
Título: {title}
Etiquetas: {labels}
Descripción:
{description}

Devuelve ÚNICAMENTE el objeto JSON.
"""
    prompt = PromptTemplate.from_template(prompt_template)
    chain = prompt | llm
    
    response = chain.invoke({
        "issue_iid": str(issue.iid),
        "title": issue.title,
        "labels": json.dumps(issue.labels),
        "description": issue.description or ""
    })
    
    try:
        parsed_json = json.loads(response.content)
        # Ensure labels are always included as they came from GitLab if missing
        if "labels" not in parsed_json:
            parsed_json["labels"] = issue.labels
        return parsed_json
    except json.JSONDecodeError:
        # Fallback en caso de que el LLM falle
        return {
            "id": str(issue.iid),
            "titulo": issue.title,
            "actor": "Desconocido",
            "accion": "Desconocida",
            "objetivo": "Desconocido",
            "criterios": [],
            "restricciones": [],
            "prioridad": "Desconocida",
            "labels": issue.labels,
            "raw_description": issue.description
        }
