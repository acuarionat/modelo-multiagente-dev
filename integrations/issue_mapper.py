import re

def mapear_issue_a_json(issue) -> dict:
    """
    Convierte una Historia de Usuario de GitLab en una representación estructurada
    extrayendo directamente los campos mediante expresiones regulares sobre la nueva plantilla Markdown.
    """
    description_text = issue.description or ""
    
    def extraer_seccion(header: str) -> str:
        # Busca el header, captura todo hasta el siguiente ## o el final del string.
        pattern = rf"##\s*{header}\s*(.*?)(?=\n##\s*|$)"
        match = re.search(pattern, description_text, re.IGNORECASE | re.DOTALL)
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
        "actor": actor,
        "funcionalidad": funcionalidad,
        "objetivo": objetivo,
        "criterios_aceptacion": extraer_lista(criterios_raw) if extraer_lista(criterios_raw) else [criterios_raw] if criterios_raw else [],
        "restricciones": extraer_lista(restricciones_raw) if extraer_lista(restricciones_raw) else [restricciones_raw] if restricciones_raw else [],
        "prioridad": prioridad,
        "observaciones": extraer_seccion("Observaciones"),
        "labels": issue.labels
    }
    
    return parsed_json
