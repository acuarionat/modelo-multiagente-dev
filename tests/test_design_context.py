import csv
import json
import os
from pathlib import Path

from core.design_context import construir_contexto_diseno
from integrations.issue_service import obtener_issues_diseno


# ---------------------------------------------------------
# Matriz de trazabilidad heredada de Requerimientos
# ---------------------------------------------------------

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_trazabilidad = list(csv.DictReader(handle))


# ---------------------------------------------------------
# Conexión real a GitLab — Milestone Diseño
# ---------------------------------------------------------

PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")


# ---------------------------------------------------------
# Construir y mostrar el contexto de cada Issue DIS-xxx
# ---------------------------------------------------------

for issue in sorted(issues_diseno, key=lambda item: item.get("diseno_id", "")):
    contexto = construir_contexto_diseno(issue, matriz_trazabilidad)
    validacion = contexto["validacion_trazabilidad"]

    print("\n" + "=" * 70)
    print(contexto.get("diseno_id"))
    print("=" * 70)

    print("Requerimientos declarados:")
    print(", ".join(issue.get("requerimientos_relacionados", [])) or "ninguno")

    print("\nReferencias válidas:")
    print(", ".join(validacion["referencias_validas"]) or "ninguna")

    print("\nReferencias inválidas:")
    print(", ".join(validacion["referencias_invalidas"]) or "ninguna")

    print("\nRequerimientos contextualizados:")
    print(json.dumps(contexto["requerimientos_contextualizados"], ensure_ascii=False, indent=2))
