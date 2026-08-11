import copy

from core.coding_matrix_input import (
    ESTADO_MATRIZ_EDITADA,
    ESTADO_MATRIZ_INVALIDA,
    ESTADO_MATRIZ_ORIGINAL,
    comparar_matrices_diseno,
    extraer_elementos_diseno_validos,
    preparar_matriz_entrada_codificacion,
)

# Filas con el mismo contrato exacto que produce
# core/design_traceability.py::construir_filas_matriz_diseno.
matriz_original = [
    {
        "HU origen": "HU-006 — Consultar horarios disponibles",
        "Código requisito": "RF-001",
        "Tipo": "Funcional",
        "Nombre del requisito": "Mostrar únicamente horarios disponibles",
        "Descripción": "El sistema deberá mostrar solo los horarios libres.",
        "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-01, ED-02",
        "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME",
        "Observación": "Relación identificada con evidencia suficiente.",
    },
    {
        "HU origen": "HU-007 — Registrar reserva",
        "Código requisito": "RF-002",
        "Tipo": "Funcional",
        "Nombre del requisito": "Registrar una reserva nueva",
        "Descripción": "El sistema deberá permitir registrar una reserva.",
        "Diseño": "DIS-002",
        "Elementos de Diseño": "ED-03",
        "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME",
        "Observación": "Relación identificada con evidencia suficiente.",
    },
]


# ==========================================================
# extraer_elementos_diseno_validos
# ==========================================================

validos = extraer_elementos_diseno_validos(matriz_original)
print("\n" + "=" * 70)
print("extraer_elementos_diseno_validos")
print("=" * 70)
print(sorted(validos))
assert validos == {"ED-01", "ED-02", "ED-03"}


# ==========================================================
# comparar_matrices_diseno
# ==========================================================

comparacion_identica = comparar_matrices_diseno(matriz_original, matriz_original)
print("\n" + "=" * 70)
print("comparar_matrices_diseno — matriz idéntica")
print("=" * 70)
print(comparacion_identica)
assert comparacion_identica["hay_cambios"] is False
assert comparacion_identica["errores_estructura"] == []

matriz_editada = copy.deepcopy(matriz_original)
matriz_editada[0]["Elementos de Diseño"] = "ED-01, ED-02, ED-04"
nueva_fila = {
    "HU origen": "HU-008 — Cancelar reserva",
    "Código requisito": "RF-003",
    "Tipo": "Funcional",
    "Nombre del requisito": "Cancelar una reserva",
    "Descripción": "El sistema deberá permitir cancelar una reserva.",
    "Diseño": "DIS-003",
    "Elementos de Diseño": "ED-05",
    "Estado de trazabilidad": "Cubierto en Diseño",
    "Estado de Diseño": "CONFORME",
    "Observación": "Relación identificada con evidencia suficiente.",
}
matriz_editada.append(nueva_fila)
fila_retirada = matriz_editada.pop(1)

comparacion_editada = comparar_matrices_diseno(matriz_original, matriz_editada)
print("\n" + "=" * 70)
print("comparar_matrices_diseno — matriz editada")
print("=" * 70)
print(comparacion_editada)
assert comparacion_editada["hay_cambios"] is True
assert comparacion_editada["agregados"] == [{"codigo_requisito": "RF-003", "diseno": "DIS-003"}]
assert comparacion_editada["retirados"] == [
    {"codigo_requisito": fila_retirada["Código requisito"], "diseno": fila_retirada["Diseño"]}
]
assert len(comparacion_editada["modificados"]) == 1
assert comparacion_editada["modificados"][0]["codigo_requisito"] == "RF-001"


# ==========================================================
# preparar_matriz_entrada_codificacion (ORIGINAL / EDITADA / INVALIDA)
# ==========================================================

resultado_original = preparar_matriz_entrada_codificacion(matriz_original, matriz_original, "GitLab")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_codificacion — ORIGINAL")
print("=" * 70)
print(resultado_original)
assert resultado_original["coding_matrix_status"] == ESTADO_MATRIZ_ORIGINAL
assert resultado_original["coding_matrix_source"] == "GitLab"
assert resultado_original["coding_matrix_version"] == "3.0"
assert resultado_original["elementos_diseno_validos"] == ["ED-01", "ED-02", "ED-03"]

resultado_editada = preparar_matriz_entrada_codificacion(matriz_original, matriz_editada, "EXCEL")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_codificacion — EDITADA")
print("=" * 70)
print(resultado_editada)
assert resultado_editada["coding_matrix_status"] == ESTADO_MATRIZ_EDITADA
assert resultado_editada["coding_matrix_changes"]["hay_cambios"] is True

matriz_invalida = [{"Código requisito": "RF-001"}]  # faltan columnas requeridas
resultado_invalido = preparar_matriz_entrada_codificacion(matriz_original, matriz_invalida, "GitLab")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_codificacion — INVALIDA")
print("=" * 70)
print(resultado_invalido)
assert resultado_invalido["coding_matrix_status"] == ESTADO_MATRIZ_INVALIDA
assert resultado_invalido["coding_matrix_changes"]["errores_estructura"] != []

resultado_vacia = preparar_matriz_entrada_codificacion(matriz_original, [], "GitLab")
assert resultado_vacia["coding_matrix_status"] == ESTADO_MATRIZ_INVALIDA

print("\nTodas las verificaciones de coding_matrix_input pasaron.")
