import re

VALORES_DESCONOCIDOS = {
    "", "desconocido", "desconocida", "n/a", "no especificado",
    "sin información", "ninguna", "ninguna.", "ninguno", "ninguno.",
}


def _extraer_seccion(description_text: str, header: str) -> str:
    # La plantilla COD-xxx numera los encabezados ("## 1. ...", "### 3.1 ...");
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


def _limpiar_codigo_inline(texto: str) -> str:
    valor = str(texto or "").strip()

    if len(valor) >= 2 and valor.startswith("`") and valor.endswith("`"):
        valor = valor[1:-1].strip()

    return valor


def _extraer_archivos_declarados(text: str) -> list:
    archivos = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 2:
            continue
        ruta = _limpiar_codigo_inline(celdas[0])
        if not ruta or ruta.casefold() in VALORES_DESCONOCIDOS:
            continue
        archivos.append({
            "ruta": ruta,
            "descripcion": celdas[1].strip(),
        })
    return archivos


def mapear_issue_codificacion(issue) -> dict:
    """
    Convierte la descripción Markdown de un Issue COD-xxx en un diccionario
    estructurado. No evalúa, no calcula métricas, no construye relaciones
    RF/RNF/DIS: eso corresponde a core/coding_contract.py y al Agente Central
    de Codificación, no a este mapper.
    """
    description_text = issue.description or ""

    cod_match = re.search(r"\bCOD\s*[-_ ]\s*(\d+)\b", issue.title, re.IGNORECASE)
    codificacion_id = f"COD-{int(cod_match.group(1)):03d}" if cod_match else ""

    seccion_elementos = _extraer_seccion(description_text, "Elementos de Diseño implementados")
    seccion_ubicacion = _extraer_seccion(description_text, "Ubicación de la implementación")
    seccion_decisiones = _extraer_seccion(description_text, "Decisiones de implementación")
    seccion_observaciones = _extraer_seccion(description_text, "Observaciones")

    return {
        "id": str(issue.iid),
        "issue_iid": int(issue.iid),
        "codificacion_id": codificacion_id,
        "titulo": issue.title,

        "descripcion": _extraer_seccion(description_text, "Descripción de la implementación"),

        "elementos_diseno_declarados": _extraer_lista(seccion_elementos),

        "archivos_declarados": _extraer_archivos_declarados(seccion_ubicacion),

        "decisiones": _extraer_lista(seccion_decisiones),
        "observaciones": _extraer_lista(seccion_observaciones),

        "labels": issue.labels,

        "validacion_entrada": {
            "estado": "",
            "campos_faltantes": [],
            "advertencias": [],
        },
    }
