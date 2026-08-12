"""
Etiquetas de presentación para las herramientas de análisis técnico.

Traduce el nombre interno de la herramienta ("herramienta" en la
evidencia normalizada de core/code_analysis/) a un nombre legible para
UI, PDF, DOCX y prompts, sin asumir en ningún lugar de la presentación
que la herramienta usada es siempre Radon/pip-audit.
"""

ETIQUETAS_HERRAMIENTAS = {
    "radon": "Radon",
    "eslint-complexity": "ESLint Complexity",
    "eslint_complexity": "ESLint Complexity",
    "semgrep": "Semgrep",
    "npm-audit": "npm audit",
    "npm_audit": "npm audit",
    "pip-audit": "pip-audit",
    "pip_audit": "pip-audit",
    "gitleaks": "Gitleaks",
}


def obtener_etiqueta_herramienta(nombre) -> str:
    clave = str(nombre or "").strip()
    return ETIQUETAS_HERRAMIENTAS.get(clave, clave or "Analizador técnico")
