"""
Modelos de datos estables para resultados de herramientas de análisis de
código (Radon, Semgrep, pip-audit, Gitleaks). Todos los analizadores
normalizan su salida cruda a estas estructuras antes de que cualquier otra
capa (métricas, agentes) las consuma.

Estados de herramienta: OK | NO_APLICA | ERROR. Un ERROR nunca se traduce
a 0 %: la métrica correspondiente queda NO_EVALUABLE (core/coding_metrics.py).
"""

ESTADO_OK = "OK"
ESTADO_NO_APLICA = "NO_APLICA"
ESTADO_ERROR = "ERROR"

ESTADOS_HERRAMIENTA_VALIDOS = {ESTADO_OK, ESTADO_NO_APLICA, ESTADO_ERROR}


def resultado_herramienta(nombre: str, estado: str, datos: dict = None, detalle_error: str = None) -> dict:
    """Envoltorio uniforme para el resultado de cualquier herramienta de análisis."""
    if estado not in ESTADOS_HERRAMIENTA_VALIDOS:
        raise ValueError(f"Estado de herramienta inválido: {estado!r}.")
    return {
        "herramienta": nombre,
        "estado": estado,
        "datos": datos or {},
        "detalle_error": detalle_error,
    }
