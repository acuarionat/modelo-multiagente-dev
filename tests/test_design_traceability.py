import copy
import csv
import os
from pathlib import Path

from core.design_context import construir_contexto_diseno
from core.design_traceability import (
    ETIQUETAS_ESTADO,
    construir_filas_matriz_diseno,
    evolucionar_matriz_a_diseno,
    normalizar_matriz_requerimientos,
    resumir_trazabilidad_diseno,
)
from integrations.issue_service import obtener_issues_diseno
from tests.fixtures_diseno import EVALUACION_POR_DISENO, RESULTADOS_CENTRAL_DISENO


COLUMNAS_ESPERADAS = [
    "HU origen",
    "Código requisito",
    "Tipo",
    "Nombre del requisito",
    "Descripción",
    "Diseño",
    "Elementos de Diseño",
    "Estado de trazabilidad",
    "Estado de Diseño",
    "Observación",
]


PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"


# ---------------------------------------------------------
# Matriz original de Requerimientos (no debe cambiar)
# ---------------------------------------------------------

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original = list(csv.DictReader(handle))

matriz_original_copia = copy.deepcopy(matriz_original)


# ---------------------------------------------------------
# GitLab → DesignMapper → DesignContext
# ---------------------------------------------------------

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")
issues_por_diseno_id = {issue.get("diseno_id"): issue for issue in issues_diseno}
contextos_por_diseno_id = {
    diseno_id: construir_contexto_diseno(issue, matriz_original)
    for diseno_id, issue in issues_por_diseno_id.items()
}


# ---------------------------------------------------------
# Resultados de Design_Central / design_summary: fixtures con datos reales
# ya validados (ver tests/fixtures_diseno.py) — sin invocar LLM en esta
# prueba de regresión. La validación real contra Groq/NVIDIA vive en
# tests/test_design_full_flow.py.
# ---------------------------------------------------------

resultados_central_diseno = RESULTADOS_CENTRAL_DISENO
evaluacion_por_diseno = EVALUACION_POR_DISENO


# ---------------------------------------------------------
# DIS-003 sigue bloqueado: no participa en la matriz
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]


# ---------------------------------------------------------
# core/design_traceability.py
# ---------------------------------------------------------

matriz_normalizada = normalizar_matriz_requerimientos(matriz_original)
estructura_interna = evolucionar_matriz_a_diseno(matriz_normalizada, resultados_central_diseno)
filas = construir_filas_matriz_diseno(estructura_interna, evaluacion_por_diseno)
resumen = resumir_trazabilidad_diseno(filas)

print("\n" + "=" * 70)
print("MATRIZ DE TRAZABILIDAD DE DISEÑO")
print("=" * 70)
for fila in filas:
    print(fila)

print("\nResumen:", resumen)


# ==========================================================
# Asserts
# ==========================================================

# ✓ matriz original no cambia
assert matriz_original == matriz_original_copia

# ✓ todos los RF/RNF originales permanecen + ✓ ningún RF/RNF inventado
codigos_originales = {fila["codigo"] for fila in matriz_normalizada}
codigos_estructura = {item["codigo_requisito"] for item in estructura_interna}
assert codigos_originales == codigos_estructura

# ✓ ningún DIS inventado + ✓ DIS-003 no aparece
dis_validos = {"DIS-001", "DIS-002"}
dis_en_filas = {fila["Diseño"] for fila in filas if fila["Diseño"] != "—"}
assert dis_en_filas <= dis_validos
assert "DIS-003" not in dis_en_filas

# ✓ ningún ED inventado
ed_validos = set()
for contexto in (contextos_por_diseno_id["DIS-001"], contextos_por_diseno_id["DIS-002"]):
    ed_validos.update(elemento["elemento_id"] for elemento in contexto.get("elementos_diseno", []))
ed_en_filas = set()
for fila in filas:
    if fila["Elementos de Diseño"] != "—":
        ed_en_filas.update(x.strip() for x in fila["Elementos de Diseño"].split(","))
assert ed_en_filas <= ed_validos

# ✓ relaciones de confianza alta → Cubierto en Diseño
# ✓ sin relación → Pendiente de relación
# ✓ confianza media/baja → Requiere revisión
# (contrato visible: solo etiquetas humanas, no nombres internos CUBIERTO/PENDIENTE_RELACION)
filas_por_clave = {(fila["Código requisito"], fila["Diseño"]): fila for fila in filas}
for item in estructura_interna:
    codigo = item["codigo_requisito"]
    for relacion in item["relaciones_diseno"]:
        fila = filas_por_clave[(codigo, relacion["diseno_id"])]
        confianza = str(relacion.get("confianza") or "").casefold()
        if relacion["estado"] == "sin_relacion_evidente":
            assert fila["Estado de trazabilidad"] == ETIQUETAS_ESTADO["PENDIENTE_RELACION"]
        elif relacion["estado"] == "relacionado" and confianza == "alta":
            assert fila["Estado de trazabilidad"] == ETIQUETAS_ESTADO["CUBIERTO"]
        elif relacion["estado"] == "relacionado" and confianza in {"media", "baja"}:
            assert fila["Estado de trazabilidad"] == ETIQUETAS_ESTADO["REQUIERE_REVISION"]

# ✓ descripción original del requisito no cambia + ✓ HU origen se conserva
normalizado_por_codigo = {item["codigo"]: item for item in matriz_normalizada}
for item in estructura_interna:
    original = normalizado_por_codigo[item["codigo_requisito"]]
    assert item["descripcion_requisito"] == original["descripcion"]
    assert item["historia_origen"] == original["historia_origen"]
for fila in filas:
    original = normalizado_por_codigo[fila["Código requisito"]]
    assert fila["Nombre del requisito"] == original["nombre"]
    assert fila["Descripción"] == original["descripcion"]
    assert fila["HU origen"] == original["historia_origen"]

# ✓ tabla visible no contiene JSON anidado
for fila in filas:
    for valor in fila.values():
        assert not isinstance(valor, (dict, list))

# ✓ tabla visible utiliza nombres comprensibles (10 columnas, orden exacto)
assert list(filas[0].keys()) == COLUMNAS_ESPERADAS
for fila in filas:
    assert list(fila.keys()) == COLUMNAS_ESPERADAS

# ✓ resumen de trazabilidad coincide con las filas
assert (
    resumen["cubiertos"] + resumen["pendientes_relacion"]
    + resumen["requieren_revision"] + resumen["no_evaluados"]
) == len(filas)

print("\nTodas las verificaciones de la matriz de trazabilidad de Diseño pasaron.")
