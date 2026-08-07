import json
import os

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_mapper import mapear_issue_a_json
from agents.central_agent import procesar_central_en_sublotes


# ---------------------------------------------------------
# Configuración controlada
# ---------------------------------------------------------

os.environ["CENTRAL_BATCH_SIZE"] = "1"
os.environ["CENTRAL_MAX_TECHNICAL_RETRIES"] = "0"


# ---------------------------------------------------------
# Conexión real a GitLab
# ---------------------------------------------------------

adapter = GitLabAdapter()


# ---------------------------------------------------------
# Issues que queremos probar
# ---------------------------------------------------------

issue_iids = [6, 7, 8]

issues_mapeadas = []


for iid in issue_iids:
    issue = adapter.obtener_issue(iid)

    mapped = mapear_issue_a_json(issue)

    issues_mapeadas.append(mapped)


# ---------------------------------------------------------
# Mostrar lo que realmente entregó IssueMapper
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("ISSUES RECIBIDAS DESDE GITLAB")
print("=" * 70)

for issue in issues_mapeadas:
    print(
        json.dumps(
            {
                "issue_iid": issue.get("issue_iid"),
                "historia_id": issue.get("historia_id"),
                "titulo": issue.get("titulo"),
                "actor": issue.get("actor"),
                "funcionalidad": issue.get("funcionalidad"),
                "objetivo": issue.get("objetivo"),
                "criterios_aceptacion": issue.get("criterios_aceptacion"),
                "restricciones": issue.get("restricciones"),
                "seguridad": issue.get("seguridad"),
                "prioridad": issue.get("prioridad"),
                "observaciones": issue.get("observaciones"),
                "validacion_entrada": issue.get("validacion_entrada"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


# ---------------------------------------------------------
# Ejecutar EXCLUSIVAMENTE Central
# ---------------------------------------------------------

resultado, diagnostico = procesar_central_en_sublotes(
    project_name="modelo-multiagente-dev",
    issues=issues_mapeadas,
    sprint_context="Recepción de Requerimientos",
    batch_size=1,
)


# ---------------------------------------------------------
# Mostrar resultado Central
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("RESULTADO CENTRAL")
print("=" * 70)

print(
    json.dumps(
        resultado,
        ensure_ascii=False,
        indent=2,
    )
)


# ---------------------------------------------------------
# Mostrar diagnóstico
# ---------------------------------------------------------

summary = diagnostico.get("summary", {})

print("\n" + "=" * 70)
print("RESUMEN DE EJECUCIÓN")
print("=" * 70)

print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
)


print("\n" + "=" * 70)
print("VALIDACIÓN PRINCIPAL")
print("=" * 70)

print("Expected:     ", summary.get("expected_issue_ids"))
print("Traceable:    ", summary.get("traceable_issue_ids"))
print("Successful:   ", summary.get("successful_issue_ids"))
print("Insufficient: ", summary.get("insufficient_issue_ids"))
print("Error:        ", summary.get("error_issue_ids"))
print("Missing:      ", summary.get("missing_issue_ids"))
print("Calls:        ", summary.get("total_calls"))
print("Retries:      ", summary.get("technical_retries"))
print("Repairs:      ", summary.get("selective_repairs"))