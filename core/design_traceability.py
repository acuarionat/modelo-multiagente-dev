from datetime import datetime

from core.design_context import normalizar_fila_trazabilidad

ESTADOS_TRAZABILIDAD_DISENO = {
    "CUBIERTO",
    "PENDIENTE_RELACION",
    "REQUIERE_REVISION",
    "NO_EVALUADO",
}

ETIQUETAS_ESTADO = {
    "CUBIERTO": "Cubierto en Diseño",
    "PENDIENTE_RELACION": "Pendiente de relación",
    "REQUIERE_REVISION": "Requiere revisión",
    "NO_EVALUADO": "No evaluado",
}

_OBSERVACION_POR_CODIGO = {
    "CUBIERTO": "Relación identificada con evidencia suficiente.",
    "PENDIENTE_RELACION": "No se identificó evidencia suficiente para asociarlo a un elemento de diseño.",
    "REQUIERE_REVISION": "Relación identificada con confianza insuficiente para confirmarla.",
    "NO_EVALUADO": "No se evaluó este requisito en ningún Issue de Diseño.",
}


def _determinar_estado_trazabilidad(estado_central: str, confianza) -> str:
    """Clasifica una relación en uno de los códigos cerrados de ESTADOS_TRAZABILIDAD_DISENO. El LLM no decide el texto visible."""
    if estado_central == "sin_relacion_evidente":
        return "PENDIENTE_RELACION"
    if estado_central == "relacionado":
        if str(confianza or "").casefold() == "alta":
            return "CUBIERTO"
        return "REQUIERE_REVISION"
    return "NO_EVALUADO"


def normalizar_matriz_requerimientos(matriz_trazabilidad: list) -> list:
    """Normaliza las filas crudas del CSV de Requerimientos sin alterar sus valores."""
    return [normalizar_fila_trazabilidad(row) for row in matriz_trazabilidad]


def evolucionar_matriz_a_diseno(matriz_normalizada: list, resultados_central_diseno: list) -> list:
    """
    Produce la estructura interna de trazabilidad de Diseño: por cada requisito
    de la matriz de Requerimientos, agrega sus relaciones técnicas con Issues
    de Diseño (DIS) y Elementos de Diseño (ED) ya calculadas por el Central de
    Diseño. Conserva todos los datos originales del requisito sin reescribirlos.
    """
    fecha = datetime.now().strftime("%Y-%m-%d")
    estructura = []

    for fila in matriz_normalizada:
        codigo_requisito = fila.get("codigo")
        relaciones_diseno = []

        for resultado_dis in resultados_central_diseno:
            diseno_id = resultado_dis.get("diseno_id")
            issue_iid = resultado_dis.get("issue_iid")

            for item in resultado_dis.get("trazabilidad_diseno") or []:
                if item.get("requisito") != codigo_requisito:
                    continue
                confianza = item.get("confianza")
                justificacion = item.get("justificacion")
                elementos = [
                    {
                        "elemento_id": elemento_id,
                        "confianza": confianza,
                        "justificacion": justificacion,
                    }
                    for elemento_id in item.get("elementos_relacionados") or []
                ]
                relaciones_diseno.append({
                    "diseno_id": diseno_id,
                    "issue_iid": issue_iid,
                    "elementos": elementos,
                    "estado": "relacionado",
                    "confianza": confianza,
                    "justificacion": justificacion,
                    "procedencia": "central_diseno",
                    "fecha": fecha,
                })

            for item in resultado_dis.get("requisitos_sin_relacion_evidente") or []:
                if item.get("requisito") != codigo_requisito:
                    continue
                relaciones_diseno.append({
                    "diseno_id": diseno_id,
                    "issue_iid": issue_iid,
                    "elementos": [],
                    "estado": "sin_relacion_evidente",
                    "confianza": item.get("confianza"),
                    "justificacion": item.get("justificacion"),
                    "procedencia": "central_diseno",
                    "fecha": fecha,
                })

        requisito = {
            "codigo_requisito": codigo_requisito,
            "nombre_requisito": fila.get("nombre"),
            "descripcion_requisito": fila.get("descripcion"),
            "tipo_requisito": fila.get("tipo"),
            "historia_origen": fila.get("historia_origen"),
            "relaciones_diseno": relaciones_diseno,
        }

        # Protección de datos originales: Diseño agrega trazabilidad, no reescribe Requerimientos.
        assert requisito["codigo_requisito"] == fila.get("codigo")
        assert requisito["descripcion_requisito"] == fila.get("descripcion")
        assert requisito["historia_origen"] == fila.get("historia_origen")

        estructura.append(requisito)

    return estructura


