"""
Trazabilidad de Pruebas.

Fase previa a los agentes: resuelve, a partir de la Matriz de
Trazabilidad de Codificación ya evolucionada (TRZ-003, columnas
HU origen -> Código requisito -> ... -> Elementos de Diseño ->
Codificación -> Estado de implementación -> Estado de Codificación), la
cadena heredada que corresponde a cada COD-xxx declarado en un Issue
PRU-xxx. No vuelve a pedir HU/RF/RNF/ED al usuario: los reconstruye desde
la matriz ya existente. No evalúa, no calcula métricas.

La matriz evolucionada final de Pruebas (HU | RF/RNF | ED | COD | PRU |
Resultado) se construye más adelante, después del Evaluador, con
construir_filas_matriz_pruebas().
"""

from datetime import datetime


def extraer_codificaciones_validas(matriz_codificacion: list) -> set:
    """Universo de COD-xxx presentes en TRZ-003 (columna 'Codificación')."""
    validos = set()
    for fila in matriz_codificacion or []:
        codigo = str(fila.get("Codificación") or "").strip()
        if codigo and codigo != "—":
            validos.add(codigo)
    return validos


def resolver_trazabilidad_heredada(codificaciones_relacionadas: list, matriz_codificacion: list) -> dict:
    """
    Para cada COD-xxx declarado en el PRU, recupera las filas de TRZ-003
    donde la columna 'Codificación' coincide, reconstruyendo la cadena
    HU -> RF/RNF -> ED -> COD ya validada en etapas anteriores. Los COD
    declarados que no existen en la matriz se reportan por separado (no
    se descartan en silencio): la validación estructural decide qué
    hacer con ellos.
    """
    cadena_por_codificacion = {}
    codificaciones_no_encontradas = []

    for codificacion_id in codificaciones_relacionadas or []:
        filas = [
            fila for fila in (matriz_codificacion or [])
            if str(fila.get("Codificación") or "").strip() == codificacion_id
        ]
        if not filas:
            codificaciones_no_encontradas.append(codificacion_id)
            continue
        cadena_por_codificacion[codificacion_id] = [
            {
                "hu_origen": fila.get("HU origen"),
                "codigo_requisito": fila.get("Código requisito"),
                "tipo_requisito": fila.get("Tipo"),
                "nombre_requisito": fila.get("Nombre del requisito"),
                "elementos_diseno": fila.get("Elementos de Diseño"),
                "estado_implementacion": fila.get("Estado de implementación"),
                "ubicacion_implementacion": fila.get("Ubicación de implementación"),
                "estado_codificacion": fila.get("Estado de Codificación"),
            }
            for fila in filas
        ]

    return {
        "cadena_por_codificacion": cadena_por_codificacion,
        "codificaciones_no_encontradas": codificaciones_no_encontradas,
    }


# ============================================================
# Matriz evolucionada final de Pruebas (después del Evaluador)
# ============================================================

ETIQUETAS_ESTADO_PRUEBAS = {
    "APROBADO": "Verificado",
    "CORREGIR": "Fallo pendiente",
    "REVISAR": "Pendiente de revisión",
    "ERROR": "Error técnico",
}


def _indexar_resumenes_por_codificacion(testing_summaries: list) -> dict:
    """COD-xxx -> lista de {"prueba_id", "estado"} de cada PRU que lo evaluó."""
    indice = {}
    for resumen in testing_summaries or []:
        prueba_id = resumen.get("prueba_id")
        estado = resumen.get("estado_orientativo")
        for codificacion_id in resumen.get("codificaciones_relacionadas") or []:
            indice.setdefault(codificacion_id, []).append({"prueba_id": prueba_id, "estado": estado})
    return indice


