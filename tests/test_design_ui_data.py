import csv
import os
from pathlib import Path

from core.design_context import construir_contexto_diseno
from core.design_traceability import (
    construir_filas_matriz_diseno,
    evolucionar_matriz_a_diseno,
    normalizar_matriz_requerimientos,
)
from core.design_ui import (
    preparar_estado_entrada_diseno,
    preparar_filas_trazabilidad_diseno_ui,
    preparar_prevalidacion_diseno,
    preparar_resultado_diseno_tabs,
)
from integrations.issue_service import obtener_issues_diseno
from tests.fixtures_diseno import (
    CONCLUSIONES_EVALUADOR_DISENO,
    DESIGN_SUMMARY_POR_DISENO,
    EVALUACION_POR_DISENO,
    RESULTADOS_CENTRAL_DISENO,
    RESULTADOS_SECURITY_DISENO,
)

PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"


# ---------------------------------------------------------
# GitLab → DesignMapper → DesignContext (real, sin LLM)
# ---------------------------------------------------------

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original = list(csv.DictReader(handle))

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")
contextos_por_diseno_id = {
    issue.get("diseno_id"): construir_contexto_diseno(issue, matriz_original)
    for issue in issues_diseno
}
matriz_normalizada = normalizar_matriz_requerimientos(matriz_original)


# ==========================================================
# preparar_prevalidacion_diseno
# ==========================================================

prevalidacion = preparar_prevalidacion_diseno(matriz_normalizada, contextos_por_diseno_id)

print("\n" + "=" * 70)
print("PREVALIDACIÓN")
print("=" * 70)
print(prevalidacion)

assert prevalidacion["requisitos_totales"] == len(matriz_normalizada)
assert prevalidacion["issues_validos"] == ["DIS-001", "DIS-002"]
assert prevalidacion["issues_bloqueados"] == ["DIS-003"]
assert prevalidacion["referencias_invalidas"] >= 2  # RF-009, RF-010 en DIS-003
assert prevalidacion["referencias_validas"] > 0


# ==========================================================
# preparar_estado_entrada_diseno
# ==========================================================

estado_entrada = preparar_estado_entrada_diseno(contextos_por_diseno_id)

print("\n" + "=" * 70)
print("ESTADO DE ENTRADA")
print("=" * 70)
for fila in estado_entrada:
    print(fila["diseno_id"], "-", fila["estado_entrada"])

por_id = {fila["diseno_id"]: fila for fila in estado_entrada}
assert por_id["DIS-001"]["estado_entrada"] == "Entrada válida"
assert por_id["DIS-001"]["entrada_valida"] is True
assert por_id["DIS-002"]["estado_entrada"] == "Entrada válida"
assert por_id["DIS-002"]["entrada_valida"] is True
assert por_id["DIS-003"]["estado_entrada"] == "Trazabilidad incompleta"
assert por_id["DIS-003"]["entrada_valida"] is False
assert set(por_id["DIS-003"]["referencias_invalidas"]) == {"RF-009", "RF-010"}


# ==========================================================
# preparar_filas_trazabilidad_diseno_ui
# ==========================================================

estructura_interna = evolucionar_matriz_a_diseno(matriz_normalizada, RESULTADOS_CENTRAL_DISENO)
filas_matriz = construir_filas_matriz_diseno(estructura_interna, EVALUACION_POR_DISENO)

filas_ui_dis001 = preparar_filas_trazabilidad_diseno_ui("DIS-001", filas_matriz)

print("\n" + "=" * 70)
print("TRAZABILIDAD UI — DIS-001")
print("=" * 70)
for fila in filas_ui_dis001:
    print(fila)

assert filas_ui_dis001
claves_esperadas = {"Requisito", "Diseño", "Elementos", "Estado de trazabilidad", "Observación"}
for fila in filas_ui_dis001:
    assert set(fila.keys()) == claves_esperadas
    assert fila["Diseño"] == "DIS-001"

filas_ui_dis003 = preparar_filas_trazabilidad_diseno_ui("DIS-003", filas_matriz)
assert filas_ui_dis003 == []


