"""
Servicio de acceso al código fuente real del repositorio GitLab del
proyecto evaluado, exclusivo de la etapa de Codificación. Descarga
únicamente los archivos declarados en cada Issue COD-xxx
(integrations/coding_issue_mapper.py) y el manifiesto de dependencias del
repositorio: nunca el repositorio completo. No ejecuta analizadores ni
calcula métricas: eso corresponde a core/code_analysis/.
"""

import base64
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

MANIFIESTOS_DEPENDENCIAS = (
    "requirements.txt", "pyproject.toml", "Pipfile", "Pipfile.lock",
    "poetry.lock", "setup.py",
)

EXTENSIONES_POR_LENGUAJE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
}


def identificar_lenguaje(rutas: list) -> str:
    """Determina el lenguaje dominante según la extensión de los archivos declarados."""
    conteo = {}
    for ruta in rutas:
        _, ext = os.path.splitext(str(ruta or ""))
        lenguaje = EXTENSIONES_POR_LENGUAJE.get(ext.casefold())
        if lenguaje:
            conteo[lenguaje] = conteo.get(lenguaje, 0) + 1
    if not conteo:
        return "desconocido"
    return max(conteo, key=conteo.get)


def _descargar_archivo(project, ruta: str, ref: str) -> dict:
    """Descarga un único archivo del repositorio GitLab. Diferencia ausencia de error técnico."""
    try:
        archivo = project.files.get(file_path=ruta, ref=ref)
    except Exception as exc:
        status_code = getattr(exc, "response_code", None)
        if status_code == 404:
            return {"ruta": ruta, "estado": "NO_ENCONTRADO", "contenido": None, "error": None}
        return {"ruta": ruta, "estado": "ERROR", "contenido": None, "error": str(exc)}
    try:
        contenido = base64.b64decode(archivo.content).decode("utf-8", errors="replace")
    except Exception as exc:
        return {"ruta": ruta, "estado": "ERROR", "contenido": None, "error": str(exc)}
    return {"ruta": ruta, "estado": "OK", "contenido": contenido, "error": None}


def localizar_archivos_cod(project, archivos_declarados: list, ref: str = None) -> list:
    """
    Descarga solo los archivos declarados en el Issue COD-xxx (sección
    "Ubicación de la implementación"). No recorre ni descarga el resto del
    repositorio.
    """
    ref = ref or getattr(project, "default_branch", None) or "main"
    resultados = []
    for declarado in archivos_declarados:
        ruta = declarado.get("ruta") if isinstance(declarado, dict) else declarado
        if not ruta:
            continue
        resultados.append(_descargar_archivo(project, ruta, ref))
    return resultados


def localizar_manifiesto_dependencias(project, ref: str = None) -> dict:
    """Busca en la raíz del repositorio el primer manifiesto de dependencias reconocido."""
    ref = ref or getattr(project, "default_branch", None) or "main"
    try:
        arbol = project.repository_tree(ref=ref, all=True)
    except Exception as exc:
        return {
            "encontrado": False, "ruta": None, "contenido": None,
            "estado": "ERROR", "error": str(exc),
        }

    nombres_raiz = {
        item["name"]: item["path"] for item in arbol if item.get("type") == "blob"
    }
    for nombre in MANIFIESTOS_DEPENDENCIAS:
        if nombre in nombres_raiz:
            archivo = _descargar_archivo(project, nombres_raiz[nombre], ref)
            if archivo["estado"] != "OK":
                return {
                    "encontrado": True, "ruta": nombres_raiz[nombre], "contenido": None,
                    "estado": archivo["estado"], "error": archivo.get("error"),
                }
            return {
                "encontrado": True, "ruta": nombres_raiz[nombre],
                "contenido": archivo["contenido"], "estado": "OK", "error": None,
            }
    return {"encontrado": False, "ruta": None, "contenido": None, "estado": "NO_APLICA", "error": None}


def preparar_workspace_codificacion(codificacion_id: str, archivos: list, manifiesto: dict) -> str:
    """
    Materializa en un directorio temporal los archivos COD ya descargados
    (y el manifiesto de dependencias, si existe), para que las herramientas
    de análisis (Radon, Semgrep, pip-audit, Gitleaks) trabajen sobre rutas
    reales de filesystem. No conserva el workspace entre ejecuciones.
    """
    workspace = tempfile.mkdtemp(prefix=f"coding_{codificacion_id}_")
    for archivo in archivos:
        if archivo.get("estado") != "OK":
            continue
        destino = os.path.join(workspace, archivo["ruta"].replace("/", os.sep))
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as handle:
            handle.write(archivo["contenido"])

    if manifiesto.get("estado") == "OK" and manifiesto.get("contenido") is not None:
        destino = os.path.join(workspace, os.path.basename(manifiesto["ruta"]))
        with open(destino, "w", encoding="utf-8") as handle:
            handle.write(manifiesto["contenido"])

    return workspace


def obtener_codigo_codificacion(adapter, codificacion_id: str, archivos_declarados: list, ref: str = None) -> dict:
    """
    Orquesta la adquisición completa de evidencia técnica para un COD-xxx:
    localiza sus archivos declarados, identifica el lenguaje dominante,
    localiza el manifiesto de dependencias y prepara el workspace temporal
    que consumirán los analizadores. No ejecuta ningún analizador.
    """
    project = adapter.project
    rutas_declaradas = [
        item.get("ruta") if isinstance(item, dict) else item for item in archivos_declarados
    ]
    archivos = localizar_archivos_cod(project, archivos_declarados, ref)
    manifiesto = localizar_manifiesto_dependencias(project, ref)
    rutas_ok = [archivo["ruta"] for archivo in archivos if archivo.get("estado") == "OK"]
    lenguaje = identificar_lenguaje(rutas_ok or rutas_declaradas)
    workspace = preparar_workspace_codificacion(codificacion_id, archivos, manifiesto)

    return {
        "codificacion_id": codificacion_id,
        "lenguaje": lenguaje,
        "archivos": archivos,
        "manifiesto_dependencias": manifiesto,
        "workspace": workspace,
    }
