import html


DESIGN_TRACEABILITY_COLUMNS = [
    "HU origen",
    "Código requisito",
    "Tipo",
    "Nombre del requisito",
    "Descripción",
    "Diseño",
    "Elementos de Diseño",
    "Estado de trazabilidad",
    "Estado de Diseño",
    "Observación",
]


def _serializar_celda(valor) -> str:
    texto = "" if valor is None else str(valor)
    texto = html.escape(texto, quote=False)
    return (
        texto.replace("|", "&#124;")
        .replace("\r\n", "&#10;")
        .replace("\r", "&#10;")
        .replace("\n", "&#10;")
        .replace("\t", "&#9;")
        .replace(" ", "&#32;")
    )


def construir_markdown_matriz_trazabilidad_diseno(filas: list) -> str:
    """Convierte las filas finales de Diseño a Markdown sin recalcularlas."""
    encabezado = "| " + " | ".join(DESIGN_TRACEABILITY_COLUMNS) + " |"
    separador = "|" + "|".join(["---"] * len(DESIGN_TRACEABILITY_COLUMNS)) + "|"
    lineas = [
        "# Matriz de Trazabilidad — Etapa Diseño",
        "",
        "Esta matriz refleja la trazabilidad alcanzada al finalizar la etapa de Diseño",
        "y constituye la entrada de trazabilidad para la etapa de Codificación.",
        "",
        "Puede ser revisada y ajustada antes de iniciar el análisis de Codificación.",
        "",
        "## Matriz de trazabilidad",
        "",
        encabezado,
        separador,
    ]
    for fila in filas:
        celdas = [_serializar_celda(fila.get(columna, "")) for columna in DESIGN_TRACEABILITY_COLUMNS]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def mapear_matriz_trazabilidad_diseno(markdown: str) -> list:
    """Recupera desde Markdown el mismo contrato de 10 columnas de Diseño."""
    filas = []
    encabezado_encontrado = False

    for linea in (markdown or "").splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue

        celdas = [celda.strip() for celda in linea.strip("|").split("|")]
        if celdas == DESIGN_TRACEABILITY_COLUMNS:
            encabezado_encontrado = True
            continue
        if not encabezado_encontrado:
            continue
        if len(celdas) == len(DESIGN_TRACEABILITY_COLUMNS) and all(
            celda and set(celda.replace(":", "")) == {"-"} for celda in celdas
        ):
            continue
        if len(celdas) != len(DESIGN_TRACEABILITY_COLUMNS):
            continue

        filas.append({
            columna: html.unescape(celda)
            for columna, celda in zip(DESIGN_TRACEABILITY_COLUMNS, celdas)
        })

    return filas
