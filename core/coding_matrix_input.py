"""
Validación y versionado de la Matriz de Diseño evolucionada como entrada de
Codificación. Todo el cómputo aquí es determinístico y local: no invoca LLM
ni GitLab. Trabaja siempre sobre filas ya producidas por
core/design_traceability.py::construir_filas_matriz_diseno (mismo contrato:
"HU origen", "Código requisito", "Tipo", "Nombre del requisito",
"Descripción", "Diseño", "Elementos de Diseño", "Estado de trazabilidad",
"Estado de Diseño", "Observación").

No reutiliza el estado interno de Diseño (matriz_entrada_diseno,
matriz_estado, etc.): produce estructuras específicas de Codificación
(coding_matrix_input, coding_matrix_status, coding_matrix_source,
coding_matrix_version, coding_matrix_changes, coding_matrix_snapshot).
"""

from datetime import datetime

ESTADO_MATRIZ_ORIGINAL = "ORIGINAL"
ESTADO_MATRIZ_EDITADA = "EDITADA"
ESTADO_MATRIZ_INVALIDA = "INVALIDA"

ESTADOS_MATRIZ_VALIDOS = {ESTADO_MATRIZ_ORIGINAL, ESTADO_MATRIZ_EDITADA, ESTADO_MATRIZ_INVALIDA}

_COLUMNAS_REQUERIDAS = (
    "Código requisito", "Diseño", "Elementos de Diseño", "Estado de trazabilidad",
)


def extraer_elementos_diseno_validos(matriz_entrada: list) -> set:
    """
    Extrae el universo de ED-xx presentes en la matriz de Diseño heredada.
    La columna "Elementos de Diseño" es texto plano ("ED-01, ED-02" o "—"),
    tal como la produce construir_filas_matriz_diseno.
    """
    validos = set()
    for fila in matriz_entrada:
        texto = str(fila.get("Elementos de Diseño") or "").strip()
        if not texto or texto == "—":
            continue
        for elemento_id in texto.split(","):
            elemento_id = elemento_id.strip()
            if elemento_id:
                validos.add(elemento_id)
    return validos


def _validar_estructura_matriz(matriz_entrada: list) -> list:
    errores = []
    if not matriz_entrada:
        errores.append("La matriz de Diseño heredada no contiene filas.")
        return errores
    for fila in matriz_entrada:
        for columna in _COLUMNAS_REQUERIDAS:
            if columna not in fila:
                errores.append(f"Fila sin columna requerida: {columna!r}.")
                break
    return errores


def _clave_fila(fila: dict) -> tuple:
    return (str(fila.get("Código requisito") or ""), str(fila.get("Diseño") or ""))


def comparar_matrices_diseno(matriz_original: list, matriz_entrada: list) -> dict:
    """
    Compara dos matrices de Diseño ya normalizadas y detecta agregados,
    modificados y retirados. La clave es (Código requisito, Diseño), porque
    un mismo requisito puede tener varias relaciones de Diseño. No decide
    ningún estado: solo reporta diferencias.
    """
    original_por_clave = {_clave_fila(fila): fila for fila in matriz_original}
    entrada_por_clave = {_clave_fila(fila): fila for fila in matriz_entrada}

    claves_original = set(original_por_clave)
    claves_entrada = set(entrada_por_clave)

    agregados = sorted(claves_entrada - claves_original)
    retirados = sorted(claves_original - claves_entrada)

    campos_comparables = ("Elementos de Diseño", "Estado de trazabilidad", "Estado de Diseño")
    modificados = []
    for clave in sorted(claves_entrada & claves_original):
        fila_original = original_por_clave[clave]
        fila_entrada = entrada_por_clave[clave]
        cambios_campo = []
        for campo in campos_comparables:
            valor_original = str(fila_original.get(campo) or "").strip()
            valor_entrada = str(fila_entrada.get(campo) or "").strip()
            if valor_original != valor_entrada:
                cambios_campo.append({
                    "campo": campo,
                    "valor_anterior": valor_original,
                    "valor_vigente": valor_entrada,
                })
        if cambios_campo:
            modificados.append({
                "codigo_requisito": clave[0], "diseno": clave[1], "cambios": cambios_campo,
            })

    return {
        "agregados": [{"codigo_requisito": clave[0], "diseno": clave[1]} for clave in agregados],
        "modificados": modificados,
        "retirados": [{"codigo_requisito": clave[0], "diseno": clave[1]} for clave in retirados],
        "errores_estructura": _validar_estructura_matriz(matriz_entrada),
        "hay_cambios": bool(agregados or modificados or retirados),
    }


def preparar_matriz_entrada_codificacion(matriz_original: list, matriz_entrada: list, fuente: str) -> dict:
    """
    Orquesta, sin recalcular nada por sí misma: valida → compara → determina
    el estado ORIGINAL/EDITADA/INVALIDA de la matriz de Diseño heredada como
    entrada de Codificación. Devuelve exactamente las estructuras
    específicas de Codificación (no reutiliza las de Diseño).
    """
    comparacion = comparar_matrices_diseno(matriz_original, matriz_entrada)
    errores_estructura = comparacion["errores_estructura"]

    if errores_estructura:
        estado = ESTADO_MATRIZ_INVALIDA
    elif comparacion["hay_cambios"]:
        estado = ESTADO_MATRIZ_EDITADA
    else:
        estado = ESTADO_MATRIZ_ORIGINAL

    return {
        "coding_matrix_input": matriz_entrada,
        "coding_matrix_status": estado,
        "coding_matrix_source": fuente,
        "coding_matrix_version": "3.0",
        "coding_matrix_changes": comparacion,
        "elementos_diseno_validos": sorted(extraer_elementos_diseno_validos(matriz_entrada)),
    }


def construir_snapshot_matriz_codificacion(matriz_entrada: list, version_anterior: str = "2.0") -> dict:
    """Envuelve la matriz vigente con metadata de versión antes de comenzar Codificación (coding_matrix_snapshot)."""
    return {
        "version": "3.0",
        "etapa": "Codificación",
        "version_anterior": version_anterior,
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d"),
        "filas": matriz_entrada,
    }
