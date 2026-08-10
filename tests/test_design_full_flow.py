import csv
import json
import os
from pathlib import Path

from core.design_context import construir_contexto_diseno
from core.graph import construir_grafo_diseno
from integrations.issue_service import obtener_issues_diseno


PROJECT_NAME = "modelo-multiagente-dev"
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
SPRINT_CONTEXT = "Diseño"

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"


# ---------------------------------------------------------
# Matriz de trazabilidad heredada de Requerimientos
# ---------------------------------------------------------

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_trazabilidad = list(csv.DictReader(handle))


# ---------------------------------------------------------
# GitLab → DesignMapper → DesignContext
# ---------------------------------------------------------

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")
issues_por_diseno_id = {issue.get("diseno_id"): issue for issue in issues_diseno}
contextos_por_diseno_id = {
    diseno_id: construir_contexto_diseno(issue, matriz_trazabilidad)
    for diseno_id, issue in issues_por_diseno_id.items()
}


def formatear_porcentaje(valor) -> str:
    return f"{valor * 100:.0f} %" if valor is not None else "No evaluable"


def ejecutar_flujo_diseno(diseno_id: str) -> dict:
    issue = issues_por_diseno_id[diseno_id]
    contexto = contextos_por_diseno_id[diseno_id]

    grafo = construir_grafo_diseno()
    initial_state = {
        "project_name": PROJECT_NAME,
        "sprint_context": SPRINT_CONTEXT,
        "design_issues": [issue],
        "design_context": [contexto],
    }
    resultado = grafo.invoke(initial_state)

    resumen = resultado["design_summary"]
    mc03_original = resultado["design_quality_result"]["mc03"]["valor"]
    mc04_original = resultado["design_quality_result"]["mc04"]["valor"]
    ms03_original = resultado["design_security_result"]["ms03"]["valor"]
    ms04_original = resultado["design_security_result"]["ms04"]["valor"]

    print("\n" + "=" * 70)
    print(diseno_id)
    print("=" * 70)

    print("\nMC-03:", formatear_porcentaje(resumen["metricas"]["MC-03"]["valor"]))
    print("MC-04:", formatear_porcentaje(resumen["metricas"]["MC-04"]["valor"]))
    print("MS-03:", formatear_porcentaje(resumen["metricas"]["MS-03"]["valor"]))
    print("MS-04:", formatear_porcentaje(resumen["metricas"]["MS-04"]["valor"]))

    print("\nÍndice Calidad Diseño:", formatear_porcentaje(resumen["indice_calidad_diseno"]))
    print("Índice Seguridad Diseño:", formatear_porcentaje(resumen["indice_seguridad_diseno"]))

    print("\nEstado orientativo:", resumen["estado_orientativo"])

    print("\nCorrecciones:")
    for item in resumen["correcciones_necesarias"]:
        print("-", item)

    print("\nPrecisiones:")
    for item in resumen["precisiones_necesarias"]:
        print("-", item)

    print("\nOportunidades:")
    for item in resumen["oportunidades_mejora"]:
        print("-", item)

    # -------------------- Asserts fuertes --------------------

    assert resumen["metricas"]["MC-03"]["valor"] == mc03_original
    assert resumen["metricas"]["MC-04"]["valor"] == mc04_original
    assert resumen["metricas"]["MS-03"]["valor"] == ms03_original
    assert resumen["metricas"]["MS-04"]["valor"] == ms04_original

    assert resumen["estado_orientativo"] in {
        "CONFORME",
        "CONFORME CON MEJORAS",
        "CORREGIR",
        "ERROR",
    }

    return resumen


ejecutar_flujo_diseno("DIS-001")
ejecutar_flujo_diseno("DIS-002")


# ---------------------------------------------------------
# DIS-003 sigue bloqueado antes de cualquier llamada LLM
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]

print("\n" + "=" * 70)
print("DIS-003 — trazabilidad_incompleta (0 llamadas a Central/Quality/Security/Evaluator)")
print("=" * 70)
print("Referencias inválidas:", contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"])
