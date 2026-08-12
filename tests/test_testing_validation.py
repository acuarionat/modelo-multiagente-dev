from core.testing_validation import (
    ESTADO_INFORMACION_INSUFICIENTE,
    ESTADO_REFERENCIA_INVALIDA,
    ESTADO_SIN_PRUEBAS,
    ESTADO_VALIDO,
    validar_entrada_pruebas,
)

MATRIZ_CODIFICACION = [
    {
        "HU origen": "HU-020", "Código requisito": "RF-001", "Tipo": "RF",
        "Nombre del requisito": "Registrar reserva", "Elementos de Diseño": "ED-01",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
    },
]

ISSUE_BASE = {
    "prueba_id": "PRU-001",
    "titulo": "PRU-001 — Pruebas del módulo de reservas",
    "descripcion": "Se probó el registro de reservas.",
    "codificaciones_relacionadas": ["COD-001"],
    "pruebas_funcionales": [{"funcionalidad": "Registrar reserva", "estado": "APROBADA"}],
    "fallos": [],
    "controles_seguridad": [],
    "pruebas_seguridad": [],
}

# ==========================================================
# VALIDO
# ==========================================================

resultado = validar_entrada_pruebas(ISSUE_BASE, MATRIZ_CODIFICACION)
print("\nVALIDO:", resultado)
assert resultado["estado"] == ESTADO_VALIDO
assert resultado["entrada_valida"] is True
assert resultado["campos_faltantes"] == []
assert resultado["referencias_invalidas"] == []
assert "COD-001" in resultado["trazabilidad_heredada"]

# Controles "No aplica" (aplica=False) no bloquean la validez si hay otra
# evidencia evaluable.
issue_con_control_no_aplicable = {
    **ISSUE_BASE,
    "pruebas_funcionales": [],
    "controles_seguridad": [{"control": "Rate limiting", "aplica": False, "verificado": False}],
}
resultado_control = validar_entrada_pruebas(issue_con_control_no_aplicable, MATRIZ_CODIFICACION)
print("VALIDO (solo control no aplicable):", resultado_control)
assert resultado_control["estado"] == ESTADO_VALIDO

# ==========================================================
# INFORMACION_INSUFICIENTE
# ==========================================================

issue_sin_descripcion = {**ISSUE_BASE, "descripcion": ""}
resultado_insuficiente = validar_entrada_pruebas(issue_sin_descripcion, MATRIZ_CODIFICACION)
print("\nINFORMACION_INSUFICIENTE:", resultado_insuficiente)
assert resultado_insuficiente["estado"] == ESTADO_INFORMACION_INSUFICIENTE
assert resultado_insuficiente["entrada_valida"] is False
assert "descripcion" in resultado_insuficiente["campos_faltantes"]

issue_sin_cod_declarado = {**ISSUE_BASE, "codificaciones_relacionadas": []}
resultado_sin_cod = validar_entrada_pruebas(issue_sin_cod_declarado, MATRIZ_CODIFICACION)
print("INFORMACION_INSUFICIENTE (sin COD declarado):", resultado_sin_cod)
assert resultado_sin_cod["estado"] == ESTADO_INFORMACION_INSUFICIENTE
assert "codificaciones_relacionadas" in resultado_sin_cod["campos_faltantes"]

# ==========================================================
# REFERENCIA_INVALIDA
# ==========================================================

issue_cod_inexistente = {**ISSUE_BASE, "codificaciones_relacionadas": ["COD-999"]}
resultado_referencia = validar_entrada_pruebas(issue_cod_inexistente, MATRIZ_CODIFICACION)
print("\nREFERENCIA_INVALIDA:", resultado_referencia)
assert resultado_referencia["estado"] == ESTADO_REFERENCIA_INVALIDA
assert resultado_referencia["entrada_valida"] is False
assert resultado_referencia["referencias_invalidas"] == ["COD-999"]

# ==========================================================
# SIN_PRUEBAS
# ==========================================================

issue_sin_pruebas = {
    **ISSUE_BASE,
    "pruebas_funcionales": [],
    "fallos": [],
    "controles_seguridad": [],
    "pruebas_seguridad": [],
}
resultado_sin_pruebas = validar_entrada_pruebas(issue_sin_pruebas, MATRIZ_CODIFICACION)
print("\nSIN_PRUEBAS:", resultado_sin_pruebas)
assert resultado_sin_pruebas["estado"] == ESTADO_SIN_PRUEBAS
assert resultado_sin_pruebas["entrada_valida"] is False

# Fallos por sí solos ya cuentan como información evaluable (0 fallos
# detectados es válido para MC-08, pero un fallo SÍ registrado ya hace
# que el PRU no esté "sin pruebas").
issue_solo_fallos = {**issue_sin_pruebas, "fallos": [{"fallo": "x", "corregido": True, "verificado": True}]}
resultado_solo_fallos = validar_entrada_pruebas(issue_solo_fallos, MATRIZ_CODIFICACION)
print("VALIDO (solo fallos registrados):", resultado_solo_fallos)
assert resultado_solo_fallos["estado"] == ESTADO_VALIDO

print("\nTodas las verificaciones de testing_validation pasaron.")
