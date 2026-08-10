import re

from core.utils import TRACEABILITY_COLUMNS


def _limpiar_celda(valor) -> str:
    texto = str(valor or "").strip()
    texto = texto.replace("|", "-")
    return " ".join(texto.splitlines())


def construir_markdown_matriz_trazabilidad(filas_oficiales: list, metadata: dict = None) -> str:
    """
    Construye el cuerpo Markdown del Issue TRZ-001 a partir de las filas
    OFICIALES ya construidas por core.utils.construir_filas_matriz_requerimientos_final
    (las mismas que alimentan CSV/XLSX). No calcula ni reconstruye nada.
    """
    encabezado = "| " + " | ".join(TRACEABILITY_COLUMNS) + " |"
    separador = "|" + "|".join(["---"] * len(TRACEABILITY_COLUMNS)) + "|"
    lineas = ["# TRZ-001 - Matriz de Trazabilidad", ""]
    if metadata:
        lineas += [
            f"_Ejecución: {metadata.get('execution_id', 'No informado')} — "
            f"Milestone: {metadata.get('milestone', 'No informado')} — "
            f"Generado: {metadata.get('generated_at', 'No informado')}._",
            "",
        ]
    lineas += [
        "Esta Matriz de Trazabilidad refleja los requerimientos formalizados "
        "por la ejecución más reciente de Recepción de Requerimientos. Puede "
        "editarse directamente en este Issue —agregar, modificar o retirar "
        "filas— antes de iniciar la etapa de Diseño.",
        "",
        "## Requerimientos",
        "",
        encabezado,
        separador,
    ]
    for fila in filas_oficiales:
        celdas = [_limpiar_celda(fila.get(columna, "")) for columna in TRACEABILITY_COLUMNS]
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


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


def mapear_matriz_trazabilidad(issue) -> list:
    """
    Parsea el Issue TRZ-001 (Markdown real, tal como pudo haber sido editado
    manualmente en GitLab) al mismo contrato oficial de 7 columnas
    (TRACEABILITY_COLUMNS) que produce construir_filas_matriz_requerimientos_final.
    No evalúa ni valida nada; no renumera.
    """
    description_text = issue.description or ""
    filas = []
    for celdas in _parsear_tabla_markdown(description_text):
        if len(celdas) < len(TRACEABILITY_COLUMNS):
            continue
        filas.append(dict(zip(TRACEABILITY_COLUMNS, celdas)))
    return filas
