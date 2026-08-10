import csv
from pathlib import Path
from types import SimpleNamespace

from core.utils import construir_filas_matriz_requerimientos_final
from integrations.issue_service import validar_consistencia_matriz_publicacion
from integrations.traceability_issue_mapper import construir_markdown_matriz_trazabilidad, mapear_matriz_trazabilidad

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original_csv = list(csv.DictReader(handle))

# Fixture real: los requerimientos formalizados de LA ejecución que produjo
# la matriz de 11 requerimientos (RF-001..RF-008, RNF-001..RNF-003, HU-006 a
# HU-010). No se lee cache_results ni ninguna otra ejecución.
requerimientos_formalizados = [
    {
        "codigo": fila.get("Código", ""),
        "nombre": fila.get("Nombre", ""),
        "descripcion_formal": fila.get("Descripción", ""),
        "tipo": fila.get("Tipo", ""),
        "historia_origen": fila.get("Historia de origen", ""),
        "fecha_generacion": fila.get("Fecha de generación", ""),
        "estado_revision": fila.get("Estado de cumplimiento", ""),
    }
    for fila in matriz_original_csv
]

filas_oficiales = construir_filas_matriz_requerimientos_final(requerimientos_formalizados, "2026-07-29")

print("\n" + "=" * 70)
print("FILAS OFICIALES — ejecución de 11 requerimientos")
print("=" * 70)
for fila in filas_oficiales:
    print(fila["Código"], "-", fila["Nombre"])


# ==========================================================
# La ejecución real produce exactamente 11 requerimientos
# ==========================================================

assert len(filas_oficiales) == 11

codigos_oficiales = {fila["Código"] for fila in filas_oficiales}
assert codigos_oficiales == {
    "RF-001", "RF-002", "RF-003", "RF-004", "RF-005", "RF-006",
    "RNF-001", "RNF-002", "RF-007", "RNF-003", "RF-008",
}


# ==========================================================
# RF-001 es exactamente el requerimiento real de esta ejecución
# ==========================================================

fila_trz_rf001 = next(fila for fila in filas_oficiales if fila["Código"] == "RF-001")
assert fila_trz_rf001["Nombre"] == "Mostrar únicamente horarios disponibles"
assert "HU-006" in fila_trz_rf001["Historia de origen"]


# ==========================================================
# No aparece contenido ajeno a esta ejecución.
# (Bug real observado: RF-001 mezclado con "Validar documento de identidad
# del paciente", que en realidad pertenece a HU-007 en OTRA ejecución.)
# ==========================================================

contenido_completo = " ".join(f"{fila['Código']} {fila['Nombre']} {fila['Descripción']}" for fila in filas_oficiales)
assert "Validar documento de identidad del paciente" not in contenido_completo
assert "RF-020" not in codigos_oficiales
assert "RF-999" not in codigos_oficiales


# ==========================================================
# Round-trip por Markdown: filas publicables (TRZ-001) == filas oficiales
# ==========================================================

markdown = construir_markdown_matriz_trazabilidad(filas_oficiales)
filas_publicables = mapear_matriz_trazabilidad(SimpleNamespace(description=markdown))

print("\n" + "=" * 70)
print("FILAS PUBLICABLES — round-trip por Markdown (TRZ-001)")
print("=" * 70)
for fila in filas_publicables:
    print(fila["Código"], "-", fila["Nombre"])

assert len(filas_publicables) == 11

codigos_publicables = {fila["Código"] for fila in filas_publicables}
assert codigos_oficiales == codigos_publicables

# GitLab no renumera: mismo orden, mismo código exacto
for original, publicada in zip(filas_oficiales, filas_publicables):
    assert original["Código"] == publicada["Código"]


# ==========================================================
# validar_consistencia_matriz_publicacion no debe lanzar con datos correctos
# ==========================================================

validar_consistencia_matriz_publicacion(filas_oficiales, filas_publicables)

# Y debe lanzar si detecta una divergencia real (p. ej. una fila ajena mezclada)
filas_trz_contaminadas = filas_publicables + [{
    "Código": "RF-999", "Nombre": "Requisito ajeno", "Descripción": "No pertenece a esta ejecución.",
    "Tipo": "Funcional", "Historia de origen": "HU-999 — Otra ejecución",
    "Fecha de generación": "01/01/2026", "Estado de revisión": "Pendiente de validación",
}]
detecto_la_contaminacion = False
try:
    validar_consistencia_matriz_publicacion(filas_oficiales, filas_trz_contaminadas)
except AssertionError:
    detecto_la_contaminacion = True
assert detecto_la_contaminacion, "Debía detectar la fila ajena mezclada en la matriz publicada."

print("\nTodas las verificaciones de consistencia Requerimientos-TRZ-001 pasaron.")
