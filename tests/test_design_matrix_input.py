import copy
import csv
from pathlib import Path

from core.design_matrix_input import (
    ESTADO_MATRIZ_EDITADA,
    ESTADO_MATRIZ_INVALIDA,
    ESTADO_MATRIZ_ORIGINAL,
    comparar_matrices_requerimientos,
    preparar_matriz_entrada_diseno,
    validar_matriz_entrada_diseno,
)
from core.design_traceability import normalizar_matriz_requerimientos

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original_csv = list(csv.DictReader(handle))

matriz_original = normalizar_matriz_requerimientos(matriz_original_csv)


# ==========================================================
# validar_matriz_entrada_diseno
# ==========================================================

validacion_original = validar_matriz_entrada_diseno(matriz_original)
print("\n" + "=" * 70)
print("VALIDACIÓN — matriz original")
print("=" * 70)
print(validacion_original)
assert validacion_original["valida"]
assert validacion_original["errores"] == []

matriz_sin_descripcion = copy.deepcopy(matriz_original)
matriz_sin_descripcion[0]["descripcion"] = ""
validacion_invalida = validar_matriz_entrada_diseno(matriz_sin_descripcion)
assert not validacion_invalida["valida"]
assert any("descripción" in error for error in validacion_invalida["errores"])

matriz_duplicada = copy.deepcopy(matriz_original)
matriz_duplicada.append(copy.deepcopy(matriz_original[0]))
validacion_duplicada = validar_matriz_entrada_diseno(matriz_duplicada)
assert not validacion_duplicada["valida"]
assert any("duplicado" in error for error in validacion_duplicada["errores"])

assert validar_matriz_entrada_diseno([])["valida"] is False


# ==========================================================
# comparar_matrices_requerimientos
# ==========================================================

comparacion_identica = comparar_matrices_requerimientos(matriz_original, matriz_original)
print("\n" + "=" * 70)
print("COMPARACIÓN — matriz idéntica")
print("=" * 70)
print(comparacion_identica)
assert comparacion_identica["hay_cambios"] is False
assert comparacion_identica["agregados"] == []
assert comparacion_identica["modificados"] == []
assert comparacion_identica["retirados"] == []

matriz_editada = copy.deepcopy(matriz_original)
nuevo_requisito = {
    "codigo": "RF-999", "nombre": "Nuevo requisito de prueba",
    "descripcion": "Descripción del nuevo requisito.", "tipo": "Funcional",
    "historia_origen": "HU-999 — Historia de prueba", "estado": "",
}
matriz_editada.append(nuevo_requisito)
matriz_editada[0]["descripcion"] = matriz_editada[0]["descripcion"] + " (ajustado)"
requisito_retirado = matriz_editada.pop(1)

comparacion_editada = comparar_matrices_requerimientos(matriz_original, matriz_editada)
print("\n" + "=" * 70)
print("COMPARACIÓN — matriz editada")
print("=" * 70)
print(comparacion_editada)
assert comparacion_editada["hay_cambios"] is True
assert comparacion_editada["agregados"] == ["RF-999"]
assert comparacion_editada["retirados"] == [requisito_retirado["codigo"]]
codigos_modificados = {item["codigo"] for item in comparacion_editada["modificados"]}
assert matriz_original[0]["codigo"] in codigos_modificados
for item in comparacion_editada["modificados"]:
    if item["codigo"] == matriz_original[0]["codigo"]:
        campos_cambiados = {cambio["campo"] for cambio in item["cambios"]}
        assert "descripcion" in campos_cambiados


# ==========================================================
# preparar_matriz_entrada_diseno (estados ORIGINAL / EDITADA / INVALIDA)
# ==========================================================

resultado_original = preparar_matriz_entrada_diseno(matriz_original, matriz_original, "GitLab")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_diseno — ORIGINAL")
print("=" * 70)
print({k: v for k, v in resultado_original.items() if k != "matriz_entrada_diseno"})
assert resultado_original["matriz_estado"] == ESTADO_MATRIZ_ORIGINAL
assert resultado_original["matriz_fuente"] == "GitLab"
assert resultado_original["matriz_validacion"]["valida"] is True
assert resultado_original["requisitos_vigentes"] == len(matriz_original)

resultado_editada = preparar_matriz_entrada_diseno(matriz_original, matriz_editada, "EXCEL")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_diseno — EDITADA")
print("=" * 70)
print({k: v for k, v in resultado_editada.items() if k != "matriz_entrada_diseno"})
assert resultado_editada["matriz_estado"] == ESTADO_MATRIZ_EDITADA
assert resultado_editada["matriz_fuente"] == "EXCEL"
assert resultado_editada["matriz_cambios_pre_diseno"]["hay_cambios"] is True

matriz_invalida = copy.deepcopy(matriz_original)
matriz_invalida[0]["descripcion"] = ""
resultado_invalido = preparar_matriz_entrada_diseno(matriz_original, matriz_invalida, "GitLab")
print("\n" + "=" * 70)
print("preparar_matriz_entrada_diseno — INVALIDA")
print("=" * 70)
print({k: v for k, v in resultado_invalido.items() if k != "matriz_entrada_diseno"})
assert resultado_invalido["matriz_estado"] == ESTADO_MATRIZ_INVALIDA
assert resultado_invalido["matriz_validacion"]["valida"] is False

print("\nTodas las verificaciones de design_matrix_input pasaron.")
