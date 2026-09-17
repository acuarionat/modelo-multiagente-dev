"""
Matriz de trazabilidad evolucionada de Codificación: extiende la matriz de
Diseño heredada (HU → RF/RNF → DIS → ED) con la relación real de
implementación (→ COD), a partir del resultado ya validado del Central de
Codificación. No recalcula métricas, no inventa relaciones: solo organiza
lo que el Central ya determinó.
"""

from datetime import datetime

ESTADOS_IMPLEMENTACION_CODIFICACION = {
    "IMPLEMENTADO",
    "NO_CONFIRMADO",
    "NO_EVALUADO",
}

ETIQUETAS_ESTADO_IMPLEMENTACION = {
    "IMPLEMENTADO": "Implementado en Codificación",
    "NO_CONFIRMADO": "Declarado sin confirmar en el código",
    "NO_EVALUADO": "No evaluado",
}

_OBSERVACION_POR_ESTADO = {
    "IMPLEMENTADO": "El Central de Codificación confirmó evidencia real de implementación en el código.",
    "NO_CONFIRMADO": "El COD declara este elemento, pero el código disponible no sustenta su implementación.",
    "NO_EVALUADO": "Ningún Issue de Codificación evaluado hace referencia a este elemento de Diseño.",
}


def _indexar_elementos_por_cod(resultados_central_codificacion: list) -> dict:
    """ED-xx -> lista de relaciones de implementación, una por cada COD que lo referencia."""
    fecha = datetime.now().strftime("%Y-%m-%d")
    indice = {}

    for resultado in resultados_central_codificacion:
        codificacion_id = resultado.get("codificacion_id")
        issue_iid = resultado.get("issue_iid")
        archivos_por_elemento = {}
        for archivo in resultado.get("archivos_consolidados") or []:
            ruta = archivo.get("ruta")
            for elemento_id in archivo.get("elementos_diseno_implementados") or []:
                archivos_por_elemento.setdefault(elemento_id, []).append(ruta)

        for elemento_id in resultado.get("elementos_implementados") or []:
            indice.setdefault(elemento_id, []).append({
                "codificacion_id": codificacion_id,
                "issue_iid": issue_iid,
                "estado": "IMPLEMENTADO",
                "ubicacion_implementacion": archivos_por_elemento.get(elemento_id, []),
                "procedencia": "central_codificacion",
                "fecha": fecha,
            })

        for elemento_id in resultado.get("elementos_no_confirmados") or []:
            indice.setdefault(elemento_id, []).append({
                "codificacion_id": codificacion_id,
                "issue_iid": issue_iid,
                "estado": "NO_CONFIRMADO",
                "ubicacion_implementacion": archivos_por_elemento.get(elemento_id, []),
                "procedencia": "central_codificacion",
                "fecha": fecha,
            })

    return indice


def construir_filas_matriz_codificacion(
    matriz_diseno_entrada: list,
    resultados_central_codificacion: list,
    evaluacion_por_cod: dict,
) -> list:
    """
    Extiende cada fila de la matriz de Diseño heredada
    (HU → RF/RNF → DIS → ED) con la relación real de Codificación (→ COD),
    produciendo filas tabulares planas y comprensibles para una persona.
    """
    indice_elementos = _indexar_elementos_por_cod(resultados_central_codificacion)
    filas = []

    for fila_diseno in matriz_diseno_entrada:
        texto_elementos = str(fila_diseno.get("Elementos de Diseño") or "").strip()
        elementos = [e.strip() for e in texto_elementos.split(",") if e.strip()] if texto_elementos and texto_elementos != "—" else []

        if not elementos:
            filas.append({
                **fila_diseno,
                "Codificación": "—",
                "Estado de implementación": ETIQUETAS_ESTADO_IMPLEMENTACION["NO_EVALUADO"],
                "Ubicación de implementación": "—",
                "Estado de Codificación": "—",
                "Observación de Codificación": "Esta fila de Diseño no declara elementos de diseño evaluables.",
            })
            continue

        for elemento_id in elementos:
            # "Elementos de Diseño" se estrecha a este único elemento_id (en
            # vez de conservar la lista completa heredada de fila_diseno):
            # cada fila que sigue describe la implementación de ESTE elemento
            # específico, no de todos los que declaraba la fila de Diseño
            # original. Sin esto, dos filas de un mismo fila_diseno con
            # elementos y estados distintos (p. ej. ED-01 implementado y
            # ED-02 sin confirmar) mostrarían la misma lista "ED-01, ED-02"
            # en ambas, sin forma de saber a cuál se refiere cada una.
            relaciones = indice_elementos.get(elemento_id)
            if not relaciones:
                filas.append({
                    **fila_diseno,
                    "Elementos de Diseño": elemento_id,
                    "Codificación": "—",
                    "Estado de implementación": ETIQUETAS_ESTADO_IMPLEMENTACION["NO_EVALUADO"],
                    "Ubicación de implementación": "—",
                    "Estado de Codificación": "—",
                    "Observación de Codificación": _OBSERVACION_POR_ESTADO["NO_EVALUADO"],
                })
                continue

            for relacion in relaciones:
                estado = relacion["estado"]
                ubicacion = ", ".join(relacion["ubicacion_implementacion"]) or "—"
                codificacion_id = relacion["codificacion_id"]
                filas.append({
                    **fila_diseno,
                    "Elementos de Diseño": elemento_id,
                    "Codificación": codificacion_id,
                    "Estado de implementación": ETIQUETAS_ESTADO_IMPLEMENTACION[estado],
                    "Ubicación de implementación": ubicacion,
                    "Estado de Codificación": evaluacion_por_cod.get(codificacion_id, "—"),
                    "Observación de Codificación": _OBSERVACION_POR_ESTADO[estado],
                })

    return filas


