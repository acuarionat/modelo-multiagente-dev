"""
Selección automática de herramientas de análisis basada en tecnologías
detectadas.

NO ejecuta herramientas, solo decide cuáles se necesitan. Cada métrica
puede tener más de una herramienta seleccionada cuando el repositorio
combina varios lenguajes/ecosistemas a la vez (p. ej. frontend
TypeScript + backend Python): core/code_analysis/orchestrator.py ejecuta
todas las seleccionadas y los resultados se consolidan por métrica.
"""

from typing import Any, Dict, List


def seleccionar_herramientas(repository_profile: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Elige qué herramientas aplicar según el perfil técnico.

    Args:
        repository_profile: salida de construir_perfil_repositorio()

    Retorna:
        {
            "MC-05": [
                {"tipo": "complejidad_ciclomatica", "herramienta": "eslint-complexity",
                 "adaptador": "eslint_complexity", "aplica_a": ["TypeScript", "JavaScript"], "estado": "pendiente"},
            ],
            "MS-05": [{"tipo": "analisis_estatico_seguridad", "herramienta": "semgrep", ...}],
            "MS-06": [{"tipo": "dependencias", "herramienta": "npm-audit", "ecosistema": "node", ...}],
            "MS-07": [{"tipo": "secretos", "herramienta": "gitleaks", ...}],
        }
    """
    lenguajes_presentes = {l["nombre"] for l in repository_profile.get("lenguajes", [])}
    ecosistemas_presentes = {e["id"] for e in repository_profile.get("ecosistemas", [])}

    # MC-05: Complejidad Ciclomática (Radon para Python, ESLint para JS/TS;
    # ambas si el repositorio combina los dos lenguajes).
    mc05 = []
    if "TypeScript" in lenguajes_presentes or "JavaScript" in lenguajes_presentes:
        mc05.append({
            "tipo": "complejidad_ciclomatica",
            "herramienta": "eslint-complexity",
            "adaptador": "eslint_complexity",
            "aplica_a": ["TypeScript", "JavaScript"],
            "estado": "pendiente",
        })
    if "Python" in lenguajes_presentes:
        mc05.append({
            "tipo": "complejidad_ciclomatica",
            "herramienta": "radon",
            "adaptador": "radon",
            "aplica_a": ["Python"],
            "estado": "pendiente",
        })

    # MS-05: Análisis Estático de Seguridad (Semgrep, multilenguaje, siempre aplica).
    ms05 = [{
        "tipo": "analisis_estatico_seguridad",
        "herramienta": "semgrep",
        "adaptador": "semgrep",
        "aplica_a": list(lenguajes_presentes),
        "estado": "pendiente",
    }]

    # MS-06: Auditoría de Dependencias (npm audit para Node, pip-audit para
    # Python; ambas si el repositorio combina los dos ecosistemas).
    ms06 = []
    if "node" in ecosistemas_presentes:
        ms06.append({
            "tipo": "dependencias",
            "herramienta": "npm-audit",
            "adaptador": "npm_audit",
            "ecosistema": "node",
            "estado": "pendiente",
        })
    if "python" in ecosistemas_presentes:
        ms06.append({
            "tipo": "dependencias",
            "herramienta": "pip-audit",
            "adaptador": "pip_audit",
            "ecosistema": "python",
            "estado": "pendiente",
        })

    # MS-07: Detección de Secretos (Gitleaks, repositorio completo, siempre aplica).
    ms07 = [{
        "tipo": "secretos",
        "herramienta": "gitleaks",
        "adaptador": "gitleaks",
        "repositorio_completo": True,
        "estado": "pendiente",
    }]

    return {"MC-05": mc05, "MS-05": ms05, "MS-06": ms06, "MS-07": ms07}
