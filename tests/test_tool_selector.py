"""
Test de core/code_analysis/tool_selector.py: confirma que el selector
elige la herramienta correcta según el lenguaje/ecosistema real, y que
puede devolver más de una herramienta por métrica cuando el repositorio
combina lenguajes (proyectos mixtos).
"""

from core.code_analysis.tool_selector import seleccionar_herramientas

PERFIL_TYPESCRIPT_NODE = {
    "lenguajes": [{"nombre": "TypeScript", "porcentaje": 90.0}],
    "ecosistemas": [{"id": "node", "nombre": "Node.js", "evidencias": [], "gestor_dependencias": "npm"}],
}

PERFIL_PYTHON = {
    "lenguajes": [{"nombre": "Python", "porcentaje": 100.0}],
    "ecosistemas": [{"id": "python", "nombre": "Python", "evidencias": [], "gestor_dependencias": "pip"}],
}

PERFIL_MIXTO = {
    "lenguajes": [{"nombre": "TypeScript", "porcentaje": 60.0}, {"nombre": "Python", "porcentaje": 40.0}],
    "ecosistemas": [
        {"id": "node", "nombre": "Node.js", "evidencias": [], "gestor_dependencias": "npm"},
        {"id": "python", "nombre": "Python", "evidencias": [], "gestor_dependencias": "pip"},
    ],
}


def _adaptadores(seleccion, metrica):
    return {entrada["adaptador"] for entrada in seleccion[metrica]}


def test_repositorio_typescript_node_selecciona_eslint_y_npm_audit():
    seleccion = seleccionar_herramientas(PERFIL_TYPESCRIPT_NODE)

    assert _adaptadores(seleccion, "MC-05") == {"eslint_complexity"}
    assert _adaptadores(seleccion, "MS-06") == {"npm_audit"}
    assert _adaptadores(seleccion, "MS-05") == {"semgrep"}
    assert _adaptadores(seleccion, "MS-07") == {"gitleaks"}


def test_repositorio_python_selecciona_radon_y_pip_audit():
    seleccion = seleccionar_herramientas(PERFIL_PYTHON)

    assert _adaptadores(seleccion, "MC-05") == {"radon"}
    assert _adaptadores(seleccion, "MS-06") == {"pip_audit"}


def test_repositorio_mixto_selecciona_ambas_herramientas_por_metrica():
    seleccion = seleccionar_herramientas(PERFIL_MIXTO)

    assert _adaptadores(seleccion, "MC-05") == {"eslint_complexity", "radon"}
    assert _adaptadores(seleccion, "MS-06") == {"npm_audit", "pip_audit"}
    # MS-05 y MS-07 siguen teniendo un único adaptador (multilenguaje, siempre aplican).
    assert len(seleccion["MS-05"]) == 1
    assert len(seleccion["MS-07"]) == 1


def test_repositorio_sin_lenguajes_conocidos_no_selecciona_mc05_ni_ms06():
    seleccion = seleccionar_herramientas({"lenguajes": [], "ecosistemas": []})

    assert seleccion["MC-05"] == []
    assert seleccion["MS-06"] == []
    # MS-05 y MS-07 siempre aplican, incluso sin lenguaje/ecosistema reconocido.
    assert len(seleccion["MS-05"]) == 1
    assert len(seleccion["MS-07"]) == 1
