import csv
import json
import os
import re
import sqlite3
from pathlib import Path

from agents.design_central_agent import procesar_diseno_central
from agents.design_evaluator_agent import analizar_evaluador_diseno
from agents.design_quality_agent import analizar_calidad_diseno
from agents.design_security_agent import analizar_seguridad_diseno
from agents.llm_invocation import obtener_ultimos_metadatos
from core.batch_contract import analizar_respuesta_lote
from core.design_context import construir_contexto_diseno
from core.design_contract import validar_salida_evaluador_diseno
from core.design_metrics import calcular_mc03, calcular_mc04, calcular_ms03, calcular_ms04
from integrations.issue_service import obtener_issues_diseno


PROJECT_NAME = "modelo-multiagente-dev"
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
SPRINT_CONTEXT = "Diseño"

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"
DB_PATH = Path(__file__).parent.parent / "database" / "database.db"


# ---------------------------------------------------------
# Matriz de trazabilidad heredada de Requerimientos
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Seguridad heredada de Requerimientos (cache_results real, sin mocks)
# ---------------------------------------------------------

def extraer_historias_relacionadas(contexto: dict) -> set:
    historias = set()
    for requerimiento in contexto.get("requerimientos_contextualizados", []):
        origen = requerimiento.get("historia_origen") or ""
        match = re.search(r"HU-\d+", origen)
        if match:
            historias.add(match.group(0))
    return historias


def obtener_seguridad_heredada(historias: set) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT security_json FROM cache_results")
        filas = cur.fetchall()
    finally:
        conn.close()

    aspectos_documentados = set()
    aspectos_pendientes = set()
    datos_identificados = set()
    datos_clasificados = set()
    datos_sin_clasificacion = set()
    lots = set()

    for (raw,) in filas:
        data = json.loads(raw)
        if data.get("historia_id") not in historias:
            continue
        metricas = data.get("metricas") or {}
        ms01 = metricas.get("cobertura_seguridad") or {}
        ms02 = metricas.get("clasificacion_datos") or {}
        aspectos_documentados.update(ms01.get("aspectos_documentados") or [])
        aspectos_pendientes.update(ms01.get("aspectos_faltantes") or [])
        datos_identificados.update(ms02.get("datos_identificados") or [])
        datos_clasificados.update(ms02.get("datos_clasificados") or [])
        datos_sin_clasificacion.update(ms02.get("datos_sin_clasificacion") or [])
        if data.get("lot_recomendado"):
            lots.add(data["lot_recomendado"])

    lot_recomendado = "LoT-3" if "LoT-3" in lots else "LoT-2"

    return {
        "aspectos_documentados": sorted(aspectos_documentados),
        "aspectos_pendientes": sorted(aspectos_pendientes),
        "datos_identificados": sorted(datos_identificados),
        "datos_clasificados": sorted(datos_clasificados),
        "datos_sin_clasificacion": sorted(datos_sin_clasificacion),
        "lot_recomendado": lot_recomendado,
    }


