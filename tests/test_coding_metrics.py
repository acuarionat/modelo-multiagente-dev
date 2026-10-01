from core.coding_metrics import (
    calcular_indice_calidad_codigo,
    calcular_indice_seguridad_codigo,
    calcular_mc05,
    calcular_ms05,
    calcular_ms06,
    calcular_ms07,
    determinar_estado_codificacion,
)

# ==========================================================
# MC-05
# ==========================================================

evidencia_radon_ok = {
    "estado": "OK",
    "datos": {"funciones": [
        {"nombre": "a", "aceptable": True}, {"nombre": "b", "aceptable": True},
        {"nombre": "c", "aceptable": False},
    ]},
}
mc05 = calcular_mc05(evidencia_radon_ok)
print("\nMC-05 (OK):", mc05)
assert mc05["estado_calculo"] == "calculada"
assert mc05["numerador"] == 2 and mc05["denominador"] == 3
assert abs(mc05["valor"] - 2 / 3) < 1e-9
assert mc05["satisfactorio"] is False

mc05_error = calcular_mc05({"estado": "ERROR", "detalle_error": "radon no encontrado"})
print("MC-05 (ERROR):", mc05_error)
assert mc05_error["estado_calculo"] == "no_evaluable"
assert mc05_error["valor"] is None  # nunca 0 %


# ==========================================================
# MS-05
# ==========================================================

evidencia_semgrep_sin_criticas = {"estado": "OK", "datos": {"hallazgos": [
    {"critico": False}, {"critico": False},
]}}
ms05_ok = calcular_ms05(evidencia_semgrep_sin_criticas)
print("\nMS-05 (sin críticas):", ms05_ok)
assert ms05_ok["numero_criticas"] == 0
assert ms05_ok["valor"] == 1.0
assert ms05_ok["satisfactorio"] is True

evidencia_semgrep_con_criticas = {"estado": "OK", "datos": {"hallazgos": [
    {"critico": True}, {"critico": False},
]}}
ms05_con_criticas = calcular_ms05(evidencia_semgrep_con_criticas)
print("MS-05 (con críticas):", ms05_con_criticas)
assert ms05_con_criticas["numero_criticas"] == 1
assert ms05_con_criticas["valor"] == 0.0
assert ms05_con_criticas["satisfactorio"] is False

ms05_error = calcular_ms05({"estado": "ERROR", "detalle_error": "semgrep no encontrado"})
assert ms05_error["estado_calculo"] == "no_evaluable"
assert ms05_error["valor"] is None


# ==========================================================
# MS-06
# ==========================================================

evidencia_pip_audit_ok = {"estado": "OK", "datos": {"dependencias": [
    {"nombre": "a", "segura": True}, {"nombre": "b", "segura": False}, {"nombre": "c", "segura": True},
]}}
ms06 = calcular_ms06(evidencia_pip_audit_ok)
print("\nMS-06 (OK):", ms06)
assert ms06["numerador"] == 2 and ms06["denominador"] == 3
assert abs(ms06["valor"] - 2 / 3) < 1e-9

ms06_no_aplica = calcular_ms06({"estado": "NO_APLICA"})
print("MS-06 (NO_APLICA):", ms06_no_aplica)
assert ms06_no_aplica["estado_calculo"] == "no_evaluable"
assert ms06_no_aplica["valor"] is None  # nunca 0 %


# ==========================================================
# MS-07
# ==========================================================

evidencia_gitleaks_ok = {
    "herramienta": "gitleaks",
    "estado": "OK",
    "secretos_detectados": 1,
    "archivos_con_secretos": ["b.py"],
    "total_archivos_con_secretos": 1,
    "hallazgos": [],
}
ms07 = calcular_ms07(evidencia_gitleaks_ok, ["a.py", "b.py", "c.py", "d.py"])
print("\nMS-07 (OK):", ms07)
assert ms07["numerador"] == 3 and ms07["denominador"] == 4
assert ms07["valor"] == 0.75
assert ms07["archivos_con_secretos"] == 1

ms07_error = calcular_ms07({"estado": "ERROR", "motivo": "gitleaks no encontrado"}, ["a.py"])
print("MS-07 (ERROR):", ms07_error)
assert ms07_error["estado_calculo"] == "no_evaluable"
assert ms07_error["valor"] is None  # nunca 0 %, herramienta ausente ≠ 0 secretos

ms07_sin_evidencia = calcular_ms07(evidencia_gitleaks_ok, [])
print("MS-07 (SIN_EVIDENCIA):", ms07_sin_evidencia)
assert ms07_sin_evidencia["estado_calculo"] == "sin_evidencia"
assert ms07_sin_evidencia["valor"] is None


# ==========================================================
# Índices agregados
# ==========================================================

assert calcular_indice_calidad_codigo(0.85) == 0.85
assert calcular_indice_calidad_codigo(None) is None

indice_seguridad = calcular_indice_seguridad_codigo(1.0, 0.9, 0.75)
print("\nÍndice de seguridad (MS-05=1.0, MS-06=0.9, MS-07=0.75):", indice_seguridad)
assert abs(indice_seguridad - (1.0 + 0.9 + 0.75) / 3) < 1e-9

# gitleaks ausente (MS-07 no_evaluable) no debe forzar el índice a la baja como si fuera 0.
indice_seguridad_sin_ms07 = calcular_indice_seguridad_codigo(1.0, 0.9, None)
print("Índice de seguridad (MS-07 no_evaluable):", indice_seguridad_sin_ms07)
assert abs(indice_seguridad_sin_ms07 - (1.0 + 0.9) / 2) < 1e-9

assert calcular_indice_seguridad_codigo(None, None, None) is None


# ==========================================================
# Estado orientativo
# ==========================================================

# El estado lo deciden los porcentajes con umbral estricto del 80 %:
# > 80 % aprueba; <= 80 % (o ningún índice evaluable) corrige.
sin_hallazgos = {"correcciones_necesarias": [], "precisiones_necesarias": [], "oportunidades_mejora": []}
assert determinar_estado_codificacion(indice_calidad=0.81, indice_seguridad=0.95, **sin_hallazgos) == "CONFORME"
assert determinar_estado_codificacion(indice_calidad=0.80, indice_seguridad=0.95, **sin_hallazgos) == "CORREGIR"
assert determinar_estado_codificacion(indice_calidad=0.95, indice_seguridad=0.80, **sin_hallazgos) == "CORREGIR"
assert determinar_estado_codificacion(indice_calidad=0.7999, indice_seguridad=1.0, **sin_hallazgos) == "CORREGIR"
assert determinar_estado_codificacion(indice_calidad=0.90, indice_seguridad=None, **sin_hallazgos) == "CONFORME"
assert determinar_estado_codificacion(indice_calidad=None, indice_seguridad=None, **sin_hallazgos) == "CORREGIR"
assert determinar_estado_codificacion(indice_calidad=0.90, indice_seguridad=0.90, correcciones_necesarias=["x"], precisiones_necesarias=[], oportunidades_mejora=[]) == "CONFORME CON MEJORAS"
assert determinar_estado_codificacion(indice_calidad=0.90, indice_seguridad=0.90, correcciones_necesarias=[], precisiones_necesarias=["x"], oportunidades_mejora=[]) == "CONFORME CON MEJORAS"
assert determinar_estado_codificacion(indice_calidad=0.50, indice_seguridad=0.50, correcciones_necesarias=[], precisiones_necesarias=[], oportunidades_mejora=[], error_tecnico=True) == "ERROR"

print("\nTodas las verificaciones de coding_metrics pasaron.")
