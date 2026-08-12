"""
Orquestador de ejecución de herramientas de análisis de código.

Recibe la selección ya decidida por
core/code_analysis/tool_selector.py::seleccionar_herramientas()
(coding_selected_tools) y ejecuta ÚNICAMENTE los analizadores
seleccionados sobre el workspace ya materializado de un COD, en vez del
bloque fijo Radon+Semgrep+pip-audit+Gitleaks. Este módulo no decide qué
herramientas usar (eso ya lo decidió tool_selector.py): solo las invoca
y agrupa sus resultados ya normalizados (core/code_analysis/models.py).
"""

from typing import Any, Dict, List, Optional

from core.code_analysis.dependency_analyzer import ejecutar_pip_audit
from core.code_analysis.eslint_complexity_analyzer import ejecutar_eslint_complexity
from core.code_analysis.models import ESTADO_NO_APLICA, resultado_herramienta
from core.code_analysis.npm_audit_analyzer import ejecutar_npm_audit
from core.code_analysis.radon_analyzer import ejecutar_radon
from core.code_analysis.secrets_analyzer import ejecutar_gitleaks
from core.code_analysis.semgrep_analyzer import ejecutar_semgrep

# MC-05 y MS-06 pueden resolverse con más de un adaptador según el
# lenguaje/ecosistema real (ver tool_selector.py); el resto del sistema
# (coding_metrics.py, prompts) consume la evidencia por métrica, no por
# nombre de herramienta.
ADAPTADORES_MC05 = ("radon", "eslint_complexity")
ADAPTADORES_MS06 = ("pip_audit", "npm_audit")


def _ejecutar_adaptador(adaptador: str, workspace: str, manifiesto_dependencias: dict) -> Dict[str, Any]:
    if adaptador == "radon":
        return ejecutar_radon(workspace)
    if adaptador == "eslint_complexity":
        return ejecutar_eslint_complexity(workspace)
    if adaptador == "semgrep":
        return ejecutar_semgrep(workspace)
    if adaptador == "pip_audit":
        return ejecutar_pip_audit(manifiesto_dependencias or {}, workspace)
    if adaptador == "npm_audit":
        return ejecutar_npm_audit(workspace)
    if adaptador == "gitleaks":
        return ejecutar_gitleaks(workspace)
    return resultado_herramienta(
        adaptador, ESTADO_NO_APLICA, detalle_error=f"Adaptador desconocido: {adaptador!r}.",
    )


def ejecutar_analizadores_seleccionados(
    workspace: str,
    herramientas_seleccionadas: Dict[str, List[Dict[str, Any]]],
    repository_profile: Dict[str, Any],
    manifiesto_dependencias: Optional[dict] = None,
) -> Dict[str, Any]:
    """Ejecuta únicamente los adaptadores seleccionados por métrica.

    Args:
        workspace: directorio temporal ya materializado con el código del COD.
        herramientas_seleccionadas: salida de tool_selector.seleccionar_herramientas().
        repository_profile: perfil técnico del repositorio (contexto informativo
            de la selección; no se usa para decidir ejecución, eso ya lo decidió
            tool_selector.py).
        manifiesto_dependencias: manifiesto de dependencias Python localizado
            (integrations/code_repository_service.py), requerido por el
            adaptador "pip_audit".

    Retorna:
        {"<adaptador>": resultado_herramienta(...), ...} — una clave por
        cada adaptador realmente seleccionado y ejecutado (sin duplicar
        ejecuciones si dos métricas comparten el mismo adaptador).
    """
    adaptadores_a_ejecutar = set()
    for entradas in (herramientas_seleccionadas or {}).values():
        for entrada in entradas:
            adaptador = entrada.get("adaptador")
            if adaptador:
                adaptadores_a_ejecutar.add(adaptador)

    return {
        adaptador: _ejecutar_adaptador(adaptador, workspace, manifiesto_dependencias)
        for adaptador in adaptadores_a_ejecutar
    }


def obtener_evidencia_por_metrica(coding_tool_results: Dict[str, Any]) -> Dict[str, Any]:
    """Resuelve, por métrica, qué evidencia de coding_tool_results le corresponde.

    MC-05 y MS-06 pueden tener más de un adaptador posible (Radon o
    ESLint; pip-audit o npm audit) según el lenguaje/ecosistema real del
    repositorio: se usa el primero que exista en coding_tool_results.
    MS-05 y MS-07 siempre usan semgrep/gitleaks (únicos adaptadores del
    catálogo para esas métricas).
    """
    tool_results = coding_tool_results or {}

    def _primero_disponible(adaptadores):
        for adaptador in adaptadores:
            if adaptador in tool_results:
                return tool_results[adaptador]
        return None

    return {
        "MC-05": _primero_disponible(ADAPTADORES_MC05),
        "MS-05": tool_results.get("semgrep"),
        "MS-06": _primero_disponible(ADAPTADORES_MS06),
        "MS-07": tool_results.get("gitleaks"),
    }
