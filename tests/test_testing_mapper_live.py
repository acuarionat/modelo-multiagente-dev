"""
Integración sin LLM: recupera los Issues PRU-xxx reales de GitLab, los
mapea (integrations/testing_issue_mapper.py) y valida su entrada
(core/testing_validation.py) contra la Matriz de Trazabilidad — Etapa
Codificación (TRZ-003) real. No invoca ningún agente ni proveedor LLM.
"""
import json
import os

from integrations.gitlab_adapter import GitLabAdapter
from integrations.testing_issue_mapper import mapear_issue_pruebas
from integrations.issue_service import obtener_issue_matriz_trazabilidad_codificacion
from core.testing_validation import validar_entrada_pruebas

PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

adapter = GitLabAdapter(project_id=PROJECT_ID)
issues = adapter.listar_issues_pendientes(milestone_title="Pruebas")

print(f"\nIssues de Pruebas encontrados: {len(issues)}")

mapeados_por_prueba_id = {}

for issue in issues:
    print("=" * 80)
    print("IID:", issue.iid)
    print("TITLE:", issue.title)
    print("DESCRIPTION RAW:")
    print(repr(issue.description))

    mapeado = mapear_issue_pruebas(issue)
    print("MAPEADO:")
    print(json.dumps(mapeado, ensure_ascii=False, indent=2))

    prueba_id = mapeado["prueba_id"] or f"issue-{mapeado['issue_iid']}"
    mapeados_por_prueba_id[prueba_id] = mapeado

    print(f"\n{prueba_id}")
    print(f"descripcion: {'OK' if mapeado['descripcion'] else 'VACIA'}")
    print(f"codificaciones_relacionadas: {mapeado['codificaciones_relacionadas']}")
    print(f"pruebas_funcionales: {len(mapeado['pruebas_funcionales'])}")
    print(f"fallos: {len(mapeado['fallos'])}")
    print(f"controles_seguridad: {len(mapeado['controles_seguridad'])}")
    print(f"pruebas_seguridad: {len(mapeado['pruebas_seguridad'])}")

_, matriz_codificacion = obtener_issue_matriz_trazabilidad_codificacion(PROJECT_ID)
matriz_codificacion = matriz_codificacion or []
print(f"\nFilas de TRZ-003 (Matriz de Trazabilidad — Etapa Codificación): {len(matriz_codificacion)}")

print("\n" + "=" * 80)
print("VALIDACIÓN (core/testing_validation.py)")
print("=" * 80)

for prueba_id, mapeado in sorted(mapeados_por_prueba_id.items()):
    validacion = validar_entrada_pruebas(mapeado, matriz_codificacion)
    print(f"{prueba_id} {validacion['estado']}", validacion if not validacion["entrada_valida"] else "")

assert "PRU-001" in mapeados_por_prueba_id, "No se encontró PRU-001 en GitLab."
assert "PRU-002" in mapeados_por_prueba_id, "No se encontró PRU-002 en GitLab."

pru_001 = mapeados_por_prueba_id["PRU-001"]
pru_002 = mapeados_por_prueba_id["PRU-002"]

assert pru_001["descripcion"], "PRU-001: descripcion vacía."
assert pru_001["codificaciones_relacionadas"] == ["COD-001"], pru_001["codificaciones_relacionadas"]

assert pru_002["descripcion"], "PRU-002: descripcion vacía."
assert pru_002["codificaciones_relacionadas"] == ["COD-002"], pru_002["codificaciones_relacionadas"]

validacion_001 = validar_entrada_pruebas(pru_001, matriz_codificacion)
validacion_002 = validar_entrada_pruebas(pru_002, matriz_codificacion)

assert validacion_001["estado"] == "VALIDO", validacion_001
assert validacion_002["estado"] == "VALIDO", validacion_002

print("\nTodas las verificaciones de testing_mapper_live pasaron.")