def construir_filas_matriz_diseno(estructura_interna: list, evaluacion_por_diseno: dict) -> list:
    """
    Transforma la estructura interna en filas tabulares planas y comprensibles
    para una persona. No incluye estructuras anidadas (JSON) ni la confianza
    como columna: solo los nombres cerrados de ESTADOS_TRAZABILIDAD_DISENO.
    """
    filas = []

    for requisito in estructura_interna:
        relaciones = requisito.get("relaciones_diseno") or []

        if not relaciones:
            codigo_estado = "NO_EVALUADO"
            filas.append({
                "HU origen": requisito.get("historia_origen"),
                "Código requisito": requisito.get("codigo_requisito"),
                "Tipo": requisito.get("tipo_requisito"),
                "Nombre del requisito": requisito.get("nombre_requisito"),
                "Descripción": requisito.get("descripcion_requisito"),
                "Diseño": "—",
                "Elementos de Diseño": "—",
                "Estado de trazabilidad": ETIQUETAS_ESTADO[codigo_estado],
                "Estado de Diseño": "—",
                "Observación": _OBSERVACION_POR_CODIGO[codigo_estado],
            })
            continue

        for relacion in relaciones:
            codigo_estado = _determinar_estado_trazabilidad(relacion.get("estado"), relacion.get("confianza"))
            elementos = relacion.get("elementos") or []
            elementos_texto = ", ".join(
                elemento.get("elemento_id") for elemento in elementos
            ) if elementos else "—"
            diseno_id = relacion.get("diseno_id")

            filas.append({
                "HU origen": requisito.get("historia_origen"),
                "Código requisito": requisito.get("codigo_requisito"),
                "Tipo": requisito.get("tipo_requisito"),
                "Nombre del requisito": requisito.get("nombre_requisito"),
                "Descripción": requisito.get("descripcion_requisito"),
                "Diseño": diseno_id,
                "Elementos de Diseño": elementos_texto,
                "Estado de trazabilidad": ETIQUETAS_ESTADO[codigo_estado],
                "Estado de Diseño": evaluacion_por_diseno.get(diseno_id, "—"),
                "Observación": _OBSERVACION_POR_CODIGO[codigo_estado],
            })

    return filas


# Evidencia más fuerte entre las filas de un mismo requisito (varios Diseños pueden referirlo).
_PRIORIDAD_ESTADO_TRAZABILIDAD = {
    ETIQUETAS_ESTADO["CUBIERTO"]: 4,
    ETIQUETAS_ESTADO["REQUIERE_REVISION"]: 3,
    ETIQUETAS_ESTADO["PENDIENTE_RELACION"]: 2,
    ETIQUETAS_ESTADO["NO_EVALUADO"]: 1,
}


def resumir_trazabilidad_diseno(filas: list) -> dict:
    """Resumen determinístico de la matriz visible; no repite los índices de Calidad/Seguridad (pertenecen al DIS, no al RF).

    Cuenta por requisito único, no por fila: la matriz repite un requisito en varias filas
    cuando más de un Diseño (o más de una relación) lo referencia. Sin esta deduplicación,
    "cubiertos" (conteo de filas) no era comparable con "requisitos_totales" (conteo de
    requisitos únicos) y los porcentajes no coincidían. Cuando un mismo requisito aparece con
    más de un estado se queda con la evidencia más fuerte: Cubierto > Requiere revisión >
    Pendiente de relación > No evaluado."""
    estado_por_requisito = {}
    for fila in filas:
        codigo = fila["Código requisito"]
        estado_fila = fila["Estado de trazabilidad"]
        actual = estado_por_requisito.get(codigo)
        if actual is None or _PRIORIDAD_ESTADO_TRAZABILIDAD.get(estado_fila, 0) > _PRIORIDAD_ESTADO_TRAZABILIDAD.get(actual, 0):
            estado_por_requisito[codigo] = estado_fila

    requisitos_totales = len(estado_por_requisito)
    estados = list(estado_por_requisito.values())
    cubiertos = estados.count(ETIQUETAS_ESTADO["CUBIERTO"])
    pendientes_relacion = estados.count(ETIQUETAS_ESTADO["PENDIENTE_RELACION"])
    requieren_revision = estados.count(ETIQUETAS_ESTADO["REQUIERE_REVISION"])
    no_evaluados = estados.count(ETIQUETAS_ESTADO["NO_EVALUADO"])

    return {
        "requisitos_totales": requisitos_totales,
        "cubiertos": cubiertos,
        "pendientes_relacion": pendientes_relacion,
        "requieren_revision": requieren_revision,
        "no_evaluados": no_evaluados,
    }


def construir_metadata_matriz_diseno(filas: list, version_anterior: str = "1.0") -> dict:
    """Envuelve la matriz visible con la metadata de versión de la etapa de Diseño."""
    return {
        "version": "2.0",
        "etapa": "Diseño",
        "version_anterior": version_anterior,
        "fecha_generacion": datetime.now().strftime("%Y-%m-%d"),
        "filas": filas,
    }
