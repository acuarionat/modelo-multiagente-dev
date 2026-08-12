"""
Validación estructural de un Issue PRU-xxx antes de continuar hacia el
cálculo de métricas o los agentes. Determinístico: no invoca LLM. No
recalcula ni reinterpreta trazabilidad: usa el resultado ya producido por
core/testing_traceability.py::resolver_trazabilidad_heredada.

No es excesivamente rígido: 0 fallos detectados es una entrada válida
(ver core/testing_metrics.py::calcular_mc08, caso NO_APLICA); un control
de seguridad marcado "Aplica = No" también es válido y no cuenta como
pendiente.
"""

from core.testing_traceability import resolver_trazabilidad_heredada

ESTADO_VALIDO = "VALIDO"
ESTADO_INFORMACION_INSUFICIENTE = "INFORMACION_INSUFICIENTE"
ESTADO_REFERENCIA_INVALIDA = "REFERENCIA_INVALIDA"
ESTADO_SIN_PRUEBAS = "SIN_PRUEBAS"


def _texto_presente(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validar_entrada_pruebas(issue_pruebas: dict, matriz_codificacion: list) -> dict:
    """
    Clasifica la entrada de un Issue PRU-xxx según reglas determinísticas,
    ANTES de calcular MC-07/MC-08/MS-08/MS-09 o de ejecutar cualquier
    agente LLM.

    matriz_codificacion es la Matriz de Trazabilidad de Codificación
    (TRZ-003) ya evolucionada y vigente. Si el Issue declara un COD que
    no existe ahí, la entrada queda con referencia inválida y el PRU no
    continúa.
    """
    campos_faltantes = []

    if not _texto_presente(issue_pruebas.get("prueba_id")):
        campos_faltantes.append("prueba_id")
    if not _texto_presente(issue_pruebas.get("titulo")):
        campos_faltantes.append("titulo")
    if not _texto_presente(issue_pruebas.get("descripcion")):
        campos_faltantes.append("descripcion")

    codificaciones_declaradas = issue_pruebas.get("codificaciones_relacionadas") or []
    if not codificaciones_declaradas:
        campos_faltantes.append("codificaciones_relacionadas")

    trazabilidad = resolver_trazabilidad_heredada(codificaciones_declaradas, matriz_codificacion)
    referencias_invalidas = trazabilidad["codificaciones_no_encontradas"]

    tiene_informacion_evaluable = bool(
        issue_pruebas.get("pruebas_funcionales")
        or issue_pruebas.get("pruebas_seguridad")
        or issue_pruebas.get("controles_seguridad")
        or issue_pruebas.get("fallos")
    )

    if campos_faltantes:
        estado = ESTADO_INFORMACION_INSUFICIENTE
    elif referencias_invalidas:
        estado = ESTADO_REFERENCIA_INVALIDA
    elif not tiene_informacion_evaluable:
        estado = ESTADO_SIN_PRUEBAS
    else:
        estado = ESTADO_VALIDO

    return {
        "estado": estado,
        "entrada_valida": estado == ESTADO_VALIDO,
        "campos_faltantes": campos_faltantes,
        "referencias_invalidas": referencias_invalidas,
        "trazabilidad_heredada": trazabilidad["cadena_por_codificacion"],
    }
