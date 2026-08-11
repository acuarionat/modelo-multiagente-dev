import os

from core.coding_traceability import (
    construir_filas_matriz_codificacion,
    construir_metadata_matriz_codificacion,
    resumir_trazabilidad_codificacion,
)
from core.traceability_export import exportar_filas_xlsx

matriz_diseno = [
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

resultados_central_codificacion = [
    {
        "issue_iid": 25,
        "codificacion_id": "COD-001",
        "elementos_implementados": ["ED-01"],
        "elementos_no_confirmados": ["ED-02"],
        "archivos_consolidados": [
            {"ruta": "core/auth_service.py", "elementos_diseno_implementados": ["ED-01"]},
        ],
    },
]

evaluacion_por_cod = {"COD-001": "CONFORME"}

filas = construir_filas_matriz_codificacion(matriz_diseno, resultados_central_codificacion, evaluacion_por_cod)
print("\n" + "=" * 70)
print("construir_filas_matriz_codificacion")
print("=" * 70)
for fila in filas:
    print(fila)

# ED-01: implementado por COD-001, con ubicación real.
filas_rf001 = [f for f in filas if f["Código requisito"] == "RF-001"]
assert len(filas_rf001) == 2  # una por cada ED (ED-01, ED-02)

fila_implementado = next(f for f in filas_rf001 if f["Codificación"] == "COD-001" and f["Estado de implementación"] == "Implementado en Codificación")
assert fila_implementado["Ubicación de implementación"] == "core/auth_service.py"
assert fila_implementado["Estado de Codificación"] == "CONFORME"

fila_no_confirmado = next(f for f in filas_rf001 if f["Estado de implementación"] == "Declarado sin confirmar en el código")
assert fila_no_confirmado["Codificación"] == "COD-001"

# RF-002 / ED-03: ningún COD lo referencia todavía -> NO_EVALUADO.
filas_rf002 = [f for f in filas if f["Código requisito"] == "RF-002"]
assert len(filas_rf002) == 1
assert filas_rf002[0]["Estado de implementación"] == "No evaluado"
assert filas_rf002[0]["Codificación"] == "—"


# ==========================================================
# resumir_trazabilidad_codificacion
# ==========================================================

resumen = resumir_trazabilidad_codificacion(filas)
print("\n" + "=" * 70)
print("resumir_trazabilidad_codificacion")
print("=" * 70)
print(resumen)
assert resumen["elementos_diseno_totales"] == 3  # ED-01, ED-02, ED-03
assert resumen["implementados"] == 1
assert resumen["no_confirmados"] == 1
assert resumen["no_evaluados"] == 1


# ==========================================================
# construir_metadata_matriz_codificacion
# ==========================================================

metadata = construir_metadata_matriz_codificacion(filas)
assert metadata["version"] == "4.0"
assert metadata["etapa"] == "Codificación"
assert metadata["filas"] == filas


# ==========================================================
# Exportación Excel (openpyxl real)
# ==========================================================

ruta_xlsx = os.path.join("output", "xlsx", "test_matriz_codificacion.xlsx")
os.makedirs(os.path.dirname(ruta_xlsx), exist_ok=True)
try:
    resultado_ruta = exportar_filas_xlsx(filas, ruta_xlsx, nombre_hoja="Trazabilidad Codificación", resumen=resumen)
    print("\n" + "=" * 70)
    print("exportar_filas_xlsx ->", resultado_ruta)
    print("=" * 70)
    assert os.path.isfile(ruta_xlsx)
    assert os.path.getsize(ruta_xlsx) > 0
finally:
    if os.path.isfile(ruta_xlsx):
        os.remove(ruta_xlsx)

print("\nTodas las verificaciones de coding_traceability pasaron.")
