"""
Test real (con conexión a GitLab y ejecución real de Gitleaks) de la
fórmula MS-07: archivos de código analizados sin secretos / archivos de
código analizados.

Ejecuta Gitleaks sobre el workspace de UN COD real (los pocos archivos
declarados en el Issue), NO sobre la raíz completa del repositorio
multiagente (373 MB): ese workspace ya existe porque
integrations/code_repository_service.py::obtener_codigo_codificacion lo
materializa a partir de los archivos declarados/localizados del COD.

NO ejecuta LLM. NO ejecuta agentes.
"""

import shutil

from dotenv import load_dotenv
load_dotenv()

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_service import obtener_issues_codificacion
from integrations.code_repository_service import obtener_codigo_codificacion
from core.code_analysis.secrets_analyzer import ejecutar_gitleaks, obtener_archivos_codigo_workspace
from core.coding_metrics import calcular_ms07

adapter = GitLabAdapter()
issues_cod = obtener_issues_codificacion(adapter.project_id, milestone_title="Codificación")
issue = {i.get("codificacion_id"): i for i in issues_cod}["COD-001"]

codigo_localizado = obtener_codigo_codificacion(adapter, "COD-001", issue.get("archivos_declarados", []))
workspace = codigo_localizado["workspace"]

try:
    evidencia_gitleaks = ejecutar_gitleaks(workspace)
    print("\n=== ejecutar_gitleaks (workspace COD-001) ===")
    print(evidencia_gitleaks)

    assert evidencia_gitleaks["estado"] == "OK"

    archivos_codigo = obtener_archivos_codigo_workspace(workspace)
    print("\nARCHIVOS DE CÓDIGO EN EL WORKSPACE:", archivos_codigo)

    ms07 = calcular_ms07(evidencia_gitleaks, archivos_codigo)
    print("\n=== MS-07 ===")
    print("denominador (archivos de código analizados):", ms07["denominador"])
    print("numerador (archivos de código sin secretos):", ms07["numerador"])
    print("archivos con secretos:", ms07["archivos_con_secretos"])
    print("secretos detectados:", ms07["secretos_detectados"])
    print("porcentaje:", ms07["porcentaje"])

    assert ms07["estado_calculo"] == "calculada"
    assert 0 <= ms07["valor"] <= 1

    print("\nOK: Gitleaks = OK, MS-07 calculado con archivos de código reales.")
finally:
    shutil.rmtree(workspace, ignore_errors=True)
