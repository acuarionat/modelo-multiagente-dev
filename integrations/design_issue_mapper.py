import re


VALORES_DESCONOCIDOS = {
    "", "desconocido", "desconocida", "n/a", "no especificado",
    "sin información", "ninguna", "ninguna.", "ninguno", "ninguno.",
}


def _extraer_seccion(description_text: str, header: str) -> str:
    # La plantilla DIS-xxx numera los encabezados ("## 1. ...", "### 5.1 ...");
    # el prefijo numérico es opcional para tolerar encabezados sin numerar.
    escaped_header = re.escape(header)
    pattern = (
        rf"^\s*#{{1,6}}\s*(?:\d+(?:\.\d+)*\.?\s*)?{escaped_header}"
        rf"\s*:?[ \t]*(.*?)(?=^\s*#{{1,6}}\s+|\Z)"
    )
    match = re.search(pattern, description_text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not match:
        return ""
    lines = [
        line for line in match.group(1).strip().splitlines()
        if not re.fullmatch(r"\s*-{3,}\s*", line)
    ]
    return "\n".join(lines).strip()


def _extraer_lista(text: str) -> list:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"-{3,}", line):
            continue
        clean_item = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s*)", "", line).strip()
        if not clean_item or clean_item.casefold() in VALORES_DESCONOCIDOS:
            continue
        items.append(clean_item)
    return items


def _es_fila_separadora(celdas: list) -> bool:
    return bool(celdas) and all(re.fullmatch(r":?-{2,}:?", celda) for celda in celdas)


def _parsear_tabla_markdown(text: str) -> list:
    filas_datos = []
    encabezado_visto = False
    for linea in text.splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue
        celdas = [celda.strip() for celda in linea.strip("|").split("|")]
        if _es_fila_separadora(celdas):
            encabezado_visto = True
            continue
        if not encabezado_visto:
            continue
        filas_datos.append(celdas)
    return filas_datos


def _extraer_elementos_diseno(text: str) -> list:
    elementos = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 4:
            continue
        elementos.append({
            "elemento_id": celdas[0],
            "nombre": celdas[1],
            "tipo": celdas[2],
            "responsabilidad": celdas[3],
        })
    return elementos


def _extraer_relaciones(text: str) -> list:
    relaciones = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 4:
            continue
        relaciones.append({
            "origen": celdas[0],
            "destino": celdas[1],
            "tipo": celdas[2],
            "descripcion": celdas[3],
        })
    return relaciones


def _texto_es_afirmativo(value: str) -> bool:
    return value.strip().casefold().rstrip(".") in {"sí", "si"}


def _extraer_amenazas(text: str) -> list:
    amenazas = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 4:
            continue
        elementos_afectados = [
            item.strip() for item in celdas[1].split(",") if item.strip()
        ]
        amenazas.append({
            "amenaza": celdas[0],
            "elementos_afectados": elementos_afectados,
            "tratamiento_definido": _texto_es_afirmativo(celdas[2]),
            "tratamiento": celdas[3],
        })
    return amenazas


def _extraer_medidas_seguridad(text: str) -> list:
    medidas = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 3:
            continue
        medidas.append({
            "aspecto": celdas[0],
            "medida": celdas[1],
            "elemento_responsable": celdas[2],
        })
    return medidas


def mapear_issue_diseno(issue) -> dict:
    """
    Convierte la descripción Markdown de un Issue DIS-xxx en un diccionario
    estructurado. No evalúa, no calcula métricas, no detecta gaps.
    """
    description_text = issue.description or ""

    diseno_match = re.search(r"\bDIS\s*[-_ ]\s*(\d+)\b", issue.title, re.IGNORECASE)
    diseno_id = f"DIS-{int(diseno_match.group(1)):03d}" if diseno_match else ""

    seccion_requerimientos = _extraer_seccion(description_text, "Requerimientos relacionados")
    seccion_elementos = _extraer_seccion(description_text, "Elementos principales del diseño")
    seccion_relaciones = _extraer_seccion(description_text, "Relaciones entre elementos")
    seccion_amenazas = _extraer_seccion(description_text, "Amenazas o situaciones de riesgo identificadas")
    seccion_medidas = _extraer_seccion(description_text, "Medidas de seguridad previstas")
    seccion_restricciones = _extraer_seccion(description_text, "Restricciones del diseño")
    seccion_decisiones = _extraer_seccion(description_text, "Decisiones importantes de diseño")
    seccion_observaciones = _extraer_seccion(description_text, "Observaciones adicionales")

    return {
        "id": str(issue.iid),
        "issue_iid": int(issue.iid),
        "diseno_id": diseno_id,
        "titulo": issue.title,

        "requerimientos_relacionados": _extraer_lista(seccion_requerimientos),

        "descripcion_general": _extraer_seccion(description_text, "Descripción general del diseño"),

        "elementos_diseno": _extraer_elementos_diseno(seccion_elementos),

        "relaciones": _extraer_relaciones(seccion_relaciones),

        "seguridad": {
            "amenazas": _extraer_amenazas(seccion_amenazas),
            "medidas_seguridad": _extraer_medidas_seguridad(seccion_medidas),
        },

        "restricciones": _extraer_lista(seccion_restricciones),
        "decisiones_diseno": _extraer_lista(seccion_decisiones),
        "observaciones": _extraer_lista(seccion_observaciones),

        "labels": issue.labels,

        "validacion_entrada": {
            "estado": "",
            "campos_faltantes": [],
            "advertencias": [],
        },
    }