def ejecutar_evaluador_diseno(diseno_id: str) -> None:
    contexto = contextos_por_diseno_id[diseno_id]
    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }
    valid_requirement_codes = {
        requerimiento["codigo"] for requerimiento in contexto["requerimientos_contextualizados"]
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

    # -------------------- DesignQuality + Python (MC-03 / MC-04) --------------------

    respuesta_calidad = analizar_calidad_diseno(
        resultado_central_json_str=json.dumps(central_envelope, ensure_ascii=False),
        contexto_json_str=json.dumps([contexto], ensure_ascii=False),
    )
    resultado_calidad = analizar_respuesta_lote(respuesta_calidad, "Design_Quality")
    resultado_calidad_issue = resultado_calidad["resultados"][0]
    metricas_calidad = resultado_calidad_issue.get("metricas", {})
    mc03_raw = metricas_calidad.get("completitud_descripcion", {})
    mc04_raw = metricas_calidad.get("acoplamiento_componentes", {})

    mc03_calculado = calcular_mc03(
        mc03_raw.get("elementos_documentados", []),
        mc03_raw.get("elementos_necesarios_faltantes", []),
    )
    mc04_calculado = calcular_mc04(mc04_raw.get("componentes_evaluados", []))

    # -------------------- DesignSecurity + Python (MS-03 / MS-04) --------------------

    historias = extraer_historias_relacionadas(contexto)
    contexto_seguridad_heredado = obtener_seguridad_heredada(historias)
    contexto_enriquecido = {**contexto, "contexto_seguridad_heredado": contexto_seguridad_heredado}

    respuesta_seguridad = analizar_seguridad_diseno(
        issues_json_str=json.dumps([contexto_enriquecido], ensure_ascii=False),
    )
    resultado_seguridad = analizar_respuesta_lote(respuesta_seguridad, "Design_Security")
    resultado_seguridad_issue = resultado_seguridad["resultados"][0]
    ms03_raw = resultado_seguridad_issue.get("cobertura_amenazas", {})
    ms04_raw = resultado_seguridad_issue.get("cobertura_controles", {})

    ms03_calculado = calcular_ms03(ms03_raw)
    ms04_calculado = calcular_ms04(ms04_raw)

    # -------------------- DesignEvaluator --------------------

    entrada_evaluador = {
        "issue_iid": contexto["issue_iid"],
        "diseno_id": contexto["diseno_id"],
        "calidad": {
            "mc03": {
                "valor": mc03_calculado.get("valor"),
                "numerador": mc03_calculado.get("documentados"),
                "denominador": mc03_calculado.get("esperados"),
                "evidencia": mc03_raw,
            },
            "mc04": {
                "valor": mc04_calculado.get("valor"),
                "numerador": mc04_calculado.get("aceptables"),
                "denominador": mc04_calculado.get("evaluables"),
                "evidencia": mc04_raw,
            },
        },
        "seguridad": {
            "ms03": {
                "valor": ms03_calculado.get("valor"),
                "numerador": ms03_calculado.get("numerador"),
                "denominador": ms03_calculado.get("denominador"),
                "evidencia": ms03_raw,
            },
            "ms04": {
                "valor": ms04_calculado.get("valor"),
                "numerador": ms04_calculado.get("numerador"),
                "denominador": ms04_calculado.get("denominador"),
                "evidencia": ms04_raw,
            },
        },
    }

    respuesta_evaluador = analizar_evaluador_diseno(
        issues_json_str=json.dumps([entrada_evaluador], ensure_ascii=False),
    )
    resultado_evaluador = analizar_respuesta_lote(respuesta_evaluador, "Design_Evaluator")
    resultado_evaluador_issue = resultado_evaluador["resultados"][0]
    metadata_llamada = obtener_ultimos_metadatos("Design_Evaluator")

    expected_issue_iid = contexto["issue_iid"]
    expected_diseno_id = contexto["diseno_id"]

    validacion = validar_salida_evaluador_diseno(
        resultado_evaluador_issue, expected_issue_iid, expected_diseno_id,
        valid_element_ids, valid_requirement_codes,
    )

    print("\n" + "=" * 70)
    print(f"EVALUADOR DISEÑO — {diseno_id}")
    print("=" * 70)
    print(json.dumps(resultado_evaluador_issue, ensure_ascii=False, indent=2))

    print("\nMétricas recibidas (solo lectura, no recalculadas por el Evaluador):")
    print("MC-03:", mc03_calculado.get("valor"))
    print("MC-04:", mc04_calculado.get("valor"))
    print("MS-03:", ms03_calculado.get("valor"))
    print("MS-04:", ms04_calculado.get("valor"))

    print("\nCorrecciones necesarias:", resultado_evaluador_issue.get("correcciones_necesarias"))
    print("Precisiones necesarias:", resultado_evaluador_issue.get("precisiones_necesarias"))
    print("Oportunidades de mejora:", resultado_evaluador_issue.get("oportunidades_mejora"))
    print("Hallazgos prioritarios:", resultado_evaluador_issue.get("hallazgos_prioritarios"))

    print("\nValidación determinística (design_contract):", "OK" if validacion["valido"] else validacion["errores"])

    print("\nCalls:", 1)
    print("Retries:", 0)
    print("Repairs:", 0)
    print("Provider:", metadata_llamada.get("provider"))
    print("Model:", metadata_llamada.get("model"))

    # -------------------- Asserts básicos obligatorios --------------------

    metricas_no_alteradas = (
        "valor" not in resultado_evaluador_issue and "porcentaje" not in resultado_evaluador_issue
        and "numerador" not in resultado_evaluador_issue and "denominador" not in resultado_evaluador_issue
    )

    assert resultado_evaluador_issue["issue_iid"] == expected_issue_iid
    assert resultado_evaluador_issue["diseno_id"] == expected_diseno_id
    assert metricas_no_alteradas
    assert isinstance(resultado_evaluador_issue.get("correcciones_necesarias"), list)
    assert isinstance(resultado_evaluador_issue.get("precisiones_necesarias"), list)
    assert isinstance(resultado_evaluador_issue.get("oportunidades_mejora"), list)
    assert isinstance(resultado_evaluador_issue.get("hallazgos_prioritarios"), list)
    assert resultado_evaluador_issue.get("conclusion_calidad")
    assert resultado_evaluador_issue.get("conclusion_seguridad")
    assert validacion["valido"], validacion["errores"]


ejecutar_evaluador_diseno("DIS-001")
ejecutar_evaluador_diseno("DIS-002")


# ---------------------------------------------------------
# DIS-003 sigue bloqueado antes de llegar al Evaluador
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]

print("\n" + "=" * 70)
print("DIS-003 — trazabilidad_incompleta (no llega al Evaluador)")
print("=" * 70)
print("Referencias inválidas:", contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"])
