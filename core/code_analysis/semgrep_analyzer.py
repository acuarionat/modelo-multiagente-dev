"""
Analizador Semgrep → evidencia para MS-05 (Vulnerabilidades Críticas
Detectadas). Ejecuta `semgrep --config auto --json` sobre el workspace
temporal de un COD y normaliza los hallazgos a una lista estable. El
agente no decide cuántas vulnerabilidades existen: MS-05 es un conteo
calculado en Python (core/coding_metrics.py) a partir de esta evidencia.
"""

import json
import os

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando

SEVERIDADES_CRITICAS = {"ERROR"}  # Semgrep: INFO < WARNING < ERROR.


def _hay_archivos(workspace: str) -> bool:
    for _raiz, _dirs, nombres in os.walk(workspace):
        if nombres:
            return True
    return False


def ejecutar_semgrep(workspace: str) -> dict:
    """Ejecuta Semgrep (config auto) sobre el workspace temporal de un COD y normaliza sus hallazgos."""
    if not _hay_archivos(workspace):
        return resultado_herramienta(
            "semgrep", ESTADO_NO_APLICA,
            detalle_error="No hay archivos declarados para este COD.",
        )

    salida = ejecutar_comando(["semgrep", "--config", "auto", "--json", workspace], timeout=180)
    if not salida["ejecutado"]:
        return resultado_herramienta("semgrep", ESTADO_ERROR, detalle_error=salida["error"])
    if salida["returncode"] not in (0, 1):  # 1 = hallazgos encontrados, no es fallo de ejecución.
        return resultado_herramienta(
            "semgrep", ESTADO_ERROR,
            detalle_error=salida["stderr"] or "semgrep terminó con código de error.",
        )

    try:
        crudo = json.loads(salida["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        return resultado_herramienta("semgrep", ESTADO_ERROR, detalle_error=f"Salida de semgrep no es JSON válido: {exc}")

    hallazgos = []
    for item in crudo.get("results", []):
        extra = item.get("extra") or {}
        severidad = str(extra.get("severity") or "").upper()
        hallazgos.append({
            "archivo": item.get("path"),
            "linea": (item.get("start") or {}).get("line"),
            "regla": item.get("check_id"),
            "mensaje": extra.get("message"),
            "severidad": severidad,
            "critico": severidad in SEVERIDADES_CRITICAS,
        })

    return resultado_herramienta("semgrep", ESTADO_OK, datos={"hallazgos": hallazgos})
