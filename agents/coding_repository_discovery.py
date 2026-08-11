"""
Nodos del grafo para Codificación — Etapa de Descubrimiento del Repositorio.

Implementa la secuencia:
1. Descubrimiento automático del repositorio
2. Detección de tecnologías
3. Construcción del perfil técnico
4. Selección de herramientas
5. Validación COD ↔ ED ↔ repositorio
6. Construcción del contexto técnico

Sin ejecutar herramientas aún.
"""

from typing import Any
from integrations.gitlab_adapter import GitLabAdapter
from core.code_analysis.repository_discovery import descubrir_repositorio
from core.code_analysis.technology_detector import detectar_tecnologias
from core.code_analysis.repository_profile import construir_perfil_repositorio
from core.code_analysis.tool_selector import seleccionar_herramientas
from core.coding_repository_context import construir_contexto_repository_codificacion


def nodo_coding_repository_discovery(adapter: GitLabAdapter, state: dict) -> dict:
    """Ejecuta descubrimiento automático del repositorio.

    Obtiene:
    - Rama predeterminada
    - Árbol de archivos y directorios
    - Lenguajes detectados
    - Clasificación de manifiestos/lockfiles/config

    No ejecuta herramientas aún.
    """
    try:
        rama = adapter.obtener_rama_predeterminada()
        arbol = adapter.obtener_arbol_repositorio(ref=rama)
        descubrimiento = descubrir_repositorio(adapter, ref=rama)

        return {
            **state,
            "coding_repository_tree": arbol,
            "coding_repository_discovery": descubrimiento,
        }
    except Exception as e:
        return {
            **state,
            "coding_repository_tree": [],
            "coding_repository_discovery": {
                "estado": "ERROR",
                "error": str(e),
            },
        }


def nodo_coding_detect_technologies(adapter: GitLabAdapter, state: dict) -> dict:
    """Detecta tecnologías, frameworks y ecosistemas.

    Combina:
    - Lenguajes de GitLab
    - Archivos de manifiesto
    - Archivos de configuración
    - Lockfiles

    No invoca LLM.
    """
    try:
        descubrimiento = state.get("coding_repository_discovery", {})
        if descubrimiento.get("estado") == "ERROR":
            return {
                **state,
                "coding_detected_technologies": {"error": descubrimiento.get("error")},
            }

        tecnologias = detectar_tecnologias(descubrimiento, adapter=adapter)
        perfil = construir_perfil_repositorio(descubrimiento, tecnologias)

        return {
            **state,
            "coding_detected_technologies": tecnologias,
            "coding_repository_profile": perfil,
        }
    except Exception as e:
        return {
            **state,
            "coding_detected_technologies": {"estado": "ERROR", "error": str(e)},
            "coding_repository_profile": {},
        }


def nodo_coding_select_tools(state: dict) -> dict:
    """Selecciona automáticamente las herramientas de análisis.

    Basado en:
    - Lenguajes detectados
    - Ecosistemas
    - Frameworks

    NO ejecuta las herramientas.
    """
    try:
        perfil = state.get("coding_repository_profile", {})
        if not perfil:
            return {
                **state,
                "coding_selected_tools": {},
            }

        herramientas = seleccionar_herramientas(perfil)

        return {
            **state,
            "coding_selected_tools": herramientas,
        }
    except Exception as e:
        return {
            **state,
            "coding_selected_tools": {"estado": "ERROR", "error": str(e)},
        }


def nodo_coding_validate_and_contextualize(state: dict) -> dict:
    """Valida Issues COD y construye el contexto técnico.

    Compara:
    - Rutas declaradas en COD contra árbol del repositorio
    - Elementos de Diseño declarados contra matriz heredada
    - Resuelve requisitos (RF/RNF) vinculados

    Produce el contexto final antes de ejecutar herramientas.
    """
    try:
        coding_issues = state.get("coding_issues", [])
        repository_tree = state.get("coding_repository_tree", [])
        matriz_diseno = state.get("coding_matrix_input", [])
        herramientas = state.get("coding_selected_tools", {})

        if not repository_tree or not matriz_diseno:
            return {
                **state,
                "coding_repository_context": {
                    "estado": "ERROR",
                    "razon": "Árbol de repositorio o matriz de diseño no disponibles",
                },
            }

        perfil = state.get("coding_repository_profile", {})
        contexto = construir_contexto_repository_codificacion(
            coding_issues,
            perfil,
            herramientas,
            repository_tree,
            matriz_diseno,
        )

        return {
            **state,
            "coding_repository_context": contexto,
        }
    except Exception as e:
        return {
            **state,
            "coding_repository_context": {
                "estado": "ERROR",
                "error": str(e),
            },
        }
