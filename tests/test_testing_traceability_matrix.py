from core.testing_traceability import (
    construir_filas_matriz_pruebas,
    construir_metadata_matriz_pruebas,
    resumir_trazabilidad_pruebas,
)
from integrations.testing_traceability_issue_mapper import (
    TESTING_TRACEABILITY_COLUMNS,
    construir_markdown_matriz_trazabilidad_pruebas,
    mapear_matriz_trazabilidad_pruebas,
)

MATRIZ_CODIFICACION = [
    {
        "HU origen": "HU-020", "Código requisito": "RF-001", "Tipo": "RF",
        "Nombre del requisito": "Registrar reserva", "Descripción": "...", "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-01", "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME", "Observación": "...",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
        "Observación de Codificación": "...",
    },
    {
        "HU origen": "HU-020", "Código requisito": "RF-002", "Tipo": "RF",
        "Nombre del requisito": "Evitar duplicados", "Descripción": "...", "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-02", "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME", "Observación": "...",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
        "Observación de Codificación": "...",
    },
    {
        "HU origen": "HU-021", "Código requisito": "RF-003", "Tipo": "RF",
        "Nombre del requisito": "Cancelar reserva", "Descripción": "...", "Diseño": "DIS-002",
        "Elementos de Diseño": "ED-03", "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME", "Observación": "...",
        "Codificación": "COD-002", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/cancelaciones.py", "Estado de Codificación": "CONFORME",
        "Observación de Codificación": "...",
    },
]

TESTING_SUMMARIES = [
    {"prueba_id": "PRU-001", "issue_iid": 40, "codificaciones_relacionadas": ["COD-001"], "estado_orientativo": "CORREGIR"},
]

filas = construir_filas_matriz_pruebas(MATRIZ_CODIFICACION, TESTING_SUMMARIES)
print("\n" + "=" * 70)
print("construir_filas_matriz_pruebas")
print("=" * 70)
for fila in filas:
    print(fila)

assert len(filas) == 3  # 2 filas COD-001 (una por PRU-001 en cada RF) + 1 fila COD-002 sin PRU

filas_cod001 = [f for f in filas if f["Codificación"] == "COD-001"]
assert len(filas_cod001) == 2
assert all(f["Pruebas"] == "PRU-001" for f in filas_cod001)
assert all(f["Estado de Pruebas"] == "Fallo pendiente" for f in filas_cod001)

fila_cod002 = next(f for f in filas if f["Codificación"] == "COD-002")
assert fila_cod002["Pruebas"] == "—"
assert fila_cod002["Estado de Pruebas"] == "—"


# ==========================================================
# Una Codificación evaluada por más de un PRU: una fila por PRU
# ==========================================================

testing_summaries_dos_pru = TESTING_SUMMARIES + [
    {"prueba_id": "PRU-002", "issue_iid": 41, "codificaciones_relacionadas": ["COD-001"], "estado_orientativo": "APROBADO"},
]
filas_dos_pru = construir_filas_matriz_pruebas(MATRIZ_CODIFICACION, testing_summaries_dos_pru)
filas_rf001_dos_pru = [f for f in filas_dos_pru if f["Código requisito"] == "RF-001"]
assert len(filas_rf001_dos_pru) == 2  # PRU-001 y PRU-002, ambos evaluaron COD-001
assert {f["Pruebas"] for f in filas_rf001_dos_pru} == {"PRU-001", "PRU-002"}
assert {f["Estado de Pruebas"] for f in filas_rf001_dos_pru} == {"Fallo pendiente", "Verificado"}


# ==========================================================
# resumir_trazabilidad_pruebas
# ==========================================================

resumen = resumir_trazabilidad_pruebas(filas)
print("\nresumir_trazabilidad_pruebas:", resumen)
assert resumen["codificaciones_totales"] == 2  # COD-001, COD-002
assert resumen["con_fallo_pendiente"] == 2
assert resumen["no_evaluadas"] == 1
assert resumen["verificadas"] == 0


# ==========================================================
# construir_metadata_matriz_pruebas
# ==========================================================

metadata = construir_metadata_matriz_pruebas(filas)
assert metadata["version"] == "5.0"
assert metadata["etapa"] == "Pruebas"
assert metadata["filas"] == filas


# ==========================================================
# Round-trip Markdown (TRZ-004)
# ==========================================================

markdown = construir_markdown_matriz_trazabilidad_pruebas(filas)
recuperadas = mapear_matriz_trazabilidad_pruebas(markdown)
print("\n" + "=" * 70)
print("Round-trip TRZ-004")
print("=" * 70)
assert len(recuperadas) == len(filas)
for original, recuperada in zip(filas, recuperadas):
    for columna in TESTING_TRACEABILITY_COLUMNS:
        assert recuperada[columna] == str(original.get(columna, "")), (columna, original, recuperada)

print("\nTodas las verificaciones de testing_traceability (matriz final) pasaron.")
