import base64
import os
import shutil
from types import SimpleNamespace

from integrations.code_repository_service import (
    identificar_lenguaje,
    localizar_archivos_cod,
    localizar_manifiesto_dependencias,
    obtener_codigo_codificacion,
    preparar_workspace_codificacion,
)


class FakeFilesManager:
    def __init__(self, archivos: dict):
        self._archivos = archivos  # ruta -> contenido de texto

    def get(self, file_path, ref):
        if file_path not in self._archivos:
            error = Exception("404 File Not Found")
            error.response_code = 404
            raise error
        contenido = self._archivos[file_path]
        return SimpleNamespace(
            content=base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
        )


class FakeProject:
    default_branch = "main"

    def __init__(self, archivos: dict, arbol_raiz: list):
        self.files = FakeFilesManager(archivos)
        self._arbol_raiz = arbol_raiz

    def repository_tree(self, ref=None, all=None):
        return self._arbol_raiz


ARCHIVOS_REPO = {
    "core/auth_service.py": "def autenticar():\n    return True\n",
    "core/token_repository.py": "def guardar_token(token):\n    pass\n",
    "requirements.txt": "requests==2.31.0\n",
}
ARBOL_RAIZ = [
    {"name": "core", "path": "core", "type": "tree"},
    {"name": "requirements.txt", "path": "requirements.txt", "type": "blob"},
    {"name": "README.md", "path": "README.md", "type": "blob"},
]

project = FakeProject(ARCHIVOS_REPO, ARBOL_RAIZ)


# ==========================================================
# identificar_lenguaje
# ==========================================================

assert identificar_lenguaje(["core/a.py", "core/b.py", "core/c.js"]) == "python"
assert identificar_lenguaje([]) == "desconocido"
assert identificar_lenguaje(["README.md"]) == "desconocido"
print("identificar_lenguaje: OK")


# ==========================================================
# localizar_archivos_cod
# ==========================================================

archivos_declarados = [
    {"ruta": "core/auth_service.py", "descripcion": "..."},
    {"ruta": "core/token_repository.py", "descripcion": "..."},
    {"ruta": "core/no_existe.py", "descripcion": "..."},
]
resultado_archivos = localizar_archivos_cod(project, archivos_declarados)
print("\n" + "=" * 70)
print("localizar_archivos_cod")
print("=" * 70)
print(resultado_archivos)

por_ruta = {item["ruta"]: item for item in resultado_archivos}
assert por_ruta["core/auth_service.py"]["estado"] == "OK"
assert "def autenticar" in por_ruta["core/auth_service.py"]["contenido"]
assert por_ruta["core/token_repository.py"]["estado"] == "OK"
assert por_ruta["core/no_existe.py"]["estado"] == "NO_ENCONTRADO"


# ==========================================================
# localizar_manifiesto_dependencias
# ==========================================================

manifiesto = localizar_manifiesto_dependencias(project)
print("\n" + "=" * 70)
print("localizar_manifiesto_dependencias")
print("=" * 70)
print(manifiesto)
assert manifiesto["encontrado"] is True
assert manifiesto["ruta"] == "requirements.txt"
assert manifiesto["estado"] == "OK"
assert "requests==2.31.0" in manifiesto["contenido"]

proyecto_sin_manifiesto = FakeProject(
    {"otro.py": "pass\n"},
    [{"name": "otro.py", "path": "otro.py", "type": "blob"}],
)
manifiesto_ausente = localizar_manifiesto_dependencias(proyecto_sin_manifiesto)
assert manifiesto_ausente["encontrado"] is False
assert manifiesto_ausente["estado"] == "NO_APLICA"


# ==========================================================
# preparar_workspace_codificacion
# ==========================================================

workspace = preparar_workspace_codificacion("COD-001", resultado_archivos, manifiesto)
print("\n" + "=" * 70)
print("preparar_workspace_codificacion — workspace:", workspace)
print("=" * 70)
try:
    assert os.path.isfile(os.path.join(workspace, "core", "auth_service.py"))
    assert os.path.isfile(os.path.join(workspace, "core", "token_repository.py"))
    assert not os.path.exists(os.path.join(workspace, "core", "no_existe.py"))
    assert os.path.isfile(os.path.join(workspace, "requirements.txt"))
    with open(os.path.join(workspace, "core", "auth_service.py"), encoding="utf-8") as handle:
        assert "def autenticar" in handle.read()
finally:
    shutil.rmtree(workspace, ignore_errors=True)


# ==========================================================
# obtener_codigo_codificacion (orquestador completo)
# ==========================================================

adapter = SimpleNamespace(project=project)
resultado_completo = obtener_codigo_codificacion(adapter, "COD-001", archivos_declarados)
print("\n" + "=" * 70)
print("obtener_codigo_codificacion")
print("=" * 70)
print({k: v for k, v in resultado_completo.items() if k != "archivos"})
try:
    assert resultado_completo["codificacion_id"] == "COD-001"
    assert resultado_completo["lenguaje"] == "python"
    assert resultado_completo["manifiesto_dependencias"]["encontrado"] is True
    assert os.path.isdir(resultado_completo["workspace"])
finally:
    shutil.rmtree(resultado_completo["workspace"], ignore_errors=True)

print("\nTodas las verificaciones de code_repository_service pasaron.")
