import csv
import json
import os
from pathlib import Path

from agents.design_central_agent import procesar_diseno_central
from core.batch_contract import analizar_respuesta_lote
from core.design_context import construir_contexto_diseno
from core.design_contract import validar_salida_central_diseno
from integrations.issue_service import obtener_issues_diseno


PROJECT_NAME = "modelo-multiagente-dev"
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
SPRINT_CONTEXT = "Diseño"


# ---------------------------------------------------------
# Matriz de trazabilidad heredada de Requerimientos
# ---------------------------------------------------------

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_trazabilidad = list(csv.DictReader(handle))


# ---------------------------------------------------------
# GitLab → DesignMapper → DesignContext
# ---------------------------------------------------------

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")
contextos_por_diseno_id = {
    issue.get("diseno_id"): construir_contexto_diseno(issue, matriz_trazabilidad)
    for issue in issues_diseno
}


def ejecutar_central_diseno(diseno_id: str) -> None:
    contexto = contextos_por_diseno_id[diseno_id]

    print("\n" + "=" * 70)
    print(f"ENTRADA CENTRAL DISEÑO — {diseno_id}")
    print("=" * 70)
    print(json.dumps(contexto, ensure_ascii=False, indent=2))

    respuesta = procesar_diseno_central(
        project_name=PROJECT_NAME,
        issues_json_str=json.dumps([contexto], ensure_ascii=False),
        sprint_context=SPRINT_CONTEXT,
    )
    resultado = analizar_respuesta_lote(respuesta, "Design_Central")

    print("\n" + "=" * 70)
    print(f"RESULTADO CENTRAL DISEÑO — {diseno_id}")
    print("=" * 70)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    resultado_issue = resultado["resultados"][0]

    valid_requirement_codes = {
        item["codigo"] for item in contexto["requerimientos_contextualizados"]
    }
    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    validacion = validar_salida_central_diseno(
        resultado_issue,
        expected_issue_ids=[contexto["issue_iid"]],
        valid_requirement_codes=valid_requirement_codes,
        valid_element_ids=valid_element_ids,
    )

    relacionados = sorted(item["requisito"] for item in resultado_issue.get("trazabilidad_diseno", []))
    sin_relacion = sorted(item["requisito"] for item in resultado_issue.get("requisitos_sin_relacion_evidente", []))
    ed_usados = {
        elemento_id
        for item in resultado_issue.get("trazabilidad_diseno", [])
        for elemento_id in item.get("elementos_relacionados", [])
    }
    ed_inventados = sorted(ed_usados - valid_element_ids)

    print("\n" + "=" * 70)
    print(f"VALIDACIÓN DE TRAZABILIDAD — {diseno_id}")
    print("=" * 70)

    print("\nRequisitos válidos esperados:")
    print("\n".join(sorted(valid_requirement_codes)))

    print("\nRelacionados:")
    print("\n".join(relacionados) or "ninguno")

    print("\nSin relación evidente:")
    print("\n".join(sin_relacion) or "ninguno")

    print("\nCódigos ED válidos:")
    print("\n".join(sorted(valid_element_ids)))

    print("\nCódigos ED inventados:")
    print("\n".join(ed_inventados) or "ninguno")

    print("\nInvariantes:")
    print(" - JSON válido:", isinstance(resultado, dict))
    print(
        " - Requisitos de entrada == requisitos clasificados en la salida:",
        (set(relacionados) | set(sin_relacion)) == valid_requirement_codes,
    )
    print(" - ED inventados:", ed_inventados or "ninguno")
    print(" - Cada requisito clasificado una sola vez:", not (set(relacionados) & set(sin_relacion)))
    print(" - validar_salida_central_diseno:", "OK" if validacion["valido"] else validacion["errores"])

    assert validacion["valido"], validacion["errores"]


ejecutar_central_diseno("DIS-001")
ejecutar_central_diseno("DIS-002")


# ---------------------------------------------------------
# DIS-003 queda fuera: trazabilidad incompleta, no se invoca Central
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]

print("\n" + "=" * 70)
print("DIS-003 — trazabilidad_incompleta (no se invoca Central)")
print("=" * 70)
print("Referencias inválidas:", contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"])
