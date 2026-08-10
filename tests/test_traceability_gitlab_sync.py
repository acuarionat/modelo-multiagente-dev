import csv
import os
from pathlib import Path

from integrations.issue_service import (
    crear_o_actualizar_issue_matriz_trazabilidad,
    obtener_issue_matriz_trazabilidad,
)

PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"


# ---------------------------------------------------------
# Lectura (siempre, es de solo lectura y no publica nada)
# ---------------------------------------------------------

issue_trz001, matriz_actual = obtener_issue_matriz_trazabilidad(PROJECT_ID)

print("\n" + "=" * 70)
print("TRZ-001 — lectura actual")
print("=" * 70)
if issue_trz001 is None:
    print("TRZ-001 no existe todavía en GitLab.")
    assert matriz_actual is None
else:
    print(f"Issue #{issue_trz001.iid} — {issue_trz001.title}")
    print(f"Requisitos en TRZ-001: {len(matriz_actual)}")
    for fila in matriz_actual:
        assert set(fila.keys()) == {"codigo", "nombre", "descripcion", "tipo", "historia_origen", "estado"}


# ---------------------------------------------------------
# Publicación/actualización real — solo si se activa explícitamente
# ---------------------------------------------------------

if os.getenv("PUBLISH_GITLAB_TEST") != "1":
    print("\nPublicación/actualización real de TRZ-001 omitida (PUBLISH_GITLAB_TEST != '1').")
else:
    # Filas oficiales reales (las mismas 11 de la ejecución real de referencia),
    # pasadas pasivamente: crear_o_actualizar_issue_matriz_trazabilidad ya no
    # reconstruye nada por sí misma.
    with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
        matriz_original_csv = list(csv.DictReader(handle))
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

    issue_publicado = crear_o_actualizar_issue_matriz_trazabilidad(PROJECT_ID, filas_oficiales)
    assert issue_publicado is not None
    print("\nTRZ-001 publicado/actualizado realmente en GitLab.")
    print(f"Issue #{issue_publicado.iid} — {issue_publicado.title}")

    issue_relectura, matriz_relectura = obtener_issue_matriz_trazabilidad(PROJECT_ID)
    assert issue_relectura is not None
    assert issue_relectura.iid == issue_publicado.iid
    assert matriz_relectura
    print(f"Relectura inmediata: {len(matriz_relectura)} requisitos parseados correctamente.")

print("\nVerificación de sincronización con GitLab (TRZ-001) completada.")
