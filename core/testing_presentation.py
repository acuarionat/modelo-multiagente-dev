"""
Contrato único de presentación de resultados de Pruebas.

Organiza y traduce para presentación los datos ya calculados por los
agentes y por Python (graph.py / testing_metrics.py). No recalcula nada.

Consumidores: Streamlit (testing_ui.py) y documentos (utils.py).
"""


def construir_presentacion_resultado_pruebas(
    issue_pruebas,
    contexto,
    central_result,
    quality_result,
    security_result,
    evaluator_result,
    testing_summary,
):
    metricas = testing_summary["metricas"]
    mc07_summary = metricas["MC-07"]
    mc08_summary = metricas["MC-08"]
    ms08_summary = metricas["MS-08"]
    ms09_summary = metricas["MS-09"]

    quality_raw = quality_result["raw"]
    security_raw = security_result["raw"]

    interpretacion_mc07 = quality_raw.get("interpretacion_mc07", {})
    interpretacion_mc08 = quality_raw.get("interpretacion_mc08", {})
    interpretacion_ms08 = security_raw.get("interpretacion_ms08", {})
    interpretacion_ms09 = security_raw.get("interpretacion_ms09", {})

    mc07 = _construir_mc07(mc07_summary, interpretacion_mc07)
    mc08 = _construir_mc08(mc08_summary, interpretacion_mc08)
    ms08 = _construir_ms08(ms08_summary, interpretacion_ms08)
    ms09 = _construir_ms09(ms09_summary, interpretacion_ms09)

    return {
        "prueba_id": contexto["prueba_id"],
        "issue_iid": contexto["issue_iid"],
        "titulo": contexto.get("titulo", ""),
        "estado_orientativo": testing_summary["estado_orientativo"],
        "codificaciones_relacionadas": contexto.get("codificaciones_relacionadas", []),
        "metricas": {
            "MC-07": mc07,
            "MC-08": mc08,
            "MS-08": ms08,
            "MS-09": ms09,
        },
        "correcciones_necesarias": testing_summary.get("correcciones_necesarias") or [],
        "precisiones_necesarias": testing_summary.get("precisiones") or [],
        "oportunidades_mejora": testing_summary.get("oportunidades_mejora") or [],
        "trazabilidad": contexto.get("trazabilidad", {}),
        "conclusion_calidad": evaluator_result.get("conclusion_calidad", ""),
        "conclusion_seguridad": evaluator_result.get("conclusion_seguridad", ""),
        "recomendacion_revision": evaluator_result.get("recomendacion_revision", ""),
        "contexto_original": {
            "descripcion": issue_pruebas.get("descripcion", ""),
            "pendientes": issue_pruebas.get("pendientes", []),
            "observaciones": issue_pruebas.get("observaciones", []),
            "pruebas_funcionales": issue_pruebas.get("pruebas_funcionales", []),
            "fallos": issue_pruebas.get("fallos", []),
            "controles_seguridad": issue_pruebas.get("controles_seguridad", []),
            "pruebas_seguridad": issue_pruebas.get("pruebas_seguridad", []),
            "evidencias": issue_pruebas.get("evidencias", []),
        },
        "central_result": {
            "coherencia_declarado_vs_evidencia": central_result.get("coherencia_declarado_vs_evidencia", {}),
            "inconsistencias_detectadas": central_result.get("inconsistencias_detectadas", []),
            "trazabilidad_confirmada": central_result.get("trazabilidad_confirmada", {}),
        },
    }


def _construir_mc07(mc07_summary, interpretacion_mc07):
    n = mc07_summary.get("numerador")
    d = mc07_summary.get("denominador")

    return {
        "codigo": "MC-07",
        "nombre": "Corrección Funcional",
        "valor": mc07_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": mc07_summary.get("estado"),
        "que_mide": (
            "Evalúa si las funcionalidades evaluadas en las pruebas tienen "
            "todas sus pruebas necesarias registradas como aprobadas."
        ),
        "funcionalidades_con_brecha": interpretacion_mc07.get("funcionalidades_con_brecha", []),
        "conclusion": interpretacion_mc07.get("conclusion", ""),
        "resultado": (
            f"{n} de {d} funcionalidades evaluadas resultaron completamente correctas."
            if d else "No se registraron pruebas funcionales evaluables."
        ),
    }


def _construir_mc08(mc08_summary, interpretacion_mc08):
    n = mc08_summary.get("numerador")
    d = mc08_summary.get("denominador")

    return {
        "codigo": "MC-08",
        "nombre": "Corrección de Fallos",
        "valor": mc08_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": mc08_summary.get("estado"),
        "fallos_detectados": mc08_summary.get("fallos_detectados"),
        "fallos_corregidos": mc08_summary.get("fallos_corregidos"),
        "fallos_corregidos_verificados": mc08_summary.get("fallos_corregidos_verificados"),
        "que_mide": (
            "Evalúa la proporción de fallos detectados durante las pruebas "
            "que fueron corregidos y verificados."
        ),
        "fallos_pendientes": interpretacion_mc08.get("fallos_pendientes", []),
        "conclusion": interpretacion_mc08.get("conclusion", ""),
        "resultado": (
            f"{n} de {d} fallos detectados fueron corregidos y verificados."
            if d else "No se detectaron fallos durante las pruebas realizadas."
        ),
    }


def _construir_ms08(ms08_summary, interpretacion_ms08):
    n = ms08_summary.get("numerador")
    d = ms08_summary.get("denominador")

    return {
        "codigo": "MS-08",
        "nombre": "Cobertura de Verificación de Controles",
        "valor": ms08_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": ms08_summary.get("estado"),
        "que_mide": (
            "Evalúa la proporción de controles de seguridad aplicables que "
            "fueron efectivamente verificados durante las pruebas."
        ),
        "controles_no_verificados": interpretacion_ms08.get("controles_no_verificados", []),
        "conclusion": interpretacion_ms08.get("conclusion_ms08", ""),
        "resultado": (
            f"{n} de {d} controles de seguridad aplicables fueron verificados."
            if d else "No se registraron controles de seguridad aplicables."
        ),
    }


def _construir_ms09(ms09_summary, interpretacion_ms09):
    n = ms09_summary.get("numerador")
    d = ms09_summary.get("denominador")

    return {
        "codigo": "MS-09",
        "nombre": "Pruebas de Seguridad Satisfactorias",
        "valor": ms09_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": ms09_summary.get("estado"),
        "que_mide": (
            "Evalúa la proporción de pruebas de seguridad ejecutadas que "
            "resultaron satisfactorias."
        ),
        "pruebas_fallidas": interpretacion_ms09.get("pruebas_fallidas", []),
        "conclusion": interpretacion_ms09.get("conclusion_ms09", ""),
        "resultado": (
            f"{n} de {d} pruebas de seguridad ejecutadas fueron satisfactorias."
            if d else "No se ejecutaron pruebas de seguridad con resultado reconocido."
        ),
    }
