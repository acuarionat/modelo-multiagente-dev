"""
Analizador Gitleaks → evidencia para MS-07 (Cobertura de Código sin
Secretos Expuestos). Ejecuta `gitleaks detect --no-git` sobre el workspace
temporal de un COD y normaliza los hallazgos, redactando cualquier valor
de secreto antes de que llegue al contexto de un agente LLM.
MS-07 = archivos_sin_secretos / archivos_analizados, calculado en Python
(core/coding_metrics.py).
"""

import json
import os
import tempfile

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando, redactar_secreto


def _archivos_en_workspace(workspace: str) -> list:
    archivos = []
    for raiz, _dirs, nombres in os.walk(workspace):
        for nombre in nombres:
            ruta = os.path.relpath(os.path.join(raiz, nombre), workspace).replace(os.sep, "/")
            archivos.append(ruta)
    return archivos


def ejecutar_gitleaks(workspace: str) -> dict:
    """Ejecuta Gitleaks sobre el workspace temporal de un COD y normaliza sus hallazgos, redactando secretos."""
    archivos_analizados = _archivos_en_workspace(workspace)
    if not archivos_analizados:
        return resultado_herramienta(
            "gitleaks", ESTADO_NO_APLICA,
            detalle_error="No hay archivos declarados para este COD.",
        )

    descriptor, ruta_reporte = tempfile.mkstemp(suffix=".json")
    os.close(descriptor)
    try:
        salida = ejecutar_comando(
            [
                "gitleaks", "detect",
                "--source", workspace,
                "--no-git",
                "--report-format", "json",
                "--report-path", ruta_reporte,
                "--exit-code", "0",
            ],
            timeout=180,
        )
        if not salida["ejecutado"]:
            return resultado_herramienta("gitleaks", ESTADO_ERROR, detalle_error=salida["error"])
        if salida["returncode"] != 0:
            return resultado_herramienta(
                "gitleaks", ESTADO_ERROR,
                detalle_error=salida["stderr"] or "gitleaks terminó con código de error.",
            )

        try:
            with open(ruta_reporte, "r", encoding="utf-8") as handle:
                contenido = handle.read().strip()
        except OSError as exc:
            return resultado_herramienta("gitleaks", ESTADO_ERROR, detalle_error=f"No se pudo leer el reporte de gitleaks: {exc}")

        try:
            hallazgos_crudos = json.loads(contenido) if contenido else []
        except json.JSONDecodeError as exc:
            return resultado_herramienta("gitleaks", ESTADO_ERROR, detalle_error=f"Salida de gitleaks no es JSON válido: {exc}")
    finally:
        try:
            os.remove(ruta_reporte)
        except OSError:
            pass

    archivos_con_secretos = set()
    hallazgos = []
    for item in hallazgos_crudos:
        ruta = item.get("File") or item.get("file")
        if ruta:
            archivos_con_secretos.add(ruta)
        hallazgos.append({
            "archivo": ruta,
            "regla": item.get("RuleID") or item.get("rule"),
            "linea": item.get("StartLine") or item.get("line"),
            "secreto_redactado": redactar_secreto(item.get("Secret") or item.get("secret") or ""),
        })

    return resultado_herramienta("gitleaks", ESTADO_OK, datos={
        "archivos_analizados": archivos_analizados,
        "archivos_con_secretos": sorted(archivos_con_secretos),
        "hallazgos": hallazgos,
    })
