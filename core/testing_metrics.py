"""
Cálculo determinístico (solo Python) de las métricas de Pruebas, a partir
de la evidencia ya estructurada por integrations/testing_issue_mapper.py
(nunca de afirmaciones de un agente LLM). Ningún agente calcula estos
valores: los agentes de Calidad y Seguridad de Pruebas solo los
interpretan.
"""

from core.umbral_aprobacion import UMBRAL_APROBACION, supera_umbral

# Umbral único (80 %, comparación estricta): ver core/umbral_aprobacion.py.
UMBRAL_MC07 = UMBRAL_APROBACION
UMBRAL_MC08 = UMBRAL_APROBACION
UMBRAL_MS08 = UMBRAL_APROBACION
UMBRAL_MS09 = UMBRAL_APROBACION

_RESULTADOS_PRUEBA_RECONOCIDOS = {"APROBADA", "FALLIDA"}


def preparar_evidencia_pruebas(issue_pruebas: dict) -> dict:
    """
    Empaqueta, sin recalcular nada, la evidencia de un PRU-xxx ya mapeado:
    las listas normalizadas que calcular_metricas_pruebas() consume, más
    los conteos base para la interfaz preliminar (sin LLM).
    """
    pruebas_funcionales = issue_pruebas.get("pruebas_funcionales") or []
    fallos = issue_pruebas.get("fallos") or []
    controles_seguridad = issue_pruebas.get("controles_seguridad") or []
    pruebas_seguridad = issue_pruebas.get("pruebas_seguridad") or []
    evidencias = issue_pruebas.get("evidencias") or []

    return {
        "prueba_id": issue_pruebas.get("prueba_id"),
        "issue_iid": issue_pruebas.get("issue_iid"),
        "codificaciones_relacionadas": issue_pruebas.get("codificaciones_relacionadas") or [],
        "pruebas_funcionales": pruebas_funcionales,
        "fallos": fallos,
        "controles_seguridad": controles_seguridad,
        "pruebas_seguridad": pruebas_seguridad,
        "evidencias": evidencias,
        "conteos": {
            "pruebas_funcionales": len(pruebas_funcionales),
            "fallos": len(fallos),
            "controles_seguridad": len(controles_seguridad),
            "pruebas_seguridad": len(pruebas_seguridad),
            "evidencias": len(evidencias),
        },
    }


def calcular_mc07(pruebas_funcionales: list) -> dict:
    """
    MC-07 Corrección Funcional: agrupa las pruebas registradas por
    funcionalidad evaluada (columna "funcionalidad", NO cuenta filas de
    caso de prueba a ciegas). Una funcionalidad es correcta solo si TODAS
    las pruebas necesarias registradas para ella resultaron APROBADA.
    MC07 = funciones_correctas / funciones_evaluables.
    """
    grupos = {}
    for prueba in pruebas_funcionales or []:
        funcionalidad = str(prueba.get("funcionalidad") or "").strip()
        estado = str(prueba.get("estado") or "").strip().upper()
        if not funcionalidad or estado not in _RESULTADOS_PRUEBA_RECONOCIDOS:
            continue
        grupos.setdefault(funcionalidad, []).append(estado)

    denominador = len(grupos)
    if denominador == 0:
        return {
            "codigo": "MC-07", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": "No se registraron pruebas funcionales evaluables (funcionalidad y resultado reconocido).",
        }

    numerador = sum(1 for estados in grupos.values() if all(estado == "APROBADA" for estado in estados))
    valor = numerador / denominador

    return {
        "codigo": "MC-07", "valor": valor, "numerador": numerador, "denominador": denominador,
        "funciones_evaluadas": sorted(grupos),
        "estado_calculo": "calculada",
        "umbral": UMBRAL_MC07,
        "cumple": supera_umbral(valor),
    }


def calcular_mc08(fallos: list) -> dict:
    """
    MC-08 Corrección de Fallos = fallos corregidos y verificados / fallos
    detectados. Si no se detectaron fallos, el resultado es NO_APLICA
    (nunca 0/0 = 100 %).
    """
    fallos = fallos or []
    fallos_detectados = len(fallos)

    if fallos_detectados == 0:
        return {
            "codigo": "MC-08", "valor": None, "numerador": None, "denominador": None,
            "fallos_detectados": 0, "fallos_corregidos": 0, "fallos_corregidos_verificados": 0,
            "estado_calculo": "NO_APLICA",
            "motivo": "No se registraron fallos detectados.",
        }

    fallos_corregidos = sum(1 for fallo in fallos if fallo.get("corregido") is True)
    fallos_corregidos_verificados = sum(
        1 for fallo in fallos if fallo.get("corregido") is True and fallo.get("verificado") is True
    )
    valor = fallos_corregidos_verificados / fallos_detectados

    return {
        "codigo": "MC-08", "valor": valor,
        "numerador": fallos_corregidos_verificados, "denominador": fallos_detectados,
        "fallos_detectados": fallos_detectados, "fallos_corregidos": fallos_corregidos,
        "fallos_corregidos_verificados": fallos_corregidos_verificados,
        "estado_calculo": "calculada",
        "umbral": UMBRAL_MC08,
        "cumple": supera_umbral(valor),
    }


