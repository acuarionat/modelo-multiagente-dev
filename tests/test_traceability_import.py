import csv
from pathlib import Path

from core.design_traceability import normalizar_matriz_requerimientos
from core.traceability_export import (
    exportar_csv_excel,
    exportar_filas_xlsx,
    importar_matriz_csv,
    importar_matriz_xlsx,
)
COLUMNAS_MATRIZ_ENTRADA_DISENO = ("Código", "Nombre", "Descripción", "Tipo", "Historia de origen", "Estado de revisión")

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"
SCRATCH_DIR = Path(__file__).parent.parent / "output"
CSV_SCRATCH = SCRATCH_DIR / "csv" / "matriz_entrada_diseno_prueba.csv"
XLSX_SCRATCH = SCRATCH_DIR / "xlsx" / "matriz_entrada_diseno_prueba.xlsx"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original_csv = list(csv.DictReader(handle))

matriz_normalizada = normalizar_matriz_requerimientos(matriz_original_csv)

# Filas con los encabezados amigables (mismos que TRZ-001 y que "Editar con Excel").
filas_editables = [
    {
        "Código": fila["codigo"],
        "Nombre": fila["nombre"],
        "Descripción": fila["descripcion"],
        "Tipo": fila["tipo"],
        "Historia de origen": fila["historia_origen"],
        "Estado de revisión": fila["estado"],
    }
    for fila in matriz_normalizada
]
assert list(filas_editables[0].keys()) == list(COLUMNAS_MATRIZ_ENTRADA_DISENO)


def verificar_round_trip(matriz_importada: list, etiqueta: str) -> None:
    print("\n" + "=" * 70)
    print(f"IMPORTACIÓN — {etiqueta}")
    print("=" * 70)
    print(f"Filas originales: {len(matriz_normalizada)} | Filas importadas: {len(matriz_importada)}")

    assert len(matriz_importada) == len(matriz_normalizada)
    importada_por_codigo = {fila["codigo"]: fila for fila in matriz_importada}
    for fila_original in matriz_normalizada:
        fila_importada = importada_por_codigo[fila_original["codigo"]]
        assert fila_importada["nombre"] == fila_original["nombre"]
        assert fila_importada["descripcion"] == fila_original["descripcion"]
        assert fila_importada["tipo"] == fila_original["tipo"]
        assert fila_importada["historia_origen"] == fila_original["historia_origen"]
        assert str(fila_importada["estado"] or "") == str(fila_original["estado"] or "")


# ---------------------------------------------------------
# importar_matriz_csv
# ---------------------------------------------------------

exportar_csv_excel(filas_editables, CSV_SCRATCH)
matriz_desde_csv = importar_matriz_csv(CSV_SCRATCH)
verificar_round_trip(matriz_desde_csv, "CSV (ruta)")

with CSV_SCRATCH.open("rb") as archivo_subido:
    matriz_desde_csv_subido = importar_matriz_csv(archivo_subido)
verificar_round_trip(matriz_desde_csv_subido, "CSV (archivo tipo upload)")


# ---------------------------------------------------------
# importar_matriz_xlsx
# ---------------------------------------------------------

exportar_filas_xlsx(filas_editables, XLSX_SCRATCH, nombre_hoja="Matriz de entrada")
matriz_desde_xlsx = importar_matriz_xlsx(XLSX_SCRATCH)
verificar_round_trip(matriz_desde_xlsx, "XLSX (ruta)")

with XLSX_SCRATCH.open("rb") as archivo_subido:
    matriz_desde_xlsx_subido = importar_matriz_xlsx(archivo_subido)
verificar_round_trip(matriz_desde_xlsx_subido, "XLSX (archivo tipo upload)")


# ---------------------------------------------------------
# GitLab y Excel convergen al mismo formato normalizado
# ---------------------------------------------------------

claves_esperadas = {"codigo", "nombre", "descripcion", "tipo", "historia_origen", "estado"}
for fila in matriz_desde_csv + matriz_desde_xlsx:
    assert set(fila.keys()) == claves_esperadas

print("\nTodas las verificaciones de importación de matriz (CSV/XLSX) pasaron.")
