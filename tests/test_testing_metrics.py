from core.testing_metrics import (
    calcular_mc07,
    calcular_mc08,
    calcular_metricas_pruebas,
    calcular_ms08,
    calcular_ms09,
    preparar_evidencia_pruebas,
)

# ==========================================================
# MC-07 — Corrección Funcional
# ==========================================================

pruebas_funcionales_mixtas = [
    {"funcionalidad": "Registrar reserva", "estado": "APROBADA"},
    {"funcionalidad": "Registrar reserva", "estado": "APROBADA"},
    {"funcionalidad": "Evitar duplicados", "estado": "APROBADA"},
    {"funcionalidad": "Evitar duplicados", "estado": "FALLIDA"},
    {"funcionalidad": "Cancelar reserva", "estado": ""},  # no reconocido: no cuenta el grupo
]
mc07 = calcular_mc07(pruebas_funcionales_mixtas)
print("\nMC-07 (mixto):", mc07)
assert mc07["estado_calculo"] == "calculada"
assert mc07["denominador"] == 2  # "Cancelar reserva" no entra: sin resultado reconocido
assert mc07["numerador"] == 1    # solo "Registrar reserva" tiene todas sus pruebas APROBADA
assert abs(mc07["valor"] - 0.5) < 1e-9
assert mc07["cumple"] is False

mc07_vacio = calcular_mc07([])
print("MC-07 (vacío):", mc07_vacio)
assert mc07_vacio["estado_calculo"] == "no_evaluable"
assert mc07_vacio["valor"] is None

mc07_todas_aprobadas = calcular_mc07([
    {"funcionalidad": "Login", "estado": "aprobada"},
    {"funcionalidad": "Logout", "estado": "Aprobada"},
])
print("MC-07 (todas aprobadas, case-insensitive):", mc07_todas_aprobadas)
assert mc07_todas_aprobadas["valor"] == 1.0
assert mc07_todas_aprobadas["cumple"] is True


# ==========================================================
# MC-08 — Corrección de Fallos
# ==========================================================

mc08_sin_fallos = calcular_mc08([])
print("\nMC-08 (sin fallos):", mc08_sin_fallos)
assert mc08_sin_fallos["estado_calculo"] == "NO_APLICA"
assert mc08_sin_fallos["valor"] is None  # nunca 0/0 = 100 %
assert mc08_sin_fallos["fallos_detectados"] == 0

fallos = [
    {"corregido": True, "verificado": True},
    {"corregido": True, "verificado": False},
    {"corregido": False, "verificado": False},
]
mc08 = calcular_mc08(fallos)
print("MC-08 (parcial):", mc08)
assert mc08["estado_calculo"] == "calculada"
assert mc08["fallos_detectados"] == 3
assert mc08["fallos_corregidos"] == 2
assert mc08["fallos_corregidos_verificados"] == 1
assert abs(mc08["valor"] - 1 / 3) < 1e-9
assert mc08["cumple"] is False


# ==========================================================
# MS-08 — Cobertura de Verificación de Controles
# ==========================================================

ms08_sin_controles = calcular_ms08([])
print("\nMS-08 (sin controles):", ms08_sin_controles)
assert ms08_sin_controles["estado_calculo"] == "no_evaluable"
assert ms08_sin_controles["valor"] is None

controles = [
    {"aplica": True, "verificado": True},
    {"aplica": True, "verificado": False},
    {"aplica": False, "verificado": False},  # no aplicable: fuera del denominador
]
ms08 = calcular_ms08(controles)
print("MS-08 (parcial):", ms08)
assert ms08["numerador"] == 1 and ms08["denominador"] == 2
assert abs(ms08["valor"] - 0.5) < 1e-9
assert ms08["cumple"] is False

ms08_completo = calcular_ms08([{"aplica": True, "verificado": True}] * 3)
print("MS-08 (completo):", ms08_completo)
assert ms08_completo["valor"] == 1.0
assert ms08_completo["cumple"] is True