def calcular_ms08(controles_seguridad: list) -> dict:
    """
    MS-08 Cobertura de Verificación de Controles = controles verificados /
    controles aplicables. Un control marcado "Aplica = No" queda fuera del
    denominador: no es un control pendiente, es un control que no
    corresponde evaluar aquí.
    """
    controles = controles_seguridad or []
    aplicables = [control for control in controles if control.get("aplica") is True]
    denominador = len(aplicables)

    if denominador == 0:
        return {
            "codigo": "MS-08", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "no_evaluable",
            "motivo": "No se registraron controles de seguridad aplicables.",
        }

    numerador = sum(1 for control in aplicables if control.get("verificado") is True)
    valor = numerador / denominador

    return {
        "codigo": "MS-08", "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "umbral": UMBRAL_MS08,
        "cumple": supera_umbral(valor),
    }


def calcular_ms09(pruebas_seguridad: list, controles_seguridad: list) -> dict:
    """
    MS-09 Pruebas de Seguridad Satisfactorias = pruebas satisfactorias
    (estado APROBADA) / pruebas ejecutadas (con estado reconocido).

    Si no hay pruebas ejecutadas se distingue: NO_APLICA cuando tampoco
    se declararon controles de seguridad aplicables (justificadamente no
    correspondía evaluar seguridad aquí) vs NO_EVALUABLE cuando sí había
    controles aplicables pero ninguna prueba de seguridad con resultado
    reconocido.
    """
    pruebas = pruebas_seguridad or []
    reconocidas = [
        prueba for prueba in pruebas
        if str(prueba.get("estado") or "").strip().upper() in _RESULTADOS_PRUEBA_RECONOCIDOS
    ]
    denominador = len(reconocidas)

    if denominador == 0:
        hay_controles_aplicables = any(control.get("aplica") is True for control in (controles_seguridad or []))
        if not hay_controles_aplicables:
            return {
                "codigo": "MS-09", "valor": None, "numerador": None, "denominador": None,
                "estado_calculo": "NO_APLICA",
                "motivo": "No se declararon pruebas ni controles de seguridad aplicables para este PRU.",
            }
        return {
            "codigo": "MS-09", "valor": None, "numerador": None, "denominador": None,
            "estado_calculo": "NO_EVALUABLE",
            "motivo": "Existen controles de seguridad aplicables, pero ninguna prueba de seguridad con resultado reconocido.",
        }

    numerador = sum(1 for prueba in reconocidas if str(prueba.get("estado")).strip().upper() == "APROBADA")
    valor = numerador / denominador

    return {
        "codigo": "MS-09", "valor": valor, "numerador": numerador, "denominador": denominador,
        "estado_calculo": "calculada",
        "umbral": UMBRAL_MS09,
        "cumple": supera_umbral(valor),
    }


def _con_porcentaje_y_estado(metrica: dict) -> dict:
    resultado = dict(metrica)
    valor = resultado.get("valor")
    resultado["porcentaje"] = round(valor * 100, 2) if valor is not None else None
    estado_calculo = resultado.pop("estado_calculo", None)
    resultado["estado"] = "EVALUADO" if estado_calculo == "calculada" else str(estado_calculo or "NO_EVALUABLE").upper()
    return resultado


def determinar_estado_pruebas(metricas: dict, *, error_tecnico: bool = False) -> str:
    """
    Estado orientativo determinístico de un PRU, calculado SIEMPRE en
    Python (nunca en el LLM) a partir de las métricas MC-07/MC-08/MS-08/MS-09
    ya calculadas:

    - Fallo técnico -> ERROR.
    - Alguna métrica EVALUADA no supera el umbral (<= 80 %) -> CORREGIR.
    - Alguna métrica queda NO_EVALUABLE (evidencia insuficiente para
      juzgarla) -> REVISAR. NO_APLICA no activa esta rama: es un
      resultado legítimo (p. ej. MC-08 sin fallos detectados), no una
      brecha ni evidencia incompleta.
    - Todas las métricas evaluables superan el 80 % -> APROBADO.
    """
    if error_tecnico:
        return "ERROR"

    valores = metricas.values()

    if any(metrica.get("estado") == "EVALUADO" and metrica.get("cumple") is False for metrica in valores):
        return "CORREGIR"

    if any(metrica.get("estado") == "NO_EVALUABLE" for metrica in valores):
        return "REVISAR"

    return "APROBADO"


def calcular_metricas_pruebas(evidencia: dict) -> dict:
    """Agregador: calcula MC-07, MC-08, MS-08 y MS-09 a partir de preparar_evidencia_pruebas()."""
    mc07 = calcular_mc07(evidencia.get("pruebas_funcionales") or [])
    mc08 = calcular_mc08(evidencia.get("fallos") or [])
    ms08 = calcular_ms08(evidencia.get("controles_seguridad") or [])
    ms09 = calcular_ms09(evidencia.get("pruebas_seguridad") or [], evidencia.get("controles_seguridad") or [])

    return {
        "MC-07": _con_porcentaje_y_estado(mc07),
        "MC-08": _con_porcentaje_y_estado(mc08),
        "MS-08": _con_porcentaje_y_estado(ms08),
        "MS-09": _con_porcentaje_y_estado(ms09),
    }
