"""
Test anti-invención (sin LLM): confirma que preparar_archivos_para_llm()
y construir_contexto_codificacion() distinguen "localizado" de
"incluido en el prompt", y que el contenido crudo de coding_codigo_localizado
no vuelve a colarse en el contexto que recibe el Central.

Tres casos reales del repositorio:
A. src/App.tsx           -> código textual pequeño: analizable.
B. package-lock.json     -> lockfile: existe, pero NO analizable directamente.
C. src/assets/logo.jpg   -> binario: existe, pero NO analizable directamente.
"""

import json

from core.coding_context import construir_contexto_codificacion
from core.coding_context_files import preparar_archivos_para_llm

ARCHIVOS_LOCALIZADOS = [
    {"ruta": "src/App.tsx", "estado": "OK", "contenido": "export default function App() {}\n", "error": None},
    {"ruta": "package-lock.json", "estado": "OK", "contenido": "{\"lockfileVersion\": 3}", "error": None},
    {"ruta": "src/assets/logo.jpg", "estado": "OK", "contenido": "��� binario ilegible ��", "error": None},
]


def test_preparar_archivos_para_llm_distingue_localizado_de_incluido():
    resultado = preparar_archivos_para_llm(ARCHIVOS_LOCALIZADOS)
    por_ruta = {archivo["ruta"]: archivo for archivo in resultado["archivos_para_llm"]}

    # A. src/App.tsx: localizado y con contenido disponible -> analizable.
    app_tsx = por_ruta["src/App.tsx"]
    assert app_tsx["estado"] == "OK"
    assert app_tsx["incluido_en_prompt"] is True
    assert app_tsx["contenido"] == "export default function App() {}\n"

    # B. package-lock.json: localizado, pero NO analizable directamente.
    lockfile = por_ruta["package-lock.json"]
    assert lockfile["estado"] == "OK"
    assert lockfile["incluido_en_prompt"] is False
    assert "motivo" in lockfile
    assert "contenido" not in lockfile

    # C. src/assets/logo.jpg: localizado, pero NO analizable directamente.
    binario = por_ruta["src/assets/logo.jpg"]
    assert binario["estado"] == "OK"
    assert binario["incluido_en_prompt"] is False
    assert "motivo" in binario
    assert "contenido" not in binario

    # Los excluidos quedan también reflejados en archivos_omitidos_del_contexto.
    rutas_omitidas = {item["ruta"] for item in resultado["archivos_omitidos_del_contexto"]}
    assert rutas_omitidas == {"package-lock.json", "src/assets/logo.jpg"}


def test_construir_contexto_codificacion_no_reinserta_codigo_localizado_crudo():
    issue_codificacion = {
        "id": "1",
        "issue_iid": 1,
        "codificacion_id": "COD-001",
        "titulo": "COD-001",
        "descripcion": "Descripción.",
        "elementos_diseno_declarados": [],
        "archivos_declarados": [],
        "decisiones": [],
        "observaciones": [],
        "labels": [],
        "validacion_entrada": {"estado": "", "campos_faltantes": [], "advertencias": []},
    }
    codigo_localizado = {
        "codificacion_id": "COD-001",
        "lenguaje": "typescript",
        "archivos": ARCHIVOS_LOCALIZADOS,
        "manifiesto_dependencias": {"encontrado": False, "ruta": None, "contenido": None, "estado": "NO_APLICA", "error": None},
        "workspace": "/tmp/no-existe",
    }
    evidencia_herramientas = {"radon": {}, "semgrep": {}, "pip_audit": {}, "gitleaks": {}}

    contexto = construir_contexto_codificacion(
        issue_codificacion, [], codigo_localizado, evidencia_herramientas,
    )

    # El objeto crudo completo (con "workspace", tal como llega a las
    # herramientas) no debe reaparecer en ningún valor del contexto.
    assert "workspace" not in contexto
    for valor in contexto.values():
        assert valor is not codigo_localizado
        assert valor is not codigo_localizado["archivos"]

    # El contenido crudo de los archivos excluidos no vuelve a colarse en
    # el contexto serializado (ni el lockfile ni el binario).
    contexto_serializado = json.dumps(contexto, ensure_ascii=False, default=str)
    assert "lockfileVersion" not in contexto_serializado
    assert "binario ilegible" not in contexto_serializado

    # El contenido textual analizable sí sigue disponible.
    assert "export default function App" in contexto_serializado