def construir_filas_matriz_pruebas(matriz_codificacion_entrada: list, testing_summaries: list) -> list:
    """
    Extiende cada fila de la Matriz de Trazabilidad de Codificación
    (HU -> RF/RNF -> ED -> COD) con la relación real de Pruebas (-> PRU),
    produciendo filas tabulares planas HU -> RF/RNF -> ED -> COD -> PRU ->
    Resultado. Una Codificación evaluada por varios PRU genera una fila
    por cada PRU que la evaluó; el resultado se toma del estado
    orientativo de ese PRU, ya calculado en Python (core/testing_metrics.py
    ::determinar_estado_pruebas), nunca del LLM.

    Pruebas no distingue granularidad más fina que la Codificación: un
    Issue PRU declara qué COD evaluó, no qué ED/RF puntual de ese COD
    cubre cada caso de prueba, así que un mismo COD-xxx recibe el mismo
    resultado en todas sus filas ED/RF heredadas, aun si el PRU evaluó
    varias funcionalidades de ese COD con resultados distintos entre sí.
    """
    indice_pruebas = _indexar_resumenes_por_codificacion(testing_summaries)
    filas = []

    for fila_codificacion in matriz_codificacion_entrada:
        codificacion_id = str(fila_codificacion.get("Codificación") or "").strip()
        pruebas_relacionadas = (
            indice_pruebas.get(codificacion_id) if codificacion_id and codificacion_id != "—" else None
        )

        if not pruebas_relacionadas:
            filas.append({
                **fila_codificacion,
                "Pruebas": "—",
                "Estado de Pruebas": "—",
                "Observación de Pruebas": "Ningún Issue de Pruebas evaluado hace referencia a esta Codificación.",
            })
            continue

        for prueba in pruebas_relacionadas:
            etiqueta = ETIQUETAS_ESTADO_PRUEBAS.get(prueba["estado"], "—")
            filas.append({
                **fila_codificacion,
                "Pruebas": prueba["prueba_id"],
                "Estado de Pruebas": etiqueta,
                "Observación de Pruebas": f"Estado orientativo del PRU: {prueba['estado']}.",
            })

    return filas


# Orden de severidad: si una misma Codificación aparece en varias filas con
# resultados distintos (heredadas de varios RF/ED, o evaluada por más de un
# PRU), gana el resultado más desfavorable — cualquier fallo pendiente pesa
# más que una revisión pendiente, y ambos pesan más que "Verificado".
_PRIORIDAD_ESTADO_PRUEBAS = {
    "Fallo pendiente": 4,
    "Pendiente de revisión": 3,
    "Error técnico": 2,
    "Verificado": 1,
}


def resumir_trazabilidad_pruebas(filas: list) -> dict:
    """Resumen determinístico de la matriz evolucionada de Pruebas.

    Cuenta por Codificación única, no por fila: la matriz heredada repite la
    misma Codificación en varias filas (una por cada RF/ED que implementa) y,
    si más de un Issue de Pruebas la evaluó, una fila adicional por cada PRU.
    Sin esta deduplicación, "verificadas"/"con_fallo_pendiente" (conteo de
    filas) podían superar a "codificaciones_totales" (conteo de
    Codificaciones únicas), produciendo porcentajes sin sentido (>100 %).
    """
    estado_por_codificacion = {}
    for fila in filas:
        codificacion_id = str(fila.get("Codificación") or "").strip()
        if codificacion_id in ("", "—"):
            continue
        estado_fila = fila.get("Estado de Pruebas")
        actual = estado_por_codificacion.get(codificacion_id)
        if actual is None or _PRIORIDAD_ESTADO_PRUEBAS.get(estado_fila, 0) > _PRIORIDAD_ESTADO_PRUEBAS.get(actual, 0):
            estado_por_codificacion[codificacion_id] = estado_fila

    verificadas = sum(1 for estado in estado_por_codificacion.values() if estado == "Verificado")
    con_fallo_pendiente = sum(1 for estado in estado_por_codificacion.values() if estado == "Fallo pendiente")
    pendientes_revision = sum(1 for estado in estado_por_codificacion.values() if estado == "Pendiente de revisión")
    no_evaluadas = sum(1 for estado in estado_por_codificacion.values() if estado == "—")

    return {
        "codificaciones_totales": len(estado_por_codificacion),
        "verificadas": verificadas,
        "con_fallo_pendiente": con_fallo_pendiente,
        "pendientes_revision": pendientes_revision,
        "no_evaluadas": no_evaluadas,
    }


def construir_metadata_matriz_pruebas(filas: list, version_anterior: str = "4.0") -> dict:
    """Envuelve la matriz visible con la metadata de versión de la etapa de Pruebas."""
    return {
        "version": "5.0",
        "etapa": "Pruebas",
        "version_anterior": version_anterior,
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d"),
        "filas": filas,
    }