# ==========================================================
# preparar_resultado_diseno_tabs
# ==========================================================

def construir_resultado_grafo_ficticio(diseno_id: str) -> dict:
    central = next(r for r in RESULTADOS_CENTRAL_DISENO if r["diseno_id"] == diseno_id)
    security_raw = RESULTADOS_SECURITY_DISENO[diseno_id]
    resumen = DESIGN_SUMMARY_POR_DISENO[diseno_id]
    conclusiones = CONCLUSIONES_EVALUADOR_DISENO[diseno_id]

    return {
        "design_context": [contextos_por_diseno_id[diseno_id]],
        "design_central_result": central,
        "design_quality_result": {
            "raw": {
                "metricas": {
                    "completitud_descripcion": {"codigo": "MC-03", "elementos_documentados": []},
                    "acoplamiento_componentes": {"codigo": "MC-04", "componentes_evaluados": []},
                },
            },
            "mc03": resumen["metricas"]["MC-03"],
            "mc04": resumen["metricas"]["MC-04"],
        },
        "design_security_result": {
            "raw": security_raw,
            "ms03": resumen["metricas"]["MS-03"],
            "ms04": resumen["metricas"]["MS-04"],
        },
        "design_evaluator_result": {
            "conclusion_calidad": conclusiones["conclusion_calidad"],
            "conclusion_seguridad": conclusiones["conclusion_seguridad"],
            "correcciones_necesarias": resumen["correcciones_necesarias"],
            "precisiones_necesarias": resumen["precisiones_necesarias"],
            "oportunidades_mejora": resumen["oportunidades_mejora"],
        },
        "design_summary": resumen,
    }


resultado_grafo_dis001 = construir_resultado_grafo_ficticio("DIS-001")
datos_tabs = preparar_resultado_diseno_tabs(resultado_grafo_dis001)

print("\n" + "=" * 70)
print("DATOS DE PESTAÑAS — DIS-001")
print("=" * 70)
print(datos_tabs)

assert datos_tabs["diseno_id"] == "DIS-001"
assert datos_tabs["estado_orientativo"] == "CORREGIR"
assert datos_tabs["resumen"]["indice_calidad_diseno"] == DESIGN_SUMMARY_POR_DISENO["DIS-001"]["indice_calidad_diseno"]
assert datos_tabs["calidad"]["mc03"]["valor"] == DESIGN_SUMMARY_POR_DISENO["DIS-001"]["metricas"]["MC-03"]["valor"]
assert datos_tabs["calidad"]["conclusion"] == CONCLUSIONES_EVALUADOR_DISENO["DIS-001"]["conclusion_calidad"]
assert datos_tabs["seguridad"]["ms03"]["valor"] == DESIGN_SUMMARY_POR_DISENO["DIS-001"]["metricas"]["MS-03"]["valor"]
assert datos_tabs["seguridad"]["conclusion"] == CONCLUSIONES_EVALUADOR_DISENO["DIS-001"]["conclusion_seguridad"]
assert datos_tabs["seguridad"]["evidencia_ms04"]["controles_faltantes"] == (
    RESULTADOS_SECURITY_DISENO["DIS-001"]["cobertura_controles"]["controles_faltantes"]
)
codigos_ed = {elemento["elemento_id"] for elemento in datos_tabs["formalizacion"]["elementos_diseno"]}
assert codigos_ed == {"ED-01", "ED-02", "ED-03"}
assert datos_tabs["formalizacion"]["aspectos_pendientes"] == (
    DESIGN_SUMMARY_POR_DISENO["DIS-001"]["correcciones_necesarias"]
    + DESIGN_SUMMARY_POR_DISENO["DIS-001"]["precisiones_necesarias"]
)

# No se recalcula nada: el valor debe ser exactamente el mismo objeto de origen
assert datos_tabs["resumen"]["correcciones_necesarias"] is DESIGN_SUMMARY_POR_DISENO["DIS-001"]["correcciones_necesarias"]

print("\nTodas las verificaciones de datos de la UI de Diseño pasaron.")
