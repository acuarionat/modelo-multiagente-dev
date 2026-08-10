import json
import os

from core.design_contract import validar_entrada_diseno
from integrations.issue_service import obtener_issues_diseno


# ---------------------------------------------------------
# Conexión real a GitLab — Milestone Diseño
# ---------------------------------------------------------

PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")


# ---------------------------------------------------------
# Mostrar lo que realmente entregó design_issue_mapper
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("ISSUES RECIBIDOS DESDE GITLAB — DISEÑO")
print("=" * 70)

for issue in issues_diseno:
    print(f"\n{issue.get('diseno_id')}")
    print(json.dumps(issue, ensure_ascii=False, indent=2))


# ---------------------------------------------------------
# Validación de entrada (core.design_contract)
# ---------------------------------------------------------

validaciones = [validar_entrada_diseno(issue) for issue in issues_diseno]

print("\n" + "=" * 70)
print("VALIDACIÓN")
print("=" * 70)

print("Issues encontrados:", len(issues_diseno))
print("DIS válidos:", sum(1 for v in validaciones if v["estado"] == "entrada_valida"))
print("Con advertencias:", sum(1 for v in validaciones if v["estado"] == "entrada_con_advertencias"))
print("Información insuficiente:", sum(1 for v in validaciones if v["estado"] == "informacion_insuficiente"))
