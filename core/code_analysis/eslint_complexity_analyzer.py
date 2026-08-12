"""
Analizador ESLint (regla "complexity") → evidencia para MC-05 en
repositorios JavaScript/TypeScript, alternativa a Radon cuando el
lenguaje detectado no es Python. Ejecuta ESLint únicamente con la regla
"complexity" habilitada (umbral 0, para que reporte la complejidad de
TODAS las funciones, no solo las que exceden un umbral) sobre el
workspace de un COD, y normaliza la salida a la MISMA forma que
radon_analyzer.py (datos.funciones, cada una con "aceptable"), para que
core/coding_metrics.py::calcular_mc05() la consuma sin cambios.

Requiere ESLint y @typescript-eslint/parser instalados localmente en el
proyecto (package.json en la raíz, node_modules/): no se instalan por red
en cada ejecución (--no-install).
"""

import json
import os
import re
import shutil

from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK, resultado_herramienta
from core.code_analysis.normalizer import ejecutar_comando
from core.config import BASE_DIR

UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE = 10  # Mismo umbral que radon_analyzer.py.

EXTENSIONES_JS_TS = (".js", ".jsx", ".ts", ".tsx")

RUTA_CONFIG_ESLINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eslint_complexity.config.mjs")

PATRON_COMPLEJIDAD = re.compile(r"has a complexity of (\d+)")
PATRON_NOMBRE_FUNCION = re.compile(r"^Function '([^']+)'")
PATRON_NOMBRE_METODO = re.compile(r"^Method '([^']+)'")


def _archivos_js_ts(workspace: str) -> list:
    archivos = []
    for raiz, _dirs, nombres in os.walk(workspace):
        for nombre in nombres:
            if nombre.endswith(EXTENSIONES_JS_TS):
                archivos.append(os.path.join(raiz, nombre))
    return archivos


def _tipo_y_nombre(mensaje: str) -> tuple:
    if mensaje.startswith("Arrow function"):
        return "arrow_function", None
    coincidencia_funcion = PATRON_NOMBRE_FUNCION.match(mensaje)
    if coincidencia_funcion:
        return "function", coincidencia_funcion.group(1)
    coincidencia_metodo = PATRON_NOMBRE_METODO.match(mensaje)
    if coincidencia_metodo:
        return "method", coincidencia_metodo.group(1)
    return "function", None


def ejecutar_eslint_complexity(workspace: str) -> dict:
    """Ejecuta ESLint (regla complexity) sobre el workspace temporal de un COD y normaliza su salida a funciones evaluables."""
    if not _archivos_js_ts(workspace):
        return resultado_herramienta(
            "eslint-complexity", ESTADO_NO_APLICA,
            detalle_error="No hay archivos JavaScript/TypeScript declarados para este COD.",
        )

    npx_ejecutable = shutil.which("npx") or "npx"
    salida = ejecutar_comando(
        [
            npx_ejecutable, "--no-install", "--prefix", str(BASE_DIR), "eslint",
            "--no-config-lookup", "-c", RUTA_CONFIG_ESLINT,
            "--format", "json", ".",
        ],
        cwd=workspace, timeout=120,
    )
    if not salida["ejecutado"]:
        return resultado_herramienta("eslint-complexity", ESTADO_ERROR, detalle_error=salida["error"])
    # ESLint: 0 = sin hallazgos, 1 = hallazgos encontrados (regla "error"), no es fallo de ejecución.
    if salida["returncode"] not in (0, 1):
        return resultado_herramienta(
            "eslint-complexity", ESTADO_ERROR,
            detalle_error=salida["stderr"] or "eslint terminó con código de error.",
        )

    try:
        crudo = json.loads(salida["stdout"] or "[]")
    except json.JSONDecodeError as exc:
        return resultado_herramienta("eslint-complexity", ESTADO_ERROR, detalle_error=f"Salida de eslint no es JSON válido: {exc}")

    funciones = []
    for archivo_resultado in crudo:
        ruta_absoluta = archivo_resultado.get("filePath") or ""
        try:
            ruta_relativa = os.path.relpath(ruta_absoluta, workspace).replace(os.sep, "/")
        except ValueError:
            ruta_relativa = ruta_absoluta
        for mensaje in archivo_resultado.get("messages", []):
            if mensaje.get("ruleId") != "complexity":
                continue
            texto = mensaje.get("message") or ""
            coincidencia = PATRON_COMPLEJIDAD.search(texto)
            complejidad = int(coincidencia.group(1)) if coincidencia else None
            tipo, nombre = _tipo_y_nombre(texto)
            funciones.append({
                "archivo": ruta_relativa,
                "nombre": nombre,
                "tipo": tipo,
                "complejidad": complejidad,
                "linea_inicio": mensaje.get("line"),
                "aceptable": complejidad is not None and complejidad <= UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE,
            })

    if not funciones:
        return resultado_herramienta(
            "eslint-complexity", ESTADO_NO_APLICA,
            detalle_error="ESLint no encontró funciones evaluables en los archivos declarados.",
        )

    return resultado_herramienta("eslint-complexity", ESTADO_OK, datos={
        "umbral_complejidad_aceptable": UMBRAL_COMPLEJIDAD_CICLOMATICA_ACEPTABLE,
        "funciones": funciones,
    })
