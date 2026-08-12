"""
Test sin LLM: confirma que la evidencia compactada para el agente de
Seguridad (core/graph.py::compactar_ms05_para_agente/ms06/ms07) reduce
drásticamente el tamaño de la entrada enviada al LLM sin perder el dato
real (los conteos totales se conservan; solo se recorta la muestra de
hallazgos/dependencias a 8 elementos).
"""

import json

from core.coding_metrics import calcular_ms05, calcular_ms06, calcular_ms07
from core.graph import compactar_ms05_para_agente, compactar_ms06_para_agente, compactar_ms07_para_agente

# ---------------------------------------------------------
# Fixtures: evidencia cruda tal como la produce
# core/code_analysis/ (semgrep_analyzer / npm_audit_analyzer / secrets_analyzer)
# ---------------------------------------------------------

evidencia_semgrep = {
    "herramienta": "semgrep",
    "estado": "OK",
    "datos": {
        "hallazgos": [
            {
                "archivo": f"src/archivo_{i}.ts",
                "linea": i,
                "regla": f"regla-{i}",
                "mensaje": f"Hallazgo de prueba número {i}.",
                "severidad": "ERROR" if i < 3 else "WARNING",
                "critico": i < 3,
            }
            for i in range(12)
        ],
    },
    "detalle_error": None,
}

# 20 dependencias vulnerables (nombradas por npm audit) + 320 sin hallazgo
# conocido (representadas sin nombre, igual que produce npm_audit_analyzer.py).
dependencias_vulnerables = [
    {
        "nombre": f"paquete-vulnerable-{i}",
        "version": None,
        "rango_afectado": "<1.0.0",
        "severidad": "high" if i % 2 == 0 else "moderate",
        "vulnerabilidades": [{"id": f"GHSA-000{i}", "descripcion": f"Vulnerabilidad {i}"}],
        "segura": False,
    }
    for i in range(20)
]
dependencias_seguras = [
    {"nombre": None, "version": None, "vulnerabilidades": [], "segura": True}
    for _ in range(320)
]
evidencia_ms06 = {
    "herramienta": "npm-audit",
    "estado": "OK",
    "datos": {"dependencias": dependencias_vulnerables + dependencias_seguras},
    "detalle_error": None,
}

archivos_codigo_workspace = [f"src/archivo_{i}.ts" for i in range(50)]
evidencia_gitleaks = {
    "herramienta": "gitleaks",
    "estado": "OK",
    "secretos_detectados": 1,
    "archivos_con_secretos": ["src/archivo_0.ts"],
    "total_archivos_con_secretos": 1,
    "hallazgos": [
        {"archivo": "src/archivo_0.ts", "linea": 10, "regla": "generic-api-key", "tipo": "Generic API Key", "valor": "[REDACTED]"},
    ],
}


def _construir_entrada():
    ms05_calculado = calcular_ms05(evidencia_semgrep)
    ms06_calculado = calcular_ms06(evidencia_ms06)
    ms07_calculado = calcular_ms07(evidencia_gitleaks, archivos_codigo_workspace)

    return {
        "issue_iid": 1,
        "codificacion_id": "COD-001",
        "ms05": ms05_calculado,
        "ms06": ms06_calculado,
        "ms07": ms07_calculado,
        "evidencia_ms05": compactar_ms05_para_agente(evidencia_semgrep),
        "evidencia_ms06": compactar_ms06_para_agente(evidencia_ms06),
        "evidencia_ms07": compactar_ms07_para_agente(evidencia_gitleaks),
    }


def test_tamano_entrada_security_compactada():
    entrada = _construir_entrada()
    entrada_json = json.dumps([entrada], ensure_ascii=False)

    print("CHARS:", len(entrada_json))
    print("TOKENS APROX:", len(entrada_json) // 4)

    assert len(entrada_json) < 12000


def test_consistencia_no_se_pierde_el_dato_real():
    entrada = _construir_entrada()

    assert entrada["evidencia_ms06"]["dependencias_vulnerables"] == 20
    assert len(entrada["evidencia_ms06"]["muestras_relevantes"]) <= 8
    assert entrada["ms06"]["numerador"] == 320
    assert entrada["ms06"]["denominador"] == 340
    assert len(entrada["evidencia_ms05"]["hallazgos_relevantes"]) <= 8
    assert entrada["evidencia_ms05"]["total_hallazgos"] == 12
    assert entrada["ms07"]["denominador"] == 50
    assert entrada["ms07"]["numerador"] == 49
