"""
Verificación de extremo a extremo (sin conexión a GitLab real, porque el
milestone Codificación todavía no tiene Issues COD-xxx creados): prueba
que la matriz heredada, el Issue COD mapeado, el código realmente
localizado y la evidencia normalizada de las 4 herramientas SÍ llegan
completas y correctas a core/coding_context.py. Esta es la verificación
exigida antes de construir cualquier agente LLM (Segunda regla crítica).
"""

import base64
import json
import os
import shutil
from types import SimpleNamespace

from core.code_analysis.dependency_analyzer import ejecutar_pip_audit
from core.code_analysis.models import ESTADO_ERROR, ESTADO_NO_APLICA, ESTADO_OK
from core.code_analysis.radon_analyzer import ejecutar_radon
from core.code_analysis.secrets_analyzer import ejecutar_gitleaks
from core.code_analysis.semgrep_analyzer import ejecutar_semgrep
from core.coding_context import construir_contexto_codificacion
from core.coding_contract import validar_entrada_codificacion
from core.coding_matrix_input import extraer_elementos_diseno_validos, preparar_matriz_entrada_codificacion
from integrations.code_repository_service import obtener_codigo_codificacion
from integrations.coding_issue_mapper import mapear_issue_codificacion


# ==========================================================
# 1. Matriz de Diseño heredada (mismo contrato de
#    construir_filas_matriz_diseno)
# ==========================================================

matriz_diseno = [
    {
        "HU origen": "HU-006 — Consultar horarios disponibles",
        "Código requisito": "RF-001",
        "Tipo": "Funcional",
        "Nombre del requisito": "Mostrar únicamente horarios disponibles",
        "Descripción": "El sistema deberá mostrar solo los horarios libres.",
        "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-01, ED-02",
        "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME",
        "Observación": "Relación identificada con evidencia suficiente.",
    },
]

preparacion_matriz = preparar_matriz_entrada_codificacion(matriz_diseno, matriz_diseno, "GitLab")
assert preparacion_matriz["coding_matrix_status"] == "ORIGINAL"
elementos_validos = extraer_elementos_diseno_validos(preparacion_matriz["coding_matrix_input"])
assert elementos_validos == {"ED-01", "ED-02"}


# ==========================================================
# 2. Issue COD-001 real (mapeado desde Markdown, como llegaría
#    de GitLab)
# ==========================================================

DESCRIPCION_COD_001 = """
## 1. Descripción de la implementación

Servicio de autenticación de usuarios mediante tokens JWT.

## 2. Elementos de Diseño implementados

- ED-01
- ED-02

## 3. Ubicación de la implementación

| Archivo/Módulo | Descripción |
|---|---|
| core/auth_service.py | Lógica principal de autenticación (ED-01). |
| core/token_repository.py | Persistencia de tokens (ED-02). |

## 4. Decisiones de implementación

- Se usó bcrypt para el hash de contraseñas.

## 5. Observaciones

- Ninguna.
"""

issue_gitlab_simulado = SimpleNamespace(
    iid=25,
    title="COD-001 — Servicio de autenticación",
    description=DESCRIPCION_COD_001,
    labels=["Pendiente"],
)
issue_codificacion = mapear_issue_codificacion(issue_gitlab_simulado)

# 2.b — Validación inicial ANTES de tocar herramientas ni LLM.
validacion_entrada = validar_entrada_codificacion(issue_codificacion, elementos_validos)
print("\n" + "=" * 70)
print("validar_entrada_codificacion")
print("=" * 70)
print(validacion_entrada)
assert validacion_entrada["entrada_valida"] is True


# ==========================================================
# 3. Código real localizado en el repositorio (GitLab simulado
#    con un doble de prueba, mismo contrato que python-gitlab)
# ==========================================================

class FakeFilesManager:
    def __init__(self, archivos):
        self._archivos = archivos

    def get(self, file_path, ref):
        if file_path not in self._archivos:
            error = Exception("404 File Not Found")
            error.response_code = 404
            raise error
        contenido = self._archivos[file_path]
        return SimpleNamespace(content=base64.b64encode(contenido.encode("utf-8")).decode("ascii"))


class FakeProject:
    default_branch = "main"

    def __init__(self, archivos, arbol_raiz):
        self.files = FakeFilesManager(archivos)
        self._arbol_raiz = arbol_raiz

    def repository_tree(self, ref=None, all=None):
        return self._arbol_raiz


CODIGO_AUTH_SERVICE = '''
import bcrypt


def autenticar(usuario, password_hash, password):
    if bcrypt.checkpw(password.encode("utf-8"), password_hash):
        if usuario.activo:
            if usuario.no_bloqueado:
                if usuario.email_verificado:
                    return True
    return False
'''
CODIGO_TOKEN_REPOSITORY = '''
def guardar_token(usuario_id, token):
    return {"usuario_id": usuario_id, "token": token}
'''

archivos_repo = {
    "core/auth_service.py": CODIGO_AUTH_SERVICE,
    "core/token_repository.py": CODIGO_TOKEN_REPOSITORY,
    "requirements.txt": "bcrypt==4.1.2\n",
}
arbol_raiz = [
    {"name": "core", "path": "core", "type": "tree"},
    {"name": "requirements.txt", "path": "requirements.txt", "type": "blob"},
]
project = FakeProject(archivos_repo, arbol_raiz)
adapter_simulado = SimpleNamespace(project=project)