# ==========================================================
# MS-09 — Pruebas de Seguridad Satisfactorias
# ==========================================================

ms09_no_aplica = calcular_ms09([], [])
print("\nMS-09 (NO_APLICA):", ms09_no_aplica)
assert ms09_no_aplica["estado_calculo"] == "NO_APLICA"
assert ms09_no_aplica["valor"] is None

ms09_no_evaluable = calcular_ms09([], [{"aplica": True, "verificado": True}])
print("MS-09 (NO_EVALUABLE):", ms09_no_evaluable)
assert ms09_no_evaluable["estado_calculo"] == "NO_EVALUABLE"
assert ms09_no_evaluable["valor"] is None

pruebas_seguridad = [
    {"estado": "APROBADA"}, {"estado": "APROBADA"}, {"estado": "FALLIDA"},
]
ms09 = calcular_ms09(pruebas_seguridad, [])
print("MS-09 (parcial):", ms09)
assert ms09["numerador"] == 2 and ms09["denominador"] == 3
assert abs(ms09["valor"] - 2 / 3) < 1e-9
assert ms09["cumple"] is False

ms09_completo = calcular_ms09([{"estado": "Aprobada"}, {"estado": "aprobada"}], [])
print("MS-09 (completo):", ms09_completo)
assert ms09_completo["valor"] == 1.0
assert ms09_completo["cumple"] is True


# ==========================================================
# preparar_evidencia_pruebas
# ==========================================================

issue_pruebas = {
    "prueba_id": "PRU-001",
    "issue_iid": 40,
    "codificaciones_relacionadas": ["COD-001"],
    "pruebas_funcionales": pruebas_funcionales_mixtas,
    "fallos": fallos,
    "controles_seguridad": controles,
    "pruebas_seguridad": pruebas_seguridad,
    "evidencias": [{"id": "EV-01"}],
}
evidencia = preparar_evidencia_pruebas(issue_pruebas)
print("\npreparar_evidencia_pruebas:", evidencia)
assert evidencia["prueba_id"] == "PRU-001"
assert evidencia["conteos"] == {
    "pruebas_funcionales": 5, "fallos": 3, "controles_seguridad": 3,
    "pruebas_seguridad": 3, "evidencias": 1,
}
assert evidencia["pruebas_funcionales"] == pruebas_funcionales_mixtas


# ==========================================================
# calcular_metricas_pruebas (agregador)
# ==========================================================

metricas = calcular_metricas_pruebas(evidencia)
print("\ncalcular_metricas_pruebas:", metricas)

assert metricas["MC-07"]["estado"] == "EVALUADO"
assert metricas["MC-07"]["porcentaje"] == 50.0
assert metricas["MC-07"]["cumple"] is False

assert metricas["MC-08"]["estado"] == "EVALUADO"
assert metricas["MC-08"]["fallos_detectados"] == 3
assert metricas["MC-08"]["fallos_corregidos"] == 2
assert metricas["MC-08"]["fallos_corregidos_verificados"] == 1
assert metricas["MC-08"]["porcentaje"] == 33.33

assert metricas["MS-08"]["estado"] == "EVALUADO"
assert metricas["MS-08"]["porcentaje"] == 50.0

assert metricas["MS-09"]["estado"] == "EVALUADO"
assert metricas["MS-09"]["porcentaje"] == 66.67

metricas_sin_evidencia = calcular_metricas_pruebas(preparar_evidencia_pruebas({}))
print("\ncalcular_metricas_pruebas (sin evidencia):", metricas_sin_evidencia)
assert metricas_sin_evidencia["MC-07"]["estado"] == "NO_EVALUABLE"
assert metricas_sin_evidencia["MC-08"]["estado"] == "NO_APLICA"
assert metricas_sin_evidencia["MS-08"]["estado"] == "NO_EVALUABLE"
assert metricas_sin_evidencia["MS-09"]["estado"] == "NO_APLICA"

print("\nTodas las verificaciones de testing_metrics pasaron.")
