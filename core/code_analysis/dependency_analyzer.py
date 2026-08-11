"""
Analizador pip-audit → evidencia para MS-06 (Cobertura de Dependencias
Seguras). Ejecuta pip-audit sobre el manifiesto de dependencias localizado
por integrations/code_repository_service.py y normaliza los hallazgos.
MS-06 = dependencias_seguras / dependencias_analizadas, calculado en
Python (core/coding_metrics.py), no por el agente.
"""

import json
import os
import sys

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando

MANIFIESTOS_SOPORTADOS_DIRECTAMENTE = {"requirements.txt"}


def ejecutar_pip_audit(manifiesto: dict, workspace: str) -> dict:
    """Ejecuta pip-audit sobre el manifiesto de dependencias declarado del COD, si existe y es soportado."""
    if not manifiesto.get("encontrado"):
        return resultado_herramienta(
            "pip-audit", ESTADO_NO_APLICA,
            detalle_error="No se localizó manifiesto de dependencias en el repositorio.",
        )
    if manifiesto.get("estado") != "OK":
        return resultado_herramienta(
            "pip-audit", ESTADO_ERROR,
            detalle_error=manifiesto.get("error") or "No se pudo descargar el manifiesto de dependencias.",
        )

    nombre_manifiesto = os.path.basename(manifiesto["ruta"])
    if nombre_manifiesto not in MANIFIESTOS_SOPORTADOS_DIRECTAMENTE:
        # pip-audit resuelve directamente requirements.txt; otros manifiestos
        # (pyproject.toml, Pipfile) requieren resolución de entorno que este
        # servicio no realiza en este alcance: se reporta NO_APLICA, no 0 %.
        return resultado_herramienta(
            "pip-audit", ESTADO_NO_APLICA,
            detalle_error=(
                f"Manifiesto {nombre_manifiesto!r} no es requirements.txt; "
                "pip-audit no se ejecuta sobre él en este alcance."
            ),
        )

    ruta_local = os.path.join(workspace, nombre_manifiesto)
    salida = ejecutar_comando(
        [sys.executable, "-m", "pip_audit", "-r", ruta_local, "--format", "json"],
        timeout=180,
    )
    if not salida["ejecutado"]:
        return resultado_herramienta("pip-audit", ESTADO_ERROR, detalle_error=salida["error"])
    if salida["returncode"] not in (0, 1):  # 1 = vulnerabilidades encontradas, no es fallo de ejecución.
        return resultado_herramienta(
            "pip-audit", ESTADO_ERROR,
            detalle_error=salida["stderr"] or "pip-audit terminó con código de error.",
        )

    try:
        crudo = json.loads(salida["stdout"] or "[]")
    except json.JSONDecodeError as exc:
        return resultado_herramienta("pip-audit", ESTADO_ERROR, detalle_error=f"Salida de pip-audit no es JSON válido: {exc}")

    dependencias_crudas = crudo.get("dependencies", []) if isinstance(crudo, dict) else crudo
    if not isinstance(dependencias_crudas, list):
        return resultado_herramienta("pip-audit", ESTADO_ERROR, detalle_error="Formato de salida de pip-audit no reconocido.")

    dependencias = []
    for dependencia in dependencias_crudas:
        vulnerabilidades = dependencia.get("vulns") or []
        dependencias.append({
            "nombre": dependencia.get("name"),
            "version": dependencia.get("version"),
            "vulnerabilidades": [
                {"id": vuln.get("id"), "descripcion": vuln.get("description")}
                for vuln in vulnerabilidades
            ],
            "segura": not vulnerabilidades,
        })

    if not dependencias:
        return resultado_herramienta(
            "pip-audit", ESTADO_NO_APLICA,
            detalle_error="El manifiesto no declara dependencias.",
        )

    return resultado_herramienta("pip-audit", ESTADO_OK, datos={"dependencias": dependencias})
