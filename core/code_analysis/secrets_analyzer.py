"""
Analizador Gitleaks → evidencia para MS-07 (Cobertura de Código sin
Secretos Expuestos). Ejecuta `gitleaks dir` sobre el workspace temporal
de un COD y normaliza sus hallazgos, redactando siempre el valor real
del secreto (--redact en la ejecución, y "valor": "[REDACTED]" en cada
hallazgo normalizado).

Este analizador solo reporta qué encontró Gitleaks (secretos y archivos
con secretos): NO calcula MS-07. MS-07 = archivos de código analizados
sin secretos / archivos de código analizados, y requiere el universo de
archivos de código del COD (obtener_archivos_codigo_workspace), ajeno a
lo que Gitleaks reporta. El cálculo vive en
core/coding_metrics.py::calcular_ms07().
"""

import json
import os
import tempfile

from core.code_analysis.models import ESTADO_ERROR, ESTADO_OK
from core.code_analysis.normalizer import ejecutar_comando

EXTENSIONES_CODIGO = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cs", ".php", ".go", ".rb",
    ".vue", ".svelte",
}


def obtener_archivos_codigo_workspace(workspace: str) -> list:
    """
    Universo de archivos de código analizables para MS-07: rutas
    relativas al workspace cuya extensión corresponde a código fuente
    (EXTENSIONES_CODIGO), excluyendo binarios, lockfiles, manifiestos y
    demás recursos no textuales.
    """
    archivos = []
    for raiz, _dirs, nombres in os.walk(workspace):
        for nombre in nombres:
            _, extension = os.path.splitext(nombre)
            if extension.casefold() not in EXTENSIONES_CODIGO:
                continue
            ruta_relativa = os.path.relpath(os.path.join(raiz, nombre), workspace).replace(os.sep, "/")
            archivos.append(ruta_relativa)
    return archivos


def ejecutar_gitleaks(workspace: str) -> dict:
    """
    Ejecuta Gitleaks sobre el workspace temporal de un COD y normaliza
    sus hallazgos. Códigos de retorno de Gitleaks: 0 = sin leaks (OK),
    1 = leaks encontrados (OK), 2+ = error técnico.
    """
    descriptor, ruta_reporte = tempfile.mkstemp(suffix=".json")
    os.close(descriptor)

    try:
        salida = ejecutar_comando(
            [
                "gitleaks", "dir", str(workspace),
                "--report-format", "json",
                "--report-path", str(ruta_reporte),
                "--redact",
                "--no-banner",
            ],
            timeout=180,
        )

        if not salida["ejecutado"]:
            return {
                "herramienta": "gitleaks",
                "estado": ESTADO_ERROR,
                "motivo": salida["error"],
                "hallazgos": [],
            }

        if salida["returncode"] not in {0, 1}:
            return {
                "herramienta": "gitleaks",
                "estado": ESTADO_ERROR,
                "motivo": (salida["stderr"] or "").strip() or "gitleaks terminó con código de error.",
                "hallazgos": [],
            }

        try:
            with open(ruta_reporte, "r", encoding="utf-8") as handle:
                contenido = handle.read().strip()
            hallazgos_raw = json.loads(contenido) if contenido else []
        except (OSError, json.JSONDecodeError):
            hallazgos_raw = []
    finally:
        try:
            os.remove(ruta_reporte)
        except OSError:
            pass

    hallazgos = []
    for item in hallazgos_raw:
        hallazgos.append({
            "archivo": str(item.get("File", "")).replace("\\", "/"),
            "linea": item.get("StartLine"),
            "regla": item.get("RuleID") or item.get("Description"),
            "tipo": item.get("Description"),
            "valor": "[REDACTED]",
        })

    archivos_con_secretos = sorted({
        item["archivo"]
        for item in hallazgos
        if item.get("archivo")
    })

    return {
        "herramienta": "gitleaks",
        "estado": ESTADO_OK,
        "secretos_detectados": len(hallazgos),
        "archivos_con_secretos": archivos_con_secretos,
        "total_archivos_con_secretos": len(archivos_con_secretos),
        "hallazgos": hallazgos,
    }
