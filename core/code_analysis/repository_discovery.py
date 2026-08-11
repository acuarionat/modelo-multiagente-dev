"""
Descubrimiento automático del repositorio sin ejecutar herramientas.

Combina GitLab API con clasificación local de archivos para construir
un perfil técnico completo del repositorio.
"""

from typing import Dict, Any
from integrations.gitlab_adapter import GitLabAdapter

EXTENSIONES_CODIGO = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".cs": "C#", ".php": "PHP", ".go": "Go", ".rb": "Ruby",
}

MANIFESTS = {
    "requirements.txt", "pyproject.toml", "Pipfile",
    "package.json", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json",
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock",
}

CONFIG_FILES = {
    "tsconfig.json",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "babel.config.js",
    ".eslintrc.json",
    ".eslintrc.js",
    ".prettierrc.json",
    "jest.config.js",
    "pytest.ini",
    ".pylintrc",
    "mypy.ini",
    "tox.ini",
    "setup.cfg",
    "pyproject.toml",
    ".gitignore",
    ".env.example",
    "firebase.json",
    ".nvmrc",
    "Dockerfile",
    "docker-compose.yml",
}


def descubrir_repositorio(adapter: GitLabAdapter, *, ref: str | None = None) -> Dict[str, Any]:
    """Descubre la estructura, tecnologías y metadatos del repositorio.

    Args:
        adapter: GitLabAdapter conectado al proyecto
        ref: rama o commit a analizar (por defecto, rama principal)

    Retorna:
        {
            "estado": "OK" | "ERROR",
            "rama": str,
            "lenguajes": [{"nombre": "TypeScript", "porcentaje": 83.4}, ...],
            "directorios": ["src", "src/components", ...],
            "archivos": ["src/App.tsx", ...],
            "archivos_codigo": ["src/App.tsx", ...],
            "manifiestos": ["package.json"],
            "lockfiles": ["package-lock.json"],
            "configuracion_tecnica": ["tsconfig.json", "vite.config.ts", ...],
            "total_archivos": 86,
            "total_directorios": 14,
        }
    """
    try:
        rama = ref or adapter.obtener_rama_predeterminada()
        arbol = adapter.obtener_arbol_repositorio(ref=rama)

        lenguajes_gitlab = adapter.obtener_lenguajes_repositorio()
        lenguajes_lista = [
            {"nombre": nombre, "porcentaje": float(porcentaje)}
            for nombre, porcentaje in sorted(lenguajes_gitlab.items(), key=lambda x: x[1], reverse=True)
        ]

        directorios = set()
        archivos = []
        archivos_codigo = []
        manifiestos = []
        lockfiles = []
        configuracion_tecnica = []

        for item in arbol:
            if item["tipo"] == "directorio":
                directorios.add(item["ruta"])
            else:
                ruta = item["ruta"]
                archivos.append(ruta)

                nombre_archivo = item["nombre"]
                if nombre_archivo in MANIFESTS:
                    manifiestos.append(ruta)

                if nombre_archivo in LOCKFILES:
                    lockfiles.append(ruta)

                if nombre_archivo in CONFIG_FILES:
                    configuracion_tecnica.append(ruta)

                for ext, lenguaje in EXTENSIONES_CODIGO.items():
                    if nombre_archivo.endswith(ext):
                        archivos_codigo.append(ruta)
                        break

        return {
            "estado": "OK",
            "rama": rama,
            "lenguajes": lenguajes_lista,
            "directorios": sorted(list(directorios)),
            "archivos": sorted(archivos),
            "archivos_codigo": sorted(archivos_codigo),
            "manifiestos": sorted(manifiestos),
            "lockfiles": sorted(lockfiles),
            "configuracion_tecnica": sorted(configuracion_tecnica),
            "total_archivos": len(archivos),
            "total_directorios": len(directorios),
        }
    except Exception as e:
        return {
            "estado": "ERROR",
            "rama": ref or "desconocida",
            "error": str(e),
            "lenguajes": [],
            "directorios": [],
            "archivos": [],
            "archivos_codigo": [],
            "manifiestos": [],
            "lockfiles": [],
            "configuracion_tecnica": [],
            "total_archivos": 0,
            "total_directorios": 0,
        }
