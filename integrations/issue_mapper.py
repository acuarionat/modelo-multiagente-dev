import json
import logging
import re

logger = logging.getLogger(__name__)

VALORES_DESCONOCIDOS = {
    "", "desconocido", "desconocida", "n/a", "no especificado",
    "sin información", "ninguna", "ninguna.", "ninguno", "ninguno."
}


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
    """Conserva todas las historias identificadas; la insuficiencia es evaluable, no un filtro."""
    insufficient = [
        item for item in issues_data
        if item.get("validacion_entrada", {}).get("estado") == "informacion_insuficiente"
    ]
    return list(issues_data), insufficient

def extraer_datos_sensibles(text: str) -> dict:
    text = str(text or "").strip()

    if not text:
        return {
            "maneja_datos_sensibles": None,
            "tipos_datos_sensibles": [],
        }

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    maneja = None
    datos = []

    for line in lines:
        if re.fullmatch(
            r"[-*]?\s*\[[xX]\]\s*s[ií]\.?",
            line,
            re.IGNORECASE,
        ):
            maneja = True
            continue

        if re.fullmatch(
            r"[-*]?\s*\[[xX]\]\s*no\.?",
            line,
            re.IGNORECASE,
        ):
            maneja = False
            continue

        if re.fullmatch(
            r"[-*]?\s*\[[ ]\]\s*(s[ií]|no)\.?",
            line,
            re.IGNORECASE,
        ):
            continue

        if re.fullmatch(r"s[ií]\.?", line, re.IGNORECASE):
            maneja = True
            continue

        if re.fullmatch(r"no\.?", line, re.IGNORECASE):
            maneja = False
            continue

        datos.append(line.rstrip("."))

    return {
        "maneja_datos_sensibles": maneja,
        "tipos_datos_sensibles": datos,
    }

