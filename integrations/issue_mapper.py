import re

VALORES_DESCONOCIDOS = {"", "desconocido", "desconocida", "n/a", "no especificado", "sin información"}


def _texto_identificado(value) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in VALORES_DESCONOCIDOS


def validar_entrada_issue(issue_data: dict) -> dict:
    """Clasifica una historia antes de invocar al modelo, sin exigir campos opcionales."""
    faltantes = []
    if not _texto_identificado(issue_data.get("titulo")):
        faltantes.append("titulo")
    if not _texto_identificado(issue_data.get("descripcion_original")):
        faltantes.append("descripcion")
    story_fields = ("actor", "funcionalidad", "objetivo")
    if not any(_texto_identificado(issue_data.get(field)) for field in story_fields):
        faltantes.append("actor_accion_objetivo")
    criterios = [x for x in issue_data.get("criterios_aceptacion", []) if _texto_identificado(x)]
    advertencias = []
    for field in story_fields:
        if not _texto_identificado(issue_data.get(field)):
            advertencias.append(f"{field} no identificado")
    if not criterios:
        advertencias.append("criterios de aceptación no especificados")
    if not _texto_identificado(issue_data.get("prioridad")):
        advertencias.append("prioridad no especificada")
    if not issue_data.get("restricciones"):
        advertencias.append("restricciones no especificadas")
    if not _texto_identificado(issue_data.get("observaciones")):
        advertencias.append("observaciones no especificadas")

    if faltantes:
        estado = "informacion_insuficiente"
    elif advertencias:
        estado = "entrada_con_advertencias"
    else:
        estado = "entrada_valida"
    return {"estado": estado, "campos_faltantes": faltantes, "advertencias": advertencias}


def separar_entradas_para_analisis(issues_data: list, allow_incomplete: bool = False) -> tuple[list, list]:
    insufficient = [
        item for item in issues_data
        if item.get("validacion_entrada", {}).get("estado") == "informacion_insuficiente"
    ]
    processable = issues_data if allow_incomplete else [item for item in issues_data if item not in insufficient]
    return processable, insufficient

def mapear_issue_a_json(issue) -> dict:
    """
    Convierte una Historia de Usuario de GitLab en una representación estructurada
    extrayendo directamente los campos mediante expresiones regulares sobre la nueva plantilla Markdown.
    """
    description_text = issue.description or ""
    
    def extraer_seccion(header: str) -> str:
        # Busca el header, captura todo hasta el siguiente ## o el final del string.
        pattern = rf"^\s*#{{1,6}}\s*{header}\s*:?[ \t]*(.*?)(?=^\s*#{{1,6}}\s+|\Z)"
        match = re.search(pattern, description_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""
        
    def extraer_lista(text: str) -> list:
        # Extrae items de lista (- o 1.)
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- ') or re.match(r'^\d+\.', line):
                clean_item = re.sub(r'^(- |\d+\.)\s*', '', line).strip()
                if clean_item:
                    items.append(clean_item)
        return items

    nombre = extraer_seccion("Nombre")
    titulo = nombre if nombre else issue.title
    
    desc_raw = extraer_seccion("Descripción")
    
    actor_match = re.search(r'\*\*Como\*\*\s*(.*?)(?=\n\*\*Quiero\*\*|$)', desc_raw, re.IGNORECASE | re.DOTALL)
    actor = actor_match.group(1).strip() if actor_match else "Desconocido"
    
    quiero_match = re.search(r'\*\*Quiero\*\*\s*(.*?)(?=\n\*\*Para\*\*|$)', desc_raw, re.IGNORECASE | re.DOTALL)
    funcionalidad = quiero_match.group(1).strip() if quiero_match else ""
    
    para_match = re.search(r'\*\*Para\*\*\s*(.*?)$', desc_raw, re.IGNORECASE | re.DOTALL)
    objetivo = para_match.group(1).strip() if para_match else "Desconocido"
    
    criterios_raw = extraer_seccion("Criterios de aceptación")
    restricciones_raw = extraer_seccion("Restricciones")
    
    prioridad_raw = extraer_seccion("Prioridad")
    prioridad_match = re.search(r'(Alta|Media|Baja)', prioridad_raw, re.IGNORECASE)
    prioridad = prioridad_match.group(1).capitalize() if prioridad_match else "Desconocida"

    parsed_json = {
        "id": str(issue.iid),
        "titulo": titulo,
        "descripcion_original": description_text.strip(),
        "actor": actor,
        "funcionalidad": funcionalidad,
        "objetivo": objetivo,
        "criterios_aceptacion": extraer_lista(criterios_raw) if extraer_lista(criterios_raw) else [criterios_raw] if criterios_raw else [],
        "restricciones": extraer_lista(restricciones_raw) if extraer_lista(restricciones_raw) else [restricciones_raw] if restricciones_raw else [],
        "prioridad": prioridad,
        "observaciones": extraer_seccion("Observaciones"),
        "labels": issue.labels
    }
    parsed_json["validacion_entrada"] = validar_entrada_issue(parsed_json)
    
    return parsed_json
