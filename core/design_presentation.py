"""
Contrato único de presentación de resultados de Diseño.

Organiza y traduce para presentación los datos ya calculados por los agentes
y por Python (graph.py / design_metrics.py). No recalcula nada.

Consumidores: Streamlit (design_ui.py) y PDF (utils.py).
"""


def construir_presentacion_resultado_diseno(
    contexto,
    central_result,
    quality_result,
    security_result,
    evaluator_result,
    design_summary,
    trazabilidad_filas,
):
    mc03_summary = design_summary["metricas"]["MC-03"]
    mc04_summary = design_summary["metricas"]["MC-04"]
    ms03_summary = design_summary["metricas"]["MS-03"]
    ms04_summary = design_summary["metricas"]["MS-04"]

    quality_raw = quality_result["raw"]
    security_raw = security_result["raw"]

    mc03_raw = quality_raw.get("metricas", {}).get("completitud_descripcion", {})
    mc04_raw = quality_raw.get("metricas", {}).get("acoplamiento_componentes", {})
    ms03_raw = security_raw.get("cobertura_amenazas", {})
    ms04_raw = security_raw.get("cobertura_controles", {})

    elementos_diseno = contexto.get("elementos_diseno", [])
    relaciones = contexto.get("relaciones", [])
    reqs_ctx = contexto.get("requerimientos_contextualizados", [])

    mc03 = _construir_mc03(mc03_summary, mc03_raw, elementos_diseno)
    mc04 = _construir_mc04(mc04_summary, mc04_raw, relaciones)
    ms03 = _construir_ms03(ms03_summary, ms03_raw)
    ms04 = _construir_ms04(ms04_summary, ms04_raw)

    trazabilidad_del_dis = _construir_trazabilidad_del_dis(
        contexto["diseno_id"], trazabilidad_filas,
    )

    propuesta = construir_propuesta_maximo_diseno(quality_result, security_result)

    return {
        "diseno_id": contexto["diseno_id"],
        "issue_iid": contexto["issue_iid"],
        "titulo": contexto.get("titulo", ""),
        "estado_orientativo": design_summary["estado_orientativo"],
        "indice_calidad": design_summary["indice_calidad_diseno"],
        "indice_seguridad": design_summary["indice_seguridad_diseno"],
        "requerimientos_relacionados": [req["codigo"] for req in reqs_ctx],
        "elementos_diseno": elementos_diseno,
        "relaciones_diseno": relaciones,
        "metricas": {
            "MC-03": mc03,
            "MC-04": mc04,
            "MS-03": ms03,
            "MS-04": ms04,
        },
        "correcciones_necesarias": design_summary.get("correcciones_necesarias") or [],
        "precisiones_necesarias": design_summary.get("precisiones_necesarias") or [],
        "oportunidades_mejora": design_summary.get("oportunidades_mejora") or [],
        "propuesta_para_maximo": propuesta,
        "trazabilidad": trazabilidad_del_dis,
        "conclusion_calidad": evaluator_result.get("conclusion_calidad", ""),
        "conclusion_seguridad": evaluator_result.get("conclusion_seguridad", ""),
        "contexto_original": {
            "restricciones": contexto.get("restricciones", []),
            "decisiones_diseno": contexto.get("decisiones_diseno", []),
            "seguridad": contexto.get("seguridad", {}),
            "requerimientos_contextualizados": reqs_ctx,
        },
        "central_result": {
            "trazabilidad_diseno": central_result.get("trazabilidad_diseno", []),
            "requisitos_sin_relacion_evidente": central_result.get("requisitos_sin_relacion_evidente", []),
        },
    }


