import csv
import json
import os
import re
import sqlite3
from pathlib import Path

from agents.design_security_agent import analizar_seguridad_diseno
from agents.llm_invocation import obtener_ultimos_metadatos
from core.batch_contract import analizar_respuesta_lote
from core.design_context import construir_contexto_diseno
from core.design_contract import normalizar_elementos_responsables, validar_salida_seguridad_diseno
from core.design_metrics import calcular_ms03, calcular_ms04
from integrations.issue_service import obtener_issues_diseno


PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

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


def ejecutar_seguridad_diseno(diseno_id: str) -> None:
    contexto = contextos_por_diseno_id[diseno_id]
    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    historias = extraer_historias_relacionadas(contexto)
    contexto_seguridad_heredado = obtener_seguridad_heredada(historias)
    contexto_enriquecido = {**contexto, "contexto_seguridad_heredado": contexto_seguridad_heredado}

    # -------------------- DesignSecurity --------------------

    respuesta_seguridad = analizar_seguridad_diseno(
        issues_json_str=json.dumps([contexto_enriquecido], ensure_ascii=False),
    )
    resultado_seguridad = analizar_respuesta_lote(respuesta_seguridad, "Design_Security")
    resultado_seguridad_issue = resultado_seguridad["resultados"][0]
    metadata_llamada = obtener_ultimos_metadatos("Design_Security")

    for control in (resultado_seguridad_issue.get("cobertura_controles") or {}).get("controles_definidos", []):
        control["elementos_responsables"] = normalizar_elementos_responsables(control)
        control.pop("elemento_responsable", None)

    ms03_raw = resultado_seguridad_issue.get("cobertura_amenazas", {})
    ms04_raw = resultado_seguridad_issue.get("cobertura_controles", {})

    # -------------------- Cálculo Python --------------------

    ms03_calculado = calcular_ms03(ms03_raw)
    ms04_calculado = calcular_ms04(ms04_raw)

    expected_issue_iid = contexto["issue_iid"]
    expected_diseno_id = contexto["diseno_id"]

    validacion = validar_salida_seguridad_diseno(
        resultado_seguridad_issue, expected_issue_iid, expected_diseno_id, valid_element_ids,
    )

    print("\n" + "=" * 70)
    print(f"SEGURIDAD DISEÑO — {diseno_id}")
    print("=" * 70)
    print(json.dumps(resultado_seguridad_issue, ensure_ascii=False, indent=2))

    def formatear_resultado(valor):
        return f"{valor * 100:.0f} %" if valor is not None else "No aplicable"

    print("\nMS-03")
    print("Amenazas identificadas:", len(ms03_raw.get("amenazas_identificadas", [])))
    print("Con tratamiento:", len(ms03_raw.get("amenazas_con_tratamiento", [])))
    print("Sin tratamiento:", len(ms03_raw.get("amenazas_sin_tratamiento", [])))
    print("Necesarias faltantes alta confianza:", len([
        x for x in ms03_raw.get("amenazas_necesarias_faltantes", [])
        if str(x.get("confianza", "")).casefold() == "alta"
    ]))
    print("Precisiones:", len(ms03_raw.get("precisiones_necesarias", [])))
    print("Resultado:", formatear_resultado(ms03_calculado.get("valor")))

    print("\nMS-04")
    print("Controles aplicables:", len(ms04_raw.get("controles_aplicables", [])))
    print("Definidos:", len(ms04_raw.get("controles_definidos", [])))
    print("Faltantes:", len(ms04_raw.get("controles_faltantes", [])))
    print("Precisiones:", len(ms04_raw.get("precisiones_necesarias", [])))
    print("Resultado:", formatear_resultado(ms04_calculado.get("valor")))

    print("\nValidación determinística (design_contract):", "OK" if validacion["valido"] else validacion["errores"])

    print("\nCalls:", 1)
    print("Retries:", 0)
    print("Repairs:", 0)
    print("Provider:", metadata_llamada.get("provider"))
    print("Model:", metadata_llamada.get("model"))

    # -------------------- Asserts básicos obligatorios --------------------

    ids_afectados = {
        elemento_id
        for item in ms03_raw.get("amenazas_identificadas", [])
        for elemento_id in item.get("elementos_afectados", [])
    }
    ids_responsables = {
        responsable
        for item in ms04_raw.get("controles_definidos", [])
        for responsable in item.get("elementos_responsables", [])
    }
    ids_ed_inventados = (ids_afectados | ids_responsables) - valid_element_ids

    porcentaje_no_viene_del_llm = (
        "valor" not in ms03_raw and "porcentaje" not in ms03_raw
        and "valor" not in ms04_raw and "porcentaje" not in ms04_raw
    )

    assert resultado_seguridad_issue["issue_iid"] == expected_issue_iid
    assert resultado_seguridad_issue["diseno_id"] == expected_diseno_id
    assert not ids_ed_inventados, ids_ed_inventados
    assert porcentaje_no_viene_del_llm
    assert validacion["valido"], validacion["errores"]


