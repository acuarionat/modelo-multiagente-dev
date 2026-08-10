import csv
import json
import os
import re
from pathlib import Path

from agents.design_central_agent import procesar_diseno_central
from agents.design_quality_agent import analizar_calidad_diseno
from agents.llm_invocation import obtener_ultimos_metadatos
from core.batch_contract import analizar_respuesta_lote
from core.design_context import construir_contexto_diseno
from core.design_contract import validar_salida_calidad_diseno
from core.design_metrics import calcular_mc03, calcular_mc04
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


def ejecutar_calidad_diseno(diseno_id: str) -> None:
    contexto = contextos_por_diseno_id[diseno_id]
    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    # -------------------- DesignCentral --------------------

    respuesta_central = procesar_diseno_central(
        project_name=PROJECT_NAME,
        issues_json_str=json.dumps([contexto], ensure_ascii=False),
        sprint_context=SPRINT_CONTEXT,
    )
    resultado_central = analizar_respuesta_lote(respuesta_central, "Design_Central")
    resultado_central_issue = resultado_central["resultados"][0]
    central_envelope = {
        "agente": "central_diseno",
        "etapa": "Diseño",
        "resultados": [resultado_central_issue],
    }

    # -------------------- DesignQuality --------------------

    respuesta_calidad = analizar_calidad_diseno(
        resultado_central_json_str=json.dumps(central_envelope, ensure_ascii=False),
        contexto_json_str=json.dumps([contexto], ensure_ascii=False),
    )
    resultado_calidad = analizar_respuesta_lote(respuesta_calidad, "Design_Quality")
    resultado_calidad_issue = resultado_calidad["resultados"][0]
    metadata_llamada = obtener_ultimos_metadatos("Design_Quality")

    metricas = resultado_calidad_issue.get("metricas", {})
    mc03_raw = metricas.get("completitud_descripcion", {})
    mc04_raw = metricas.get("acoplamiento_componentes", {})

    # -------------------- Cálculo Python --------------------

    mc03_calculado = calcular_mc03(
        mc03_raw.get("elementos_documentados", []),
        mc03_raw.get("elementos_necesarios_faltantes", []),
    )
    mc04_calculado = calcular_mc04(mc04_raw.get("componentes_evaluados", []))

    validacion = validar_salida_calidad_diseno(metricas, valid_element_ids)

    print("\n" + "=" * 70)
    print(f"RESULTADO CALIDAD DISEÑO — {diseno_id}")
    print("=" * 70)
    print(json.dumps(resultado_calidad_issue, ensure_ascii=False, indent=2))

    print("\nMC-03")
    print("Elementos documentados:", [x.get("elemento_id") for x in mc03_raw.get("elementos_documentados", [])])
    print("Elementos necesarios faltantes:", [x.get("elemento") for x in mc03_raw.get("elementos_necesarios_faltantes", [])])
    print("Precisiones:", [x.get("precision") for x in mc03_raw.get("precisiones_necesarias", [])])
    print("Resultado calculado:", mc03_calculado)

    print("\nMC-04")
    print("Componentes evaluados:", [x.get("elemento_id") for x in mc04_raw.get("componentes_evaluados", [])])
    print("Aceptables:", [x.get("elemento_id") for x in mc04_raw.get("componentes_evaluados", []) if x.get("estado_acoplamiento") == "aceptable"])
    print("No aceptables:", [x.get("elemento_id") for x in mc04_raw.get("componentes_evaluados", []) if x.get("estado_acoplamiento") == "no_aceptable"])
    print("No evaluables:", [x.get("elemento_id") for x in mc04_raw.get("componentes_evaluados", []) if x.get("estado_acoplamiento") == "no_evaluable"])
    print("Resultado calculado:", mc04_calculado)

    print("\nValidación determinística (design_contract):", "OK" if validacion["valido"] else validacion["errores"])

    print("\nCalls:", 1)
    print("Retries:", 0)
    print("Repairs:", 0)
    print("Provider:", metadata_llamada.get("provider"))
    print("Model:", metadata_llamada.get("model"))

    # -------------------- Asserts básicos obligatorios --------------------

    expected_issue_iid = contexto["issue_iid"]
    expected_diseno_id = contexto["diseno_id"]

    ids_documentados = {x.get("elemento_id") for x in mc03_raw.get("elementos_documentados", [])}
    ids_componentes = {x.get("elemento_id") for x in mc04_raw.get("componentes_evaluados", [])}
    ids_dependencias = {
        dep
        for x in mc04_raw.get("componentes_evaluados", [])
        for dep in x.get("dependencias_consideradas", [])
    }
    ids_ed_inventados = (ids_documentados | ids_componentes | ids_dependencias) - valid_element_ids

    codigos_rf_inventados = [
        item.get("elemento")
        for item in mc03_raw.get("elementos_necesarios_faltantes", [])
        if isinstance(item.get("elemento"), str) and re.fullmatch(r"RN?F-\d+", item.get("elemento").strip())
    ]

    porcentaje_no_viene_del_llm = (
        "valor" not in mc03_raw and "porcentaje" not in mc03_raw
        and "valor" not in mc04_raw and "porcentaje" not in mc04_raw
    )

    assert resultado_calidad_issue["issue_iid"] == expected_issue_iid
    assert resultado_calidad_issue["diseno_id"] == expected_diseno_id
    assert not ids_ed_inventados, ids_ed_inventados
    assert not codigos_rf_inventados, codigos_rf_inventados
    assert porcentaje_no_viene_del_llm
    assert validacion["valido"], validacion["errores"]


ejecutar_calidad_diseno("DIS-001")
ejecutar_calidad_diseno("DIS-002")


# ---------------------------------------------------------
# DIS-003 sigue bloqueado por referencias inválidas
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]

print("\n" + "=" * 70)
print("DIS-003 — trazabilidad_incompleta (no se invoca Central ni Calidad)")
print("=" * 70)
print("Referencias inválidas:", contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"])