def _construir_mc03(mc03_summary, mc03_raw, elementos_diseno):
    elementos_documentados_raw = mc03_raw.get("elementos_documentados", [])
    elementos_faltantes_raw = mc03_raw.get("elementos_necesarios_faltantes", [])

    ids_documentados = {
        item.get("elemento_id") for item in elementos_documentados_raw if isinstance(item, dict)
    }

    ed_por_id = {ed["elemento_id"]: ed for ed in elementos_diseno}

    elementos_evaluados = []
    for item in elementos_documentados_raw:
        if not isinstance(item, dict):
            continue
        eid = item.get("elemento_id", "")
        ed_original = ed_por_id.get(eid, {})
        elementos_evaluados.append({
            "id": eid,
            "nombre": ed_original.get("nombre", item.get("nombre", "")),
            "tipo": ed_original.get("tipo", item.get("tipo", "")),
            "responsabilidad": ed_original.get("responsabilidad", item.get("responsabilidad", "")),
            "estado": "documentado",
        })

    elementos_faltantes = []
    for item in elementos_faltantes_raw:
        if not isinstance(item, dict):
            continue
        if str(item.get("confianza", "")).casefold() != "alta":
            continue
        elementos_faltantes.append({
            "id": item.get("elemento", ""),
            "nombre": item.get("nombre", ""),
            "tipo": item.get("tipo", ""),
            "responsabilidad": item.get("responsabilidad", ""),
            "estado": "faltante",
        })

    n = mc03_summary["numerador"]
    d = mc03_summary["denominador"]

    return {
        "codigo": "MC-03",
        "nombre": "Completitud de la Descripción",
        "valor": mc03_summary["valor"],
        "numerador": n,
        "denominador": d,
        "que_mide": (
            "Evalúa si los Elementos de Diseño que forman parte "
            "del diseño cuentan con una responsabilidad claramente "
            "definida y están suficientemente descritos."
        ),
        "elementos_evaluados": elementos_evaluados,
        "elementos_faltantes": elementos_faltantes,
        "resultado": (
            f"{'Los' if n > 1 else 'El'} {n} de {d} "
            f"elemento{'s' if d != 1 else ''} del diseño "
            f"{'cuentan' if n > 1 else 'cuenta'} con una descripción suficiente."
            if d > 0 else "No se identificaron elementos evaluables."
        ),
    }


def _construir_mc04(mc04_summary, mc04_raw, relaciones_contexto):
    componentes_raw = mc04_raw.get("componentes_evaluados", [])

    componentes_aceptables = []
    componentes_no_aceptables = []
    no_evaluables = []

    for comp in componentes_raw:
        if not isinstance(comp, dict):
            continue
        estado = comp.get("estado_acoplamiento", "")
        item = {
            "elemento_id": comp.get("elemento_id", ""),
            "dependencias": comp.get("dependencias_consideradas", []),
            "justificacion": comp.get("justificacion", ""),
        }
        if estado == "aceptable":
            componentes_aceptables.append(item)
        elif estado == "no_aceptable":
            componentes_no_aceptables.append(item)
        else:
            no_evaluables.append(item)

    relaciones_documentadas = [
        {
            "origen": rel.get("origen", ""),
            "destino": rel.get("destino", ""),
            "tipo": rel.get("tipo", ""),
            "descripcion": rel.get("descripcion", ""),
        }
        for rel in relaciones_contexto
    ]

    n = mc04_summary["numerador"]
    d = mc04_summary["denominador"]

    return {
        "codigo": "MC-04",
        "nombre": "Acoplamiento de Componentes",
        "valor": mc04_summary["valor"],
        "numerador": n,
        "denominador": d,
        "que_mide": (
            "Evalúa si los componentes del diseño presentan un nivel de "
            "acoplamiento aceptable, con dependencias claras y controladas "
            "entre los Elementos de Diseño."
        ),
        "relaciones_documentadas": relaciones_documentadas,
        "componentes_aceptables": componentes_aceptables,
        "componentes_no_aceptables": componentes_no_aceptables,
        "no_evaluables": no_evaluables,
        "interpretacion": (
            f"{n} de {d} componentes evaluados presentan un acoplamiento aceptable."
            if d > 0 else "No se identificaron componentes evaluables."
        ),
    }


def _construir_ms03(ms03_summary, ms03_raw):
    amenazas_identificadas = ms03_raw.get("amenazas_identificadas", [])
    amenazas_con_tratamiento_set = set(ms03_raw.get("amenazas_con_tratamiento") or [])

    amenazas = []
    for item in amenazas_identificadas:
        if not isinstance(item, dict):
            continue
        identidad = item.get("identidad", "")
        tiene = item.get("tratamiento_documentado", identidad in amenazas_con_tratamiento_set)
        amenazas.append({
            "amenaza": identidad,
            "tiene_tratamiento": bool(tiene),
            "tratamiento": identidad if tiene else None,
            "elementos_afectados": item.get("elementos_afectados", []),
        })

    n = ms03_summary["numerador"]
    d = ms03_summary["denominador"]

    return {
        "codigo": "MS-03",
        "nombre": "Cobertura de Amenazas con Tratamiento Definido",
        "valor": ms03_summary["valor"],
        "numerador": n,
        "denominador": d,
        "que_mide": (
            "Evalúa si las amenazas identificadas en el diseño "
            "cuentan con un tratamiento documentado que mitigue "
            "o controle el riesgo asociado."
        ),
        "amenazas": amenazas,
    }


