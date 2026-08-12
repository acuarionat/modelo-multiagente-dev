import copy

from core.testing_contract import (
    validar_salida_central_pruebas,
    validar_salida_calidad_pruebas,
    validar_salida_seguridad_pruebas,
    validar_salida_evaluador_pruebas,
)

CODIFICACIONES_VALIDAS = {"COD-001"}

# ==========================================================
# validar_salida_central_pruebas
# ==========================================================

central_valido = {
    "issue_iid": 40, "prueba_id": "PRU-001", "titulo": "PRU-001 — Pruebas del módulo",
    "coherencia_declarado_vs_evidencia": {"estado": "coherente", "justificacion": "..."},
    "inconsistencias_detectadas": [],
    "trazabilidad_confirmada": {"COD-001": {"elementos_diseno": ["ED-01"], "requisitos": ["RF-001"], "historias": ["HU-020"]}},
}
resultado = validar_salida_central_pruebas(central_valido, [40], CODIFICACIONES_VALIDAS)
print("\ncentral válido:", resultado)
assert resultado["valido"], resultado["errores"]

central_cod_inventado = copy.deepcopy(central_valido)
central_cod_inventado["trazabilidad_confirmada"] = {"COD-999": {"elementos_diseno": [], "requisitos": [], "historias": []}}
resultado_invalido = validar_salida_central_pruebas(central_cod_inventado, [40], CODIFICACIONES_VALIDAS)
print("central con COD inventado:", resultado_invalido)
assert not resultado_invalido["valido"]
assert any("COD-999" in error for error in resultado_invalido["errores"])

central_sin_prueba_id = copy.deepcopy(central_valido)
central_sin_prueba_id["prueba_id"] = ""
resultado_sin_id = validar_salida_central_pruebas(central_sin_prueba_id, [40], CODIFICACIONES_VALIDAS)
assert not resultado_sin_id["valido"]

central_estado_invalido = copy.deepcopy(central_valido)
central_estado_invalido["coherencia_declarado_vs_evidencia"] = {"estado": "no_se", "justificacion": "..."}
resultado_estado_invalido = validar_salida_central_pruebas(central_estado_invalido, [40], CODIFICACIONES_VALIDAS)
assert not resultado_estado_invalido["valido"]


# ==========================================================
# validar_salida_calidad_pruebas
# ==========================================================

calidad_valida = {
    "interpretacion_mc07": {
        "funcionalidades_con_brecha": [{"funcionalidad": "Evitar duplicados", "explicacion": "..."}],
        "conclusion": "Explicación real.",
    },
    "interpretacion_mc08": {
        "fallos_pendientes": [],
        "conclusion": "Explicación real.",
    },
    "precisiones_necesarias": [],
    "oportunidades_adicionales": [],
}
resultado_calidad = validar_salida_calidad_pruebas(calidad_valida)
print("\ncalidad válida:", resultado_calidad)
assert resultado_calidad["valido"], resultado_calidad["errores"]

calidad_recalcula = copy.deepcopy(calidad_valida)
calidad_recalcula["interpretacion_mc07"]["valor"] = 0.5
resultado_calidad_invalida = validar_salida_calidad_pruebas(calidad_recalcula)
print("calidad recalculando MC-07:", resultado_calidad_invalida)
assert not resultado_calidad_invalida["valido"]

calidad_sin_conclusion = copy.deepcopy(calidad_valida)
calidad_sin_conclusion["interpretacion_mc08"]["conclusion"] = ""
resultado_calidad_sin_conclusion = validar_salida_calidad_pruebas(calidad_sin_conclusion)
assert not resultado_calidad_sin_conclusion["valido"]


# ==========================================================
# validar_salida_seguridad_pruebas
# ==========================================================

seguridad_valida = {
    "interpretacion_ms08": {
        "controles_no_verificados": [{"control": "Registrar operaciones", "explicacion": "..."}],
        "conclusion_ms08": "Explicación real.",
    },
    "interpretacion_ms09": {
        "pruebas_fallidas": [],
        "conclusion_ms09": "Explicación real.",
    },
    "precisiones_necesarias": [],
    "oportunidades_adicionales": [],
}
resultado_seguridad = validar_salida_seguridad_pruebas(seguridad_valida)
print("\nseguridad válida:", resultado_seguridad)
assert resultado_seguridad["valido"], resultado_seguridad["errores"]

seguridad_recalcula = copy.deepcopy(seguridad_valida)
seguridad_recalcula["interpretacion_ms09"]["numerador"] = 2
resultado_seguridad_invalida = validar_salida_seguridad_pruebas(seguridad_recalcula)
print("seguridad recalculando MS-09:", resultado_seguridad_invalida)
assert not resultado_seguridad_invalida["valido"]


# ==========================================================
# validar_salida_evaluador_pruebas
# ==========================================================

evaluador_valido = {
    "issue_iid": 40, "prueba_id": "PRU-001",
    "conclusion_calidad": "Explicación real.",
    "conclusion_seguridad": "Explicación real.",
    "correcciones_necesarias": ["Evitar duplicados tiene una prueba fallida (CP-03)."],
    "precisiones_necesarias": [],
    "oportunidades_mejora": [],
    "hallazgos_prioritarios": ["Evitar duplicados tiene una prueba fallida (CP-03)."],
    "recomendacion_revision": "Revisar el caso CP-03 antes de aprobar COD-001.",
}
resultado_evaluador = validar_salida_evaluador_pruebas(evaluador_valido, 40, "PRU-001", CODIFICACIONES_VALIDAS)
print("\nevaluador válido:", resultado_evaluador)
assert resultado_evaluador["valido"], resultado_evaluador["errores"]

evaluador_cod_inventado = copy.deepcopy(evaluador_valido)
evaluador_cod_inventado["recomendacion_revision"] = "Revisar también COD-999, que no corresponde a este PRU."
resultado_evaluador_invalido = validar_salida_evaluador_pruebas(evaluador_cod_inventado, 40, "PRU-001", CODIFICACIONES_VALIDAS)
print("evaluador mencionando COD ajeno:", resultado_evaluador_invalido)
assert not resultado_evaluador_invalido["valido"]
assert any("COD-999" in error for error in resultado_evaluador_invalido["errores"])

evaluador_recalcula = copy.deepcopy(evaluador_valido)
evaluador_recalcula["cumple"] = True
resultado_evaluador_recalcula = validar_salida_evaluador_pruebas(evaluador_recalcula, 40, "PRU-001", CODIFICACIONES_VALIDAS)
assert not resultado_evaluador_recalcula["valido"]

evaluador_lista_faltante = copy.deepcopy(evaluador_valido)
del evaluador_lista_faltante["hallazgos_prioritarios"]
resultado_evaluador_lista_faltante = validar_salida_evaluador_pruebas(evaluador_lista_faltante, 40, "PRU-001", CODIFICACIONES_VALIDAS)
assert not resultado_evaluador_lista_faltante["valido"]

print("\nTodas las verificaciones de testing_contract pasaron.")
