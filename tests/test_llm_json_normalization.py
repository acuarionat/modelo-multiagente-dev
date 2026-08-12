"""
Test de agents/llm_invocation.py::normalizar_json_llm(): normalización
sintáctica MÍNIMA (solo fences Markdown), sin reparaciones agresivas.
"""

import json

from agents.llm_invocation import normalizar_json_llm


def test_json_puro():
    raw = '{"resultados":[]}'
    assert json.loads(normalizar_json_llm(raw)) == {"resultados": []}


def test_json_con_fence():
    raw = """```json
{"resultados":[]}
```"""
    assert json.loads(normalizar_json_llm(raw)) == {"resultados": []}


def test_texto_extra_no_se_repara():
    raw = """
    Aquí está el resultado:
    {"resultados":[]}
    """
    limpio = normalizar_json_llm(raw)
    try:
        json.loads(limpio)
        assert False
    except json.JSONDecodeError:
        pass