ejecutar_seguridad_diseno("DIS-001")
ejecutar_seguridad_diseno("DIS-002")


# ---------------------------------------------------------
# DIS-003 sigue bloqueado por referencias inválidas
# ---------------------------------------------------------

contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]

print("\n" + "=" * 70)
print("DIS-003 — trazabilidad_incompleta (no se invoca Central ni Seguridad)")
print("=" * 70)
print("Referencias inválidas:", contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"])


# ---------------------------------------------------------
# Validación de elementos_responsables (contrato canónico)
# ---------------------------------------------------------

print("\n" + "=" * 70)
print("VALIDACIÓN DE ELEMENTOS_RESPONSABLES")
print("=" * 70)

valid_ids = {"ED-01", "ED-02", "ED-03", "ED-04"}

base_resultado = {
    "issue_iid": 16,
    "diseno_id": "DIS-001",
    "cobertura_amenazas": {
        "amenazas_identificadas": [],
        "amenazas_con_tratamiento": [],
        "amenazas_sin_tratamiento": [],
    },
    "cobertura_controles": {
        "controles_aplicables": [
            {"control": "C1", "aspecto_relacionado": "Autenticación", "confianza": "alta"},
        ],
        "controles_definidos": [],
        "controles_faltantes": [],
    },
}

import copy

# Caso 1: un responsable → debe pasar
r1 = copy.deepcopy(base_resultado)
r1["cobertura_controles"]["controles_definidos"] = [
    {"control": "C1", "medida_documentada": "M1", "elementos_responsables": ["ED-01"]},
]
v1 = validar_salida_seguridad_diseno(r1, 16, "DIS-001", valid_ids)
assert v1["valido"], f"Caso 1 falló: {v1['errores']}"
print("Caso 1 (un responsable): OK")

# Caso 2: varios responsables → debe pasar
r2 = copy.deepcopy(base_resultado)
r2["cobertura_controles"]["controles_definidos"] = [
    {"control": "C1", "medida_documentada": "M1", "elementos_responsables": ["ED-02", "ED-04"]},
]
v2 = validar_salida_seguridad_diseno(r2, 16, "DIS-001", valid_ids)
assert v2["valido"], f"Caso 2 falló: {v2['errores']}"
print("Caso 2 (varios responsables): OK")

# Caso 3: un responsable inválido entre válidos → debe fallar solo por ED-99
r3 = copy.deepcopy(base_resultado)
r3["cobertura_controles"]["controles_definidos"] = [
    {"control": "C1", "medida_documentada": "M1", "elementos_responsables": ["ED-02", "ED-99"]},
]
v3 = validar_salida_seguridad_diseno(r3, 16, "DIS-001", valid_ids)
assert not v3["valido"]
assert any("ED-99" in error for error in v3["errores"])
assert not any("ED-02" in error for error in v3["errores"])
print("Caso 3 (ED-99 inválido): OK")

# Caso 4: compatibilidad con campo legacy "elemento_responsable": "ED-02, ED-04"
r4 = copy.deepcopy(base_resultado)
r4["cobertura_controles"]["controles_definidos"] = [
    {"control": "C1", "medida_documentada": "M1", "elemento_responsable": "ED-02, ED-04"},
]
for control in r4["cobertura_controles"]["controles_definidos"]:
    control["elementos_responsables"] = normalizar_elementos_responsables(control)
    control.pop("elemento_responsable", None)

assert r4["cobertura_controles"]["controles_definidos"][0]["elementos_responsables"] == ["ED-02", "ED-04"]
v4 = validar_salida_seguridad_diseno(r4, 16, "DIS-001", valid_ids)
assert v4["valido"], f"Caso 4 falló: {v4['errores']}"
print("Caso 4 (compatibilidad legacy string): OK")

# Caso 5: compatibilidad con campo legacy "elemento_responsable": "ED-02"
r5 = copy.deepcopy(base_resultado)
r5["cobertura_controles"]["controles_definidos"] = [
    {"control": "C1", "medida_documentada": "M1", "elemento_responsable": "ED-02"},
]
for control in r5["cobertura_controles"]["controles_definidos"]:
    control["elementos_responsables"] = normalizar_elementos_responsables(control)
    control.pop("elemento_responsable", None)

assert r5["cobertura_controles"]["controles_definidos"][0]["elementos_responsables"] == ["ED-02"]
v5 = validar_salida_seguridad_diseno(r5, 16, "DIS-001", valid_ids)
assert v5["valido"], f"Caso 5 falló: {v5['errores']}"
print("Caso 5 (compatibilidad legacy single): OK")

print("\nTodas las validaciones de elementos_responsables pasaron.")
