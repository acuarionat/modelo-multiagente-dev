"""
Perfil de repositorio — objeto estable reutilizable por UI, PDF, DOCX y herramientas.

No contiene el árbol completo (evita pasar 300 archivos), sino información
consolidada sobre estructura, ecosistema y configuración técnica.
"""

from typing import Dict, List, Any


def construir_perfil_repositorio(
    descubrimiento: Dict[str, Any],
    tecnologias_detectadas: Dict[str, Any],
) -> Dict[str, Any]:
    """Construye el perfil técnico consolidado del repositorio.

    Args:
        descubrimiento: salida de descubrir_repositorio()
        tecnologias_detectadas: salida de detectar_tecnologias()

    Retorna:
        {
            "rama": "main",
            "lenguajes": [...],
            "ecosistemas": [...],
            "frameworks_tecnologias": ["React", "Vite", "Firebase"],
            "estructura": {
                "total_archivos": 86,
                "total_directorios": 14,
                "archivos_codigo": 61
            },
            "manifiestos": ["package.json"],
            "lockfiles": ["package-lock.json"],
            "archivos_configuracion": ["tsconfig.json", "vite.config.ts", ...]
        }
    """
    lenguajes = tecnologias_detectadas.get("lenguajes", [])
    ecosistemas = tecnologias_detectadas.get("ecosistemas", [])
    tecnologias = tecnologias_detectadas.get("tecnologias_detectadas", [])

    frameworks_tecnologias = []
    for tech in tecnologias:
        tipo = tech.get("tipo", "")
        if tipo in ["framework", "framework_backend", "herramienta_framework", "plataforma"]:
            frameworks_tecnologias.append(tech["nombre"])

    return {
        "rama": descubrimiento.get("rama", "main"),
        "lenguajes": lenguajes,
        "ecosistemas": ecosistemas,
        "frameworks_tecnologias": frameworks_tecnologias,
        "estructura": {
            "total_archivos": descubrimiento.get("total_archivos", 0),
            "total_directorios": descubrimiento.get("total_directorios", 0),
            "archivos_codigo": len(descubrimiento.get("archivos_codigo", [])),
        },
        "manifiestos": descubrimiento.get("manifiestos", []),
        "lockfiles": descubrimiento.get("lockfiles", []),
        "archivos_configuracion": descubrimiento.get("configuracion_tecnica", []),
    }
