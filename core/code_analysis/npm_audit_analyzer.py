"""
Analizador npm audit → evidencia para MS-06 (Cobertura de Dependencias
Seguras) en repositorios Node/npm, alternativa a pip-audit cuando el
ecosistema detectado es Node. Ejecuta `npm audit --json` directamente
sobre package.json + package-lock.json ya localizados y materializados
en el workspace de un COD (sin instalar node_modules) y normaliza la
salida a la MISMA forma que dependency_analyzer.py (datos.dependencias,
cada una con "segura"), para que
core/coding_metrics.py::calcular_ms06() la consuma sin cambios.

npm audit --json solo enumera por nombre los paquetes CON hallazgos
("vulnerabilities"); el resto de dependencias analizadas solo se conoce
como total agregado ("metadata.dependencies.total"). Para conservar el
mismo contrato de conteo (dependencias_seguras / dependencias_analizadas)
sin inventar nombres o versiones que npm audit no reporta, las
dependencias sin hallazgo conocido se representan como entradas sin
nombre, marcadas "segura": true.
"""

import json
import os
import shutil

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando


def ejecutar_npm_audit(workspace: str) -> dict:
    """Ejecuta npm audit sobre package.json + package-lock.json ya localizados en el workspace de un COD."""
    ruta_package_json = os.path.join(workspace, "package.json")
    ruta_lockfile = os.path.join(workspace, "package-lock.json")
    if not (os.path.isfile(ruta_package_json) and os.path.isfile(ruta_lockfile)):
        return resultado_herramienta(
            "npm-audit", ESTADO_NO_APLICA,
            detalle_error="No se localizó package.json/package-lock.json para este COD.",
        )

    npm_ejecutable = shutil.which("npm") or "npm"
    salida = ejecutar_comando([npm_ejecutable, "audit", "--json"], cwd=workspace, timeout=180)
    if not salida["ejecutado"]:
        return resultado_herramienta("npm-audit", ESTADO_ERROR, detalle_error=salida["error"])

    try:
        crudo = json.loads(salida["stdout"] or "{}")
    except json.JSONDecodeError as exc:
        return resultado_herramienta("npm-audit", ESTADO_ERROR, detalle_error=f"Salida de npm audit no es JSON válido: {exc}")

    metadata = crudo.get("metadata") or {}
    total_dependencias = (metadata.get("dependencies") or {}).get("total")
    if not total_dependencias:
        return resultado_herramienta(
            "npm-audit", ESTADO_NO_APLICA,
            detalle_error="npm audit no reportó dependencias analizadas.",
        )

    vulnerabilidades_por_paquete = crudo.get("vulnerabilities") or {}
    dependencias = []
    for nombre, info in vulnerabilidades_por_paquete.items():
        vias = info.get("via") or []
        vulnerabilidades = [
            {"id": via.get("url") or via.get("source"), "descripcion": via.get("title")}
            for via in vias if isinstance(via, dict)
        ]
        dependencias.append({
            "nombre": nombre,
            "version": None,
            "rango_afectado": info.get("range"),
            "severidad": info.get("severity"),
            "vulnerabilidades": vulnerabilidades,
            "segura": False,
        })

    dependencias_sin_vulnerabilidad_conocida = max(total_dependencias - len(dependencias), 0)
    for _ in range(dependencias_sin_vulnerabilidad_conocida):
        dependencias.append({
            "nombre": None,
            "version": None,
            "vulnerabilidades": [],
            "segura": True,
        })

    return resultado_herramienta("npm-audit", ESTADO_OK, datos={"dependencias": dependencias})
