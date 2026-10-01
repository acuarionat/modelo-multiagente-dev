"""
Analizador Radon → evidencia para MC-05 (Adecuación de la Complejidad
Ciclomática). Ejecuta `radon cc --json` sobre el workspace de un COD y
normaliza la salida a una lista estable de funciones con su complejidad.
Aplica el umbral por función (Python decide, no el agente); el umbral
agregado de MC-05 (> 80 %) se calcula en core/coding_metrics.py.
"""

import json
import os

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando

UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE = 10  # CC ≤ 10 por función se considera aceptable.


def _archivos_python(workspace: str) -> list:
    archivos = []
    for raiz, _dirs, nombres in os.walk(workspace):
        for nombre in nombres:
            if nombre.endswith(".py"):
                archivos.append(os.path.join(raiz, nombre))
    return archivos


def ejecutar_radon(workspace: str) -> dict:
    """Ejecuta Radon sobre el workspace temporal de un COD y normaliza su salida a funciones evaluables."""
    if not _archivos_python(workspace):
        return resultado_herramienta(
            "radon", ESTADO_NO_APLICA,
            detalle_error="No hay archivos Python declarados para este COD.",
        )

    salida = ejecutar_comando(["radon", "cc", workspace, "--json"])
    if not salida["ejecutado"]:
        return resultado_herramienta("radon", ESTADO_ERROR, detalle_error=salida["error"])
    if salida["returncode"] != 0:
        return resultado_herramienta(
            "radon", ESTADO_ERROR,
            detalle_error=salida["stderr"] or "radon terminó con código de error.",
        )

    try:
        crudo = json.loads(salida["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        return resultado_herramienta("radon", ESTADO_ERROR, detalle_error=f"Salida de radon no es JSON válido: {exc}")

    funciones = []
    for ruta_absoluta, entradas in crudo.items():
        try:
            ruta_relativa = os.path.relpath(ruta_absoluta, workspace).replace(os.sep, "/")
        except ValueError:
            ruta_relativa = ruta_absoluta
        for entrada in entradas:
            complejidad = entrada.get("complexity")
            funciones.append({
                "archivo": ruta_relativa,
                "nombre": entrada.get("name"),
                "tipo": entrada.get("type"),
                "complejidad": complejidad,
                "rango": entrada.get("rank"),
                "linea_inicio": entrada.get("lineno"),
                "aceptable": complejidad is not None and complejidad <= UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE,
            })

    if not funciones:
        return resultado_herramienta(
            "radon", ESTADO_NO_APLICA,
            detalle_error="Radon no encontró funciones evaluables en los archivos declarados.",
        )

    return resultado_herramienta("radon", ESTADO_OK, datos={
        "umbral_complejidad_aceptable": UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE,
        "funciones": funciones,
    })