def _construir_ms04(ms04_summary, ms04_raw):
    controles_aplicables = ms04_raw.get("controles_aplicables", [])
    controles_definidos = ms04_raw.get("controles_definidos", [])
    controles_faltantes = ms04_raw.get("controles_faltantes", [])

    definidos_map = {}
    for c in controles_definidos:
        if isinstance(c, dict):
            definidos_map[c.get("control", "")] = c

    controles = []
    for item in controles_aplicables:
        if not isinstance(item, dict):
            continue
        nombre_control = item.get("control", "")
        definido_info = definidos_map.get(nombre_control)
        responsables = definido_info.get("elementos_responsables", []) if definido_info else []
        controles.append({
            "control": nombre_control,
            "aspecto": item.get("aspecto_relacionado", ""),
            "definido": definido_info is not None,
            "responsables": ", ".join(responsables) if responsables else "",
            "medida_documentada": definido_info.get("medida_documentada") if definido_info else None,
        })

    n = ms04_summary["numerador"]
    d = ms04_summary["denominador"]

    return {
        "codigo": "MS-04",
        "nombre": "Cobertura de Controles de Seguridad Definidos",
        "valor": ms04_summary["valor"],
        "numerador": n,
        "denominador": d,
        "que_mide": (
            "Evalúa si los controles de seguridad aplicables al diseño "
            "están definidos y asignados a un Elemento de Diseño responsable."
        ),
        "controles": controles,
        "controles_faltantes_detalle": [
            {
                "control": c.get("control", ""),
                "justificacion": c.get("justificacion", ""),
            }
            for c in controles_faltantes if isinstance(c, dict)
        ],
    }


def _construir_trazabilidad_del_dis(diseno_id, filas_matriz):
    cubiertos = []
    pendientes_relacion = []
    requieren_revision = []

    for fila in filas_matriz:
        if fila.get("Diseño") != diseno_id:
            continue
        codigo = fila.get("Código requisito", "")
        estado = fila.get("Estado de trazabilidad", "")
        if "Cubierto" in estado:
            cubiertos.append(codigo)
        elif "Pendiente" in estado:
            pendientes_relacion.append(codigo)
        elif "Requiere" in estado:
            requieren_revision.append(codigo)

    return {
        "cubiertos": cubiertos,
        "pendientes_relacion": pendientes_relacion,
        "requieren_revision": requieren_revision,
    }


def construir_propuesta_maximo_diseno(quality_result, security_result):
    propuesta = []
    quality_raw = quality_result["raw"]
    security_raw = security_result["raw"]

    mc03_raw = quality_raw.get("metricas", {}).get("completitud_descripcion", {})
    faltantes_mc03 = mc03_raw.get("elementos_necesarios_faltantes", [])
    for item in faltantes_mc03:
        if not isinstance(item, dict):
            continue
        if str(item.get("confianza", "")).casefold() != "alta":
            continue
        nombre = item.get("elemento", item.get("nombre", ""))
        if nombre:
            propuesta.append(
                f"Documentar el elemento faltante identificado: {nombre}."
            )

    mc04_raw = quality_raw.get("metricas", {}).get("acoplamiento_componentes", {})
    for comp in mc04_raw.get("componentes_evaluados", []):
        if not isinstance(comp, dict):
            continue
        if comp.get("estado_acoplamiento") == "no_aceptable":
            eid = comp.get("elemento_id", "")
            propuesta.append(
                f"Reducir el acoplamiento del componente {eid} para alcanzar un nivel aceptable."
            )

    ms03_raw = security_raw.get("cobertura_amenazas", {})
    for amenaza in ms03_raw.get("amenazas_sin_tratamiento", []):
        texto = amenaza if isinstance(amenaza, str) else str(amenaza)
        if texto:
            propuesta.append(
                f"Definir y documentar el tratamiento de la amenaza: {texto}."
            )

    ms04_raw = security_raw.get("cobertura_controles", {})
    for control in ms04_raw.get("controles_faltantes", []):
        if not isinstance(control, dict):
            continue
        nombre = control.get("control", "")
        if nombre:
            propuesta.append(
                f"Definir una medida de seguridad para el control faltante: {nombre}."
            )

    return propuesta