def mapear_issue_a_json(issue) -> dict:
    """
    Convierte una Historia de Usuario de GitLab en una representación estructurada
    extrayendo directamente los campos mediante expresiones regulares sobre la nueva plantilla Markdown.
    """
    description_text = issue.description or ""
    
    def extraer_seccion(header: str) -> str:
        # Busca el header, captura todo hasta el siguiente ## o el final del string.
        escaped_header = re.escape(header)
        pattern = rf"^\s*#{{1,6}}\s*{escaped_header}\s*:?[ \t]*(.*?)(?=^\s*#{{1,6}}\s+|\Z)"
        match = re.search(pattern, description_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if match:
            lines = [
                line for line in match.group(1).strip().splitlines()
                if not re.fullmatch(r"\s*---+\s*", line)
            ]
            return "\n".join(lines).strip()
        return ""
        
    def extraer_lista(text: str) -> list:
        # La plantilla oficial admite viñetas Markdown o un elemento por línea.
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line or re.fullmatch(r"---+", line):
                continue
            clean_item = re.sub(
                r"^(?:[-*+]\s+|\d+[.)]\s*)",
                "",
                line,
            ).strip()
            if not clean_item:
                continue
            if clean_item.casefold() in VALORES_DESCONOCIDOS:
                continue
            items.append(clean_item)
        return items

    nombre = extraer_seccion("Nombre")
    titulo = nombre if nombre else issue.title
    # El IID de GitLab identifica técnicamente el issue. Si el equipo ya asignó
    # un código HU en el título, lo conservamos como identidad documental para
    # que el Central no tenga que adivinarlo a partir del IID de GitLab.
    historia_match = re.search(
        r"\bHU\s*[-_ ]\s*(\d+)\b", f"{issue.title}\n{titulo}", re.IGNORECASE,
    )
    historia_id = (
        f"HU-{int(historia_match.group(1)):03d}"
        if historia_match else ""
    )
    
    desc_raw = extraer_seccion("Descripción")
    
    actor_seccion = extraer_seccion("Como")
    actor_match = re.search(r'\*\*Como\*\*\s*(.*?)(?=\n\*\*Quiero\*\*|$)', desc_raw, re.IGNORECASE | re.DOTALL)
    actor = actor_seccion or (actor_match.group(1).strip() if actor_match else "Desconocido")
    
    funcionalidad_seccion = extraer_seccion("Quiero")
    quiero_match = re.search(r'\*\*Quiero\*\*\s*(.*?)(?=\n\*\*Para\*\*|$)', desc_raw, re.IGNORECASE | re.DOTALL)
    funcionalidad = funcionalidad_seccion or (quiero_match.group(1).strip() if quiero_match else "")
    
    objetivo_seccion = extraer_seccion("Para")
    para_match = re.search(r'\*\*Para\*\*\s*(.*?)$', desc_raw, re.IGNORECASE | re.DOTALL)
    objetivo = objetivo_seccion or (para_match.group(1).strip() if para_match else "Desconocido")
    
    criterios_raw = extraer_seccion("Criterios de aceptación")
    restricciones_raw = extraer_seccion("Restricciones")
    datos_seguridad_raw = extraer_seccion(
        "¿La historia maneja datos sensibles?"
    )

    datos_seguridad = extraer_datos_sensibles(
        datos_seguridad_raw
    )

    seguridad = {
        "descripcion": extraer_seccion("Seguridad"),
        "maneja_datos_sensibles": datos_seguridad[
            "maneja_datos_sensibles"
        ],
        "tipos_datos_sensibles": datos_seguridad[
            "tipos_datos_sensibles"
        ],
        "autenticacion": extraer_seccion("Autenticación"),
        "autorizacion_roles": extraer_seccion("Autorización / Roles"),
        "auditoria": extraer_seccion("Auditoría"),
    }
    
    prioridad_raw = extraer_seccion("Prioridad")
    prioridad_match = re.search(r'(Alta|Media|Baja)', prioridad_raw, re.IGNORECASE)
    prioridad = prioridad_match.group(1).capitalize() if prioridad_match else "Desconocida"

    parsed_json = {
        "id": str(issue.iid),
        "issue_iid": int(issue.iid),
        "historia_id": historia_id,
        "titulo": titulo,
        "descripcion_original": description_text.strip(),
        "actor": actor,
        "funcionalidad": funcionalidad,
        "objetivo": objetivo,
        "criterios_aceptacion": extraer_lista(criterios_raw),
        "restricciones": extraer_lista(restricciones_raw),
        "seguridad": seguridad,
        "prioridad": prioridad,
        "observaciones": extraer_seccion("Observaciones"),
        "labels": issue.labels
    }
    parsed_json["validacion_entrada"] = validar_entrada_issue(parsed_json)
    diagnostic_payload = {
        "issue_iid": parsed_json["id"],
        "titulo": parsed_json["titulo"],
        "descripcion_original": parsed_json["descripcion_original"],
        "actor": parsed_json["actor"],
        "funcionalidad": parsed_json["funcionalidad"],
        "objetivo": parsed_json["objetivo"],
        "criterios_aceptacion": parsed_json["criterios_aceptacion"],
        "restricciones": parsed_json["restricciones"],
        "seguridad": parsed_json.get("seguridad"),
        "observaciones": parsed_json["observaciones"],
        "prioridad": parsed_json["prioridad"],
        "validacion_entrada": parsed_json["validacion_entrada"],
    }
    logger.info(
        "MAPPER_DIAGNOSTICO\n%s",
        json.dumps(diagnostic_payload, ensure_ascii=False, indent=2),
    )
    story_fields = ("actor", "funcionalidad", "objetivo")
    identified_fields = {
        field: _texto_identificado(parsed_json.get(field))
        for field in story_fields
    }
    logger.info(
        "VALIDACION_ENTRADA\n%s",
        json.dumps(
            {
                "issue_iid": parsed_json["id"],
                "campos_actor_accion_objetivo_identificados": identified_fields,
                "condicion_sin_actor_accion_objetivo": not any(identified_fields.values()),
                "resultado": parsed_json["validacion_entrada"],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    
    return parsed_json

def preparar_payload_central(issue_data: dict) -> dict:
    return {
        "issue_iid": issue_data["issue_iid"],
        "historia_id": issue_data.get("historia_id", ""),
        "titulo": issue_data.get("titulo", ""),
        "actor": issue_data.get("actor", ""),
        "funcionalidad": issue_data.get("funcionalidad", ""),
        "objetivo": issue_data.get("objetivo", ""),
        "criterios_aceptacion": issue_data.get(
            "criterios_aceptacion", []
        ),
        "restricciones": issue_data.get("restricciones", []),
        "seguridad": issue_data.get("seguridad", {}),
        "prioridad": issue_data.get("prioridad", ""),
        "observaciones": issue_data.get("observaciones", ""),
        "validacion_entrada": issue_data.get(
            "validacion_entrada", {}
        ),
    }
