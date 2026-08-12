"""
Filtra los archivos ya localizados de un COD-xxx (integrations/
code_repository_service.py::obtener_codigo_codificacion) para decidir
qué contenido se envía al contexto del LLM (Coding_Central).

El objeto completo (con el contenido íntegro de cada archivo, incluidos
binarios y lockfiles) sigue disponible en el estado del grafo
(state["coding_codigo_localizado"]) para las herramientas (Radon,
Semgrep, pip-audit, Gitleaks): esta clasificación solo decide qué entra
al prompt, no altera lo que reciben las herramientas.
"""

import json
import os

EXTENSIONES_CODIGO = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".php", ".go", ".rb", ".vue", ".svelte",
}

MANIFIESTOS_RESUMIBLES = {
    "package.json", "requirements.txt", "pyproject.toml", "pom.xml", "composer.json",
}

CONFIGURACIONES_RESUMIBLES_PREFIJOS = (
    "tsconfig.json", "vite.config.", "eslint.config.",
)

LOCKFILES_EXCLUIDOS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
}

EXTENSIONES_BINARIAS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".ico",
    ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".avi",
    ".pdf", ".zip", ".tar", ".gz", ".rar",
}

TAMANO_MAXIMO_CONTENIDO_COMPLETO = 30 * 1024  # 30 KB


def _nombre_archivo(ruta: str) -> str:
    return os.path.basename(ruta or "")


def _clasificar_tipo(ruta: str) -> str:
    nombre = _nombre_archivo(ruta)
    _, extension = os.path.splitext(nombre)
    extension = extension.casefold()

    if nombre in LOCKFILES_EXCLUIDOS:
        return "lockfile"
    if extension in EXTENSIONES_BINARIAS:
        return "binario"
    if nombre in MANIFIESTOS_RESUMIBLES:
        return "manifest"
    if nombre.startswith(CONFIGURACIONES_RESUMIBLES_PREFIJOS):
        return "configuracion_textual"
    if extension in EXTENSIONES_CODIGO:
        return "codigo"
    return "recurso"


def _resumir_package_json(contenido: str) -> dict:
    try:
        data = json.loads(contenido)
    except (TypeError, ValueError):
        return {}
    return {
        "scripts": data.get("scripts", {}),
        "dependencies": sorted((data.get("dependencies") or {}).keys()),
        "devDependencies": sorted((data.get("devDependencies") or {}).keys()),
    }


def _contenido_o_compacto(ruta: str, tipo: str, estado, contenido: str) -> dict:
    base = {"ruta": ruta, "tipo": tipo, "estado": estado, "incluido_en_prompt": True}
    if len(contenido) <= TAMANO_MAXIMO_CONTENIDO_COMPLETO:
        base["contenido"] = contenido
    else:
        base["lineas"] = contenido.count("\n") + 1
        base["contenido_truncado"] = True
    return base


def preparar_archivos_para_llm(archivos_localizados: list) -> dict:
    """
    Clasifica cada archivo localizado y decide qué se envía al LLM:
    - codigo / configuracion_textual / manifest textual: contenido completo
      si es pequeño (<=30 KB), representación compacta con contenido_truncado
      si es grande.
    - package.json (manifest): resumen (scripts, dependencias, dev-dependencias).
    - lockfile / binario: nunca contenido, solo metadata.

    Retorna:
        {
            "archivos_para_llm": [...],
            "archivos_omitidos_del_contexto": [...],
        }
    """
    archivos_para_llm = []
    archivos_omitidos = []

    for archivo in archivos_localizados:
        ruta = archivo.get("ruta")
        estado = archivo.get("estado")
        contenido = archivo.get("contenido")
        tipo = _clasificar_tipo(ruta)

        if estado != "OK" or contenido is None:
            archivos_para_llm.append({
                "ruta": ruta,
                "tipo": tipo,
                "estado": estado,
                "incluido_en_prompt": False,
            })
            continue

        if tipo == "lockfile":
            archivos_para_llm.append({
                "ruta": ruta,
                "tipo": tipo,
                "estado": estado,
                "incluido_en_prompt": False,
                "motivo": "Analizado por herramienta de dependencias",
            })
            archivos_omitidos.append({
                "ruta": ruta,
                "tipo": tipo,
                "razon": "Procesado por herramienta de dependencias",
            })
            continue

        if tipo == "binario":
            archivos_para_llm.append({
                "ruta": ruta,
                "tipo": tipo,
                "estado": estado,
                "incluido_en_prompt": False,
                "motivo": "Archivo no textual",
            })
            archivos_omitidos.append({
                "ruta": ruta,
                "tipo": tipo,
                "razon": "Contenido no textual",
            })
            continue

        if tipo == "manifest" and _nombre_archivo(ruta) == "package.json":
            archivos_para_llm.append({
                "ruta": ruta,
                "tipo": tipo,
                "estado": estado,
                "incluido_en_prompt": True,
                "contenido_resumido": _resumir_package_json(contenido),
            })
            continue

        archivos_para_llm.append(_contenido_o_compacto(ruta, tipo, estado, contenido))

    return {
        "archivos_para_llm": archivos_para_llm,
        "archivos_omitidos_del_contexto": archivos_omitidos,
    }
