"""
Utilidades compartidas por los analizadores de core/code_analysis/:
ejecución uniforme de subprocesos externos y redacción de secretos antes
de que cualquier evidencia llegue al contexto de un agente LLM.
"""

import subprocess


def ejecutar_comando(comando: list, cwd: str = None, timeout: int = 120) -> dict:
    """
    Ejecuta un comando de herramienta externa y clasifica el resultado.
    Nunca lanza excepción: cualquier fallo (herramienta ausente, timeout,
    error inesperado) se traduce a ejecutado=False con detalle, para que el
    analizador pueda diferenciar ERROR de un resultado negativo legítimo.
    """
    try:
        proceso = subprocess.run(
            comando, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except FileNotFoundError:
        return {
            "ejecutado": False, "returncode": None, "stdout": "", "stderr": "",
            "error": f"Herramienta no encontrada en el sistema: {comando[0]!r}.",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ejecutado": False, "returncode": None,
            "stdout": exc.stdout or "", "stderr": exc.stderr or "",
            "error": f"Tiempo de espera agotado ejecutando {comando[0]!r}.",
        }
    except Exception as exc:
        return {
            "ejecutado": False, "returncode": None, "stdout": "", "stderr": "",
            "error": f"Error inesperado ejecutando {comando[0]!r}: {exc}",
        }
    return {
        "ejecutado": True, "returncode": proceso.returncode,
        "stdout": proceso.stdout, "stderr": proceso.stderr, "error": None,
    }


def redactar_secreto(valor: str, prefijo_visible: int = 4) -> str:
    """Nunca se incluye el valor completo de una credencial en el contexto del LLM."""
    if not valor:
        return ""
    visible = valor[:prefijo_visible]
    return f"{visible}...[REDACTED]"
