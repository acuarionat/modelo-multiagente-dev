"""
Detección de tecnologías y ecosistemas sin invocar LLM.

Combina evidencia de archivos, manifiestos y lenguajes para identificar
frameworks, librerías y plataformas en uso.
"""

import json
from typing import Dict, List, Any, Optional
from integrations.gitlab_adapter import GitLabAdapter


def detectar_tecnologias(
    descubrimiento: Dict[str, Any],
    adapter: Optional[GitLabAdapter] = None,
) -> Dict[str, Any]:
    """Detecta tecnologías, frameworks y ecosistemas del repositorio.

    Usa evidencia de:
    - Archivos de manifiesto (package.json, requirements.txt, etc.)
    - Archivos de configuración (vite.config.ts, jest.config.js, etc.)
    - Lenguajes detectados por GitLab
    - Lockfiles

    Args:
        descubrimiento: salida de descubrir_repositorio()
        adapter: GitLabAdapter opcional para leer manifiestos si es necesario

    Retorna:
        {
            "lenguajes": [...],
            "ecosistemas": [
                {
                    "id": "node",
                    "nombre": "Node.js",
                    "evidencias": ["package.json", "package-lock.json"],
                    "gestor_dependencias": "npm"
                }
            ],
            "tecnologias_detectadas": [
                {"nombre": "TypeScript", "tipo": "lenguaje"},
                {"nombre": "Vite", "tipo": "herramienta_framework", "evidencia": "vite.config.ts"},
                {"nombre": "React", "tipo": "framework", "evidencia": "package.json"}
            ]
        }
    """
    ecosistemas = []
    tecnologias = []
    lenguajes = descubrimiento.get("lenguajes", [])

    archivos = set(descubrimiento.get("archivos", []))
    manifiestos = set(descubrimiento.get("manifiestos", []))
    lockfiles = set(descubrimiento.get("lockfiles", []))
    config_files = set(descubrimiento.get("configuracion_tecnica", []))

    dependencies_by_file = {}
    if adapter:
        for manifest in manifiestos:
            try:
                contenido = adapter.obtener_archivo_repositorio(manifest)
                if contenido:
                    dependencies_by_file[manifest] = contenido.decode('utf-8', errors='ignore')
            except Exception:
                pass

    nombres_manifiestos = {ruta.rsplit("/", 1)[-1] for ruta in manifiestos}
    nombres_lockfiles = {ruta.rsplit("/", 1)[-1] for ruta in lockfiles}
    nombres_config = {ruta.rsplit("/", 1)[-1] for ruta in config_files}

    # Detectar Node.js / npm
    if "package.json" in nombres_manifiestos or "package-lock.json" in nombres_lockfiles:
        evidencias = []
        gestor = "npm"
        if "package.json" in nombres_manifiestos:
            evidencias.append("package.json")
        if "package-lock.json" in nombres_lockfiles:
            evidencias.append("package-lock.json")
        elif "yarn.lock" in nombres_lockfiles:
            evidencias.append("yarn.lock")
            gestor = "yarn"
        elif "pnpm-lock.yaml" in nombres_lockfiles:
            evidencias.append("pnpm-lock.yaml")
            gestor = "pnpm"

        ecosistemas.append({
            "id": "node",
            "nombre": "Node.js",
            "evidencias": evidencias,
            "gestor_dependencias": gestor
        })

    # Detectar Python
    if nombres_manifiestos & {"requirements.txt", "pyproject.toml", "Pipfile"}:
        evidencias = []
        if "requirements.txt" in nombres_manifiestos:
            evidencias.append("requirements.txt")
        if "pyproject.toml" in nombres_manifiestos:
            evidencias.append("pyproject.toml")
        if "Pipfile" in nombres_manifiestos:
            evidencias.append("Pipfile")

        ecosistemas.append({
            "id": "python",
            "nombre": "Python",
            "evidencias": evidencias,
            "gestor_dependencias": "pip" if "requirements.txt" in nombres_manifiestos else (
                "poetry" if "pyproject.toml" in nombres_manifiestos else "pipenv"
            )
        })

    # Agregar lenguajes detectados
    for lang in lenguajes:
        tecnologias.append({
            "nombre": lang["nombre"],
            "tipo": "lenguaje",
            "porcentaje": lang.get("porcentaje")
        })

    # Detectar TypeScript
    if "tsconfig.json" in nombres_config:
        tecnologias.append({
            "nombre": "TypeScript",
            "tipo": "lenguaje_compilado",
            "evidencia": "tsconfig.json"
        })

    # Detectar Vite
    vite_config = next((f for f in config_files if f.endswith("vite.config.ts") or f.endswith("vite.config.js")), None)
    if vite_config:
        tecnologias.append({
            "nombre": "Vite",
            "tipo": "herramienta_framework",
            "evidencia": vite_config
        })

    # Detectar frameworks basándose en package.json si está disponible
    for ruta_manifiesto, contenido in dependencies_by_file.items():
        if not ruta_manifiesto.endswith("package.json"):
            continue
        try:
            package_data = json.loads(contenido)
            deps = package_data.get("dependencies", {})
            dev_deps = package_data.get("devDependencies", {})
            all_deps = {**deps, **dev_deps}

            if "react" in all_deps:
                tecnologias.append({
                    "nombre": "React",
                    "tipo": "framework",
                    "evidencia": ruta_manifiesto
                })
            if "firebase" in all_deps:
                tecnologias.append({
                    "nombre": "Firebase",
                    "tipo": "plataforma",
                    "evidencia": ruta_manifiesto
                })
        except Exception:
            pass

    # Detectar Firebase (configuración, sin depender de package.json)
    firebase_config = next((f for f in archivos if f.rsplit("/", 1)[-1] == "firebase.json"), None)
    if firebase_config and not any(t["nombre"] == "Firebase" for t in tecnologias):
        tecnologias.append({
            "nombre": "Firebase",
            "tipo": "plataforma",
            "evidencia": firebase_config
        })

    return {
        "lenguajes": lenguajes,
        "ecosistemas": ecosistemas,
        "tecnologias_detectadas": tecnologias,
    }
