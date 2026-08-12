import html


TESTING_TRACEABILITY_COLUMNS = [
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
    "Codificación",
    "Estado de implementación",
    "Ubicación de implementación",
    "Estado de Codificación",
    "Observación de Codificación",
    "Pruebas",
    "Estado de Pruebas",
    "Observación de Pruebas",
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


def construir_markdown_matriz_trazabilidad_pruebas(filas: list) -> str:
    encabezado = "| " + " | ".join(TESTING_TRACEABILITY_COLUMNS) + " |"
    separador = "|" + "|".join(["---"] * len(TESTING_TRACEABILITY_COLUMNS)) + "|"
    lineas = [
        "# Matriz de Trazabilidad — Etapa Pruebas",
        "",
        "Esta matriz refleja la trazabilidad alcanzada al finalizar la etapa de Pruebas:",
        "HU → RF/RNF → ED → COD → PRU → Resultado.",
        "",
        "## Matriz de trazabilidad",
        "",
        encabezado,
        separador,
    ]
    for fila in filas:
        celdas = [_serializar_celda(fila.get(columna, "")) for columna in TESTING_TRACEABILITY_COLUMNS]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def mapear_matriz_trazabilidad_pruebas(markdown: str) -> list:
    filas = []
    encabezado_encontrado = False

    for linea in (markdown or "").splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue

        celdas = [celda.strip() for celda in linea.strip("|").split("|")]
        if celdas == TESTING_TRACEABILITY_COLUMNS:
            encabezado_encontrado = True
            continue
        if not encabezado_encontrado:
            continue
        if len(celdas) == len(TESTING_TRACEABILITY_COLUMNS) and all(
            celda and set(celda.replace(":", "")) == {"-"} for celda in celdas
        ):
            continue
        if len(celdas) != len(TESTING_TRACEABILITY_COLUMNS):
            continue

        filas.append({
            columna: html.unescape(celda)
            for columna, celda in zip(TESTING_TRACEABILITY_COLUMNS, celdas)
        })

    return filas
