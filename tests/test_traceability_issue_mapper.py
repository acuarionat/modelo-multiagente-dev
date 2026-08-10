import csv
from pathlib import Path
from types import SimpleNamespace

from core.utils import TRACEABILITY_COLUMNS
from integrations.traceability_issue_mapper import (
    construir_markdown_matriz_trazabilidad,
    mapear_matriz_trazabilidad,
)

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original_csv = list(csv.DictReader(handle))

# Filas oficiales en el contrato de 7 columnas (TRACEABILITY_COLUMNS), el
# mismo que produce core.utils.construir_filas_matriz_requerimientos_final.
filas_oficiales = [
    {
        "Código": fila.get("Código", ""),
        "Nombre": fila.get("Nombre", ""),
        "Descripción": fila.get("Descripción", ""),
        "Tipo": fila.get("Tipo", ""),
        "Historia de origen": fila.get("Historia de origen", ""),
        "Fecha de generación": fila.get("Fecha de generación", ""),
        "Estado de revisión": fila.get("Estado de cumplimiento", ""),
    }
    for fila in matriz_original_csv
]


# ---------------------------------------------------------
# construir_markdown_matriz_trazabilidad
# ---------------------------------------------------------

markdown = construir_markdown_matriz_trazabilidad(filas_oficiales)

print("\n" + "=" * 70)
print("MARKDOWN TRZ-001 (primeras líneas)")
print("=" * 70)
print("\n".join(markdown.splitlines()[:10]))

assert "TRZ-001" in markdown
assert "| " + " | ".join(TRACEABILITY_COLUMNS) + " |" in markdown
for fila in filas_oficiales:
    assert fila["Código"] in markdown
    assert fila["Descripción"] in markdown

# Con metadata de ejecución (sección 10)
markdown_con_metadata = construir_markdown_matriz_trazabilidad(
    filas_oficiales,
    {"execution_id": "requerimientos-20260809-120000", "milestone": "Recepción de Requerimientos", "generated_at": "2026-08-09T12:00:00"},
)
assert "requerimientos-20260809-120000" in markdown_con_metadata
assert "Recepción de Requerimientos" in markdown_con_metadata


# ---------------------------------------------------------
# mapear_matriz_trazabilidad (round-trip, sin renumerar)
# ---------------------------------------------------------

issue_ficticio = SimpleNamespace(description=markdown)
filas_publicables = mapear_matriz_trazabilidad(issue_ficticio)

print("\n" + "=" * 70)
print("MATRIZ RECONSTRUIDA (round-trip)")
print("=" * 70)
print(f"Filas oficiales: {len(filas_oficiales)} | Filas publicadas: {len(filas_publicables)}")

assert len(filas_publicables) == len(filas_oficiales)

publicadas_por_codigo = {fila["Código"]: fila for fila in filas_publicables}
for fila_oficial in filas_oficiales:
    fila_publicada = publicadas_por_codigo[fila_oficial["Código"]]
    assert fila_publicada["Nombre"] == fila_oficial["Nombre"]
    assert fila_publicada["Descripción"] == fila_oficial["Descripción"]
    assert fila_publicada["Tipo"] == fila_oficial["Tipo"]
    assert fila_publicada["Historia de origen"] == fila_oficial["Historia de origen"]

# No renumera: el orden y el código deben conservarse exactamente
for oficial, publicada in zip(filas_oficiales, filas_publicables):
    assert oficial["Código"] == publicada["Código"]

# Issue sin tabla → matriz vacía, sin excepción
issue_vacio = SimpleNamespace(description="Sin contenido todavía.")
assert mapear_matriz_trazabilidad(issue_vacio) == []

print("\nTodas las verificaciones del traceability_issue_mapper pasaron.")
