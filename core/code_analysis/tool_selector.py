"""
Selección automática de herramientas de análisis basada en tecnologías detectadas.

NO ejecuta herramientas, solo decide cuáles se necesitan.
"""

from typing import Dict, Any


def seleccionar_herramientas(repository_profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Elige qué herramientas aplicar según el perfil técnico.

    Args:
        repository_profile: salida de construir_perfil_repositorio()

    Retorna:
        {
            "MC-05": {
                "tipo": "complejidad_ciclomatica",
                "herramienta": "eslint",
                "adaptador": "eslint_complexity",
                "aplica_a": ["TypeScript", "JavaScript"]
            },
            "MS-05": {"tipo": "analisis_estatico_seguridad", "herramienta": "semgrep"},
            "MS-06": {"tipo": "dependencias", "herramienta": "npm-audit", "ecosistema": "node"},
            "MS-07": {"tipo": "secretos", "herramienta": "gitleaks"}
        }
    """
    herramientas_seleccionadas = {}
    lenguajes_presentes = {l["nombre"] for l in repository_profile.get("lenguajes", [])}
    ecosistemas_presentes = {e["id"] for e in repository_profile.get("ecosistemas", [])}

    # MC-05: Complejidad Ciclomática
    if "TypeScript" in lenguajes_presentes or "JavaScript" in lenguajes_presentes:
        herramientas_seleccionadas["MC-05"] = {
            "tipo": "complejidad_ciclomatica",
            "herramienta": "eslint",
            "adaptador": "eslint_complexity",
            "aplica_a": ["TypeScript", "JavaScript"],
            "estado": "pendiente"
        }
    elif "Python" in lenguajes_presentes:
        herramientas_seleccionadas["MC-05"] = {
            "tipo": "complejidad_ciclomatica",
            "herramienta": "radon",
            "adaptador": "radon_complexity",
            "aplica_a": ["Python"],
            "estado": "pendiente"
        }

    # MS-05: Análisis Estático de Seguridad
    herramientas_seleccionadas["MS-05"] = {
        "tipo": "analisis_estatico_seguridad",
        "herramienta": "semgrep",
        "adaptador": "semgrep_analyzer",
        "aplica_a": list(lenguajes_presentes),
        "estado": "pendiente"
    }

    # MS-06: Auditoría de Dependencias
    if "node" in ecosistemas_presentes:
        herramientas_seleccionadas["MS-06"] = {
            "tipo": "dependencias",
            "herramienta": "npm-audit",
            "adaptador": "npm_audit_analyzer",
            "ecosistema": "node",
            "estado": "pendiente"
        }
    elif "python" in ecosistemas_presentes:
        herramientas_seleccionadas["MS-06"] = {
            "tipo": "dependencias",
            "herramienta": "pip-audit",
            "adaptador": "pip_audit_analyzer",
            "ecosistema": "python",
            "estado": "pendiente"
        }

    # MS-07: Detección de Secretos (siempre aplica)
    herramientas_seleccionadas["MS-07"] = {
        "tipo": "secretos",
        "herramienta": "gitleaks",
        "adaptador": "gitleaks_analyzer",
        "repositorio_completo": True,
        "estado": "pendiente"
    }

    return herramientas_seleccionadas