_PRIORIDAD_ESTADO_IMPLEMENTACION = {
    ETIQUETAS_ESTADO_IMPLEMENTACION["IMPLEMENTADO"]: 3,
    ETIQUETAS_ESTADO_IMPLEMENTACION["NO_CONFIRMADO"]: 2,
    ETIQUETAS_ESTADO_IMPLEMENTACION["NO_EVALUADO"]: 1,
}


def resumir_trazabilidad_codificacion(filas: list) -> dict:
    """Resumen determinístico de la matriz evolucionada de Codificación.

    Cuenta por par (Diseño, Elemento) único, no por fila: la matriz heredada
    repite el mismo par en varias filas cuando más de un requisito comparte
    el mismo Diseño, o cuando más de una Codificación lo referencia. Sin esta
    deduplicación, "implementados" (conteo de filas) podía superar a
    "elementos_diseno_totales" (conteo de pares únicos), produciendo
    porcentajes sin sentido (>100 %). Cuando un mismo par aparece con más de
    un estado (p. ej. implementado por una Codificación y sin confirmar por
    otra), se queda con la evidencia más fuerte: Implementado > Declarado sin
    confirmar > No evaluado.
    """
    estado_por_par = {}
    for fila in filas:
        elemento = str(fila.get("Elementos de Diseño") or "").strip()
        if not elemento or elemento == "—":
            continue
        par = (fila.get("Diseño"), elemento)
        estado_fila = fila.get("Estado de implementación")
        actual = estado_por_par.get(par)
        if actual is None or _PRIORIDAD_ESTADO_IMPLEMENTACION.get(estado_fila, 0) > _PRIORIDAD_ESTADO_IMPLEMENTACION.get(actual, 0):
            estado_por_par[par] = estado_fila

    implementados = sum(
        1 for estado in estado_por_par.values() if estado == ETIQUETAS_ESTADO_IMPLEMENTACION["IMPLEMENTADO"]
    )
    no_confirmados = sum(
        1 for estado in estado_por_par.values() if estado == ETIQUETAS_ESTADO_IMPLEMENTACION["NO_CONFIRMADO"]
    )
    no_evaluados = sum(
        1 for estado in estado_por_par.values() if estado == ETIQUETAS_ESTADO_IMPLEMENTACION["NO_EVALUADO"]
    )

    return {
        "elementos_diseno_totales": len(estado_por_par),
        "implementados": implementados,
        "no_confirmados": no_confirmados,
        "no_evaluados": no_evaluados,
    }


def construir_metadata_matriz_codificacion(filas: list, version_anterior: str = "3.0") -> dict:
    """Envuelve la matriz visible con la metadata de versión de la etapa de Codificación."""
    return {
        "version": "4.0",
        "etapa": "Codificación",
        "version_anterior": version_anterior,
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d"),
        "filas": filas,
    }
