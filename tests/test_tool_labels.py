"""
Test de core/code_analysis/tool_labels.py y de la presentación dinámica
de la herramienta usada en MC-05 (core/coding_presentation.py): un
repositorio TypeScript debe mostrar "ESLint Complexity", uno Python debe
mostrar "Radon" — nunca una etiqueta "(Radon)" fija sin importar la
herramienta real.
"""

from core.code_analysis.tool_labels import obtener_etiqueta_herramienta
from core.coding_presentation import _construir_mc05


def test_etiqueta_typescript():
    evidencia = {"herramienta": "eslint-complexity"}
    assert obtener_etiqueta_herramienta(evidencia["herramienta"]) == "ESLint Complexity"
    assert obtener_etiqueta_herramienta("eslint_complexity") == "ESLint Complexity"


def test_etiqueta_python():
    evidencia = {"herramienta": "radon"}
    assert obtener_etiqueta_herramienta(evidencia["herramienta"]) == "Radon"


def test_etiqueta_desconocida_no_asume_radon():
    assert obtener_etiqueta_herramienta(None) == "Analizador técnico"
    assert obtener_etiqueta_herramienta("") == "Analizador técnico"
    assert obtener_etiqueta_herramienta("otra-herramienta") == "otra-herramienta"


def test_presentacion_mc05_typescript_muestra_eslint_no_radon():
    mc05_summary = {
        "herramienta": "eslint-complexity", "valor": 1.0, "numerador": 3, "denominador": 3,
        "estado_calculo": "calculada",
    }
    mc05 = _construir_mc05(mc05_summary, {})

    assert mc05["herramienta"] == "ESLint Complexity"
    assert "ESLint Complexity" in mc05["que_mide"]
    assert "(Radon)" not in mc05["que_mide"]
    assert "(Radon)" not in mc05["resultado"]


def test_presentacion_mc05_python_muestra_radon():
    mc05_summary = {
        "herramienta": "radon", "valor": 1.0, "numerador": 2, "denominador": 2,
        "estado_calculo": "calculada",
    }
    mc05 = _construir_mc05(mc05_summary, {})

    assert mc05["herramienta"] == "Radon"
    assert "(Radon)" in mc05["que_mide"]