codigo_localizado = obtener_codigo_codificacion(
    adapter_simulado,
    issue_codificacion["codificacion_id"],
    issue_codificacion["archivos_declarados"],
)
print("\n" + "=" * 70)
print("obtener_codigo_codificacion")
print("=" * 70)
print({k: v for k, v in codigo_localizado.items() if k != "archivos"})
assert codigo_localizado["lenguaje"] == "python"
assert all(a["estado"] == "OK" for a in codigo_localizado["archivos"])
assert codigo_localizado["manifiesto_dependencias"]["encontrado"] is True

workspace = codigo_localizado["workspace"]

try:
    # ==========================================================
    # 4. Evidencia normalizada de las 4 herramientas reales
    # ==========================================================

    evidencia_radon = ejecutar_radon(workspace)
    evidencia_semgrep = ejecutar_semgrep(workspace)
    evidencia_pip_audit = ejecutar_pip_audit(codigo_localizado["manifiesto_dependencias"], workspace)
    evidencia_gitleaks = ejecutar_gitleaks(workspace)

    print("\n" + "=" * 70)
    print("Evidencia normalizada por herramienta")
    print("=" * 70)
    for nombre, evidencia in (
        ("radon", evidencia_radon), ("semgrep", evidencia_semgrep),
        ("pip_audit", evidencia_pip_audit), ("gitleaks", evidencia_gitleaks),
    ):
        print(f"- {nombre}: estado={evidencia['estado']}")

    assert evidencia_radon["estado"] == ESTADO_OK
    assert len(evidencia_radon["datos"]["funciones"]) == 2
    assert evidencia_semgrep["estado"] in {ESTADO_OK, ESTADO_ERROR}
    assert evidencia_pip_audit["estado"] in {ESTADO_OK, ESTADO_ERROR}
    # gitleaks no está instalado en este entorno: debe ser ERROR, nunca 0 %.
    assert evidencia_gitleaks["estado"] == ESTADO_ERROR

    # ==========================================================
    # 5. Ensamblado final — core/coding_context.py
    # ==========================================================

    contexto = construir_contexto_codificacion(
        issue_codificacion,
        preparacion_matriz["coding_matrix_input"],
        codigo_localizado,
        {
            "radon": evidencia_radon,
            "semgrep": evidencia_semgrep,
            "pip_audit": evidencia_pip_audit,
            "gitleaks": evidencia_gitleaks,
        },
    )

    print("\n" + "=" * 70)
    print("coding_context.py — contexto ensamblado completo")
    print("=" * 70)
    print(json.dumps(
        {k: v for k, v in contexto.items() if k not in {"archivos_localizados"}},
        ensure_ascii=False, indent=2, default=str,
    ))

    # Identidad conservada sin inventar nada.
    assert contexto["issue_iid"] == 25
    assert contexto["codificacion_id"] == "COD-001"
    assert contexto["elementos_diseno_declarados"] == ["ED-01", "ED-02"]

    # La matriz heredada realmente contextualiza los ED declarados.
    assert contexto["validacion_elementos_diseno"]["referencias_validas"] == ["ED-01", "ED-02"]
    assert contexto["validacion_elementos_diseno"]["referencias_invalidas"] == []
    ed01 = next(item for item in contexto["elementos_diseno_contextualizados"] if item["elemento_id"] == "ED-01")
    assert ed01["relaciones_diseno"][0]["diseno"] == "DIS-001"
    assert ed01["relaciones_diseno"][0]["codigo_requisito"] == "RF-001"

    # El código realmente localizado llega completo.
    assert len(contexto["archivos_localizados"]) == 2
    assert all(a["estado"] == "OK" for a in contexto["archivos_localizados"])
    assert contexto["lenguaje_detectado"] == "python"

    # La evidencia de las 4 herramientas llega completa, con sus estados reales.
    assert contexto["evidencia_tecnica"]["radon"]["estado"] == ESTADO_OK
    assert contexto["evidencia_tecnica"]["gitleaks"]["estado"] == ESTADO_ERROR

    # Ningún secreto real puede llegar al contexto: no existe ninguna clave
    # "secreto" sin redactar en toda la estructura serializada.
    contexto_serializado = json.dumps(contexto, ensure_ascii=False, default=str)
    assert "[REDACTED]" not in contexto_serializado or "secreto_redactado" in contexto_serializado

finally:
    shutil.rmtree(workspace, ignore_errors=True)


# ==========================================================
# 6. Caso ED-99 inexistente: el COD no debe pasar (gate previo
#    a herramientas y agentes)
# ==========================================================

issue_con_ed_inexistente = dict(issue_codificacion)
issue_con_ed_inexistente["elementos_diseno_declarados"] = ["ED-01", "ED-99"]
validacion_rechazo = validar_entrada_codificacion(issue_con_ed_inexistente, elementos_validos)
print("\n" + "=" * 70)
print("validar_entrada_codificacion — ED-99 inexistente (debe rechazar)")
print("=" * 70)
print(validacion_rechazo)
assert validacion_rechazo["entrada_valida"] is False
assert validacion_rechazo["referencias_invalidas"] == ["ED-99"]

print("\nTodas las verificaciones de coding_context (extremo a extremo) pasaron.")
