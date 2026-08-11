"""
Contrato único de presentación de resultados de Codificación.

Organiza y traduce para presentación los datos ya calculados por los
agentes y por Python (graph.py / coding_metrics.py). No recalcula nada.

Consumidores: Streamlit (coding_ui.py) y documentos (utils.py).
"""


def construir_presentacion_resultado_codificacion(
    contexto,
    central_result,
    quality_result,
    security_result,
    evaluator_result,
    coding_summary,
    trazabilidad_filas,
):
    mc05_summary = coding_summary["metricas"]["MC-05"]
    ms05_summary = coding_summary["metricas"]["MS-05"]
    ms06_summary = coding_summary["metricas"]["MS-06"]
    ms07_summary = coding_summary["metricas"]["MS-07"]

    quality_raw = quality_result["raw"]
    security_raw = security_result["raw"]

    interpretacion_mc05 = quality_raw.get("interpretacion_mc05", {})
    interpretacion_ms05 = security_raw.get("interpretacion_ms05", {})
    interpretacion_ms06 = security_raw.get("interpretacion_ms06", {})
    interpretacion_ms07 = security_raw.get("interpretacion_ms07", {})

    mc05 = _construir_mc05(mc05_summary, interpretacion_mc05)
    ms05 = _construir_ms05(ms05_summary, interpretacion_ms05)
    ms06 = _construir_ms06(ms06_summary, interpretacion_ms06)
    ms07 = _construir_ms07(ms07_summary, interpretacion_ms07)

    trazabilidad_del_cod = _construir_trazabilidad_del_cod(
        contexto["codificacion_id"], trazabilidad_filas,
    )

    propuesta = construir_propuesta_maximo_codificacion(quality_result, security_result)

    return {
        "codificacion_id": contexto["codificacion_id"],
        "issue_iid": contexto["issue_iid"],
        "titulo": contexto.get("titulo", ""),
        "estado_orientativo": coding_summary["estado_orientativo"],
        "indice_calidad": coding_summary["indice_calidad_codigo"],
        "indice_seguridad": coding_summary["indice_seguridad_codigo"],
        "elementos_diseno_declarados": contexto.get("elementos_diseno_declarados", []),
        "archivos_declarados": contexto.get("archivos_declarados", []),
        "lenguaje_detectado": contexto.get("lenguaje_detectado"),
        "metricas": {
            "MC-05": mc05,
            "MS-05": ms05,
            "MS-06": ms06,
            "MS-07": ms07,
        },
        "correcciones_necesarias": coding_summary.get("correcciones_necesarias") or [],
        "precisiones_necesarias": coding_summary.get("precisiones_necesarias") or [],
        "oportunidades_mejora": coding_summary.get("oportunidades_mejora") or [],
        "propuesta_para_maximo": propuesta,
        "trazabilidad": trazabilidad_del_cod,
        "conclusion_calidad": evaluator_result.get("conclusion_calidad", ""),
        "conclusion_seguridad": evaluator_result.get("conclusion_seguridad", ""),
        "contexto_original": {
            "descripcion": contexto.get("descripcion", ""),
            "decisiones": contexto.get("decisiones", []),
            "observaciones": contexto.get("observaciones", []),
            "elementos_diseno_contextualizados": contexto.get("elementos_diseno_contextualizados", []),
        },
        "central_result": {
            "elementos_implementados": central_result.get("elementos_implementados", []),
            "elementos_no_confirmados": central_result.get("elementos_no_confirmados", []),
            "archivos_consolidados": central_result.get("archivos_consolidados", []),
            "coherencia_declarado_vs_evidencia": central_result.get("coherencia_declarado_vs_evidencia", {}),
            "inconsistencias_detectadas": central_result.get("inconsistencias_detectadas", []),
        },
    }


def _construir_mc05(mc05_summary, interpretacion_mc05):
    n = mc05_summary.get("numerador")
    d = mc05_summary.get("denominador")

    return {
        "codigo": "MC-05",
        "nombre": "Adecuación de la Complejidad Ciclomática",
        "valor": mc05_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": mc05_summary.get("estado_calculo"),
        "que_mide": (
            "Evalúa si las funciones del código implementado tienen una "
            "complejidad ciclomática aceptable (Radon), como indicador de "
            "mantenibilidad."
        ),
        "funciones_criticas": interpretacion_mc05.get("funciones_criticas", []),
        "conclusion": interpretacion_mc05.get("conclusion", ""),
        "resultado": (
            f"{n} de {d} funciones analizadas tienen una complejidad ciclomática aceptable."
            if d else "No se evaluaron funciones (Radon no aplicable o en error)."
        ),
    }


def _construir_ms05(ms05_summary, interpretacion_ms05):
    return {
        "codigo": "MS-05",
        "nombre": "Vulnerabilidades Críticas Detectadas",
        "valor": ms05_summary.get("valor"),
        "numero_criticas": ms05_summary.get("numero_criticas"),
        "estado_calculo": ms05_summary.get("estado_calculo"),
        "que_mide": (
            "Evalúa la cantidad de vulnerabilidades críticas detectadas por "
            "análisis estático (Semgrep). El resultado deseado es 0."
        ),
        "vulnerabilidades_criticas": interpretacion_ms05.get("vulnerabilidades_criticas", []),
        "conclusion": interpretacion_ms05.get("conclusion_ms05", ""),
    }


def _construir_ms06(ms06_summary, interpretacion_ms06):
    n = ms06_summary.get("numerador")
    d = ms06_summary.get("denominador")

    return {
        "codigo": "MS-06",
        "nombre": "Cobertura de Dependencias Seguras",
        "valor": ms06_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": ms06_summary.get("estado_calculo"),
        "que_mide": (
            "Evalúa la proporción de dependencias declaradas que no "
            "presentan vulnerabilidades conocidas (pip-audit)."
        ),
        "dependencias_inseguras": interpretacion_ms06.get("dependencias_inseguras", []),
        "conclusion": interpretacion_ms06.get("conclusion_ms06", ""),
        "resultado": (
            f"{n} de {d} dependencias analizadas no presentan vulnerabilidades conocidas."
            if d else "No se evaluaron dependencias (pip-audit no aplicable o en error)."
        ),
    }


def _construir_ms07(ms07_summary, interpretacion_ms07):
    n = ms07_summary.get("numerador")
    d = ms07_summary.get("denominador")

    return {
        "codigo": "MS-07",
        "nombre": "Cobertura de Código sin Secretos Expuestos",
        "valor": ms07_summary.get("valor"),
        "numerador": n,
        "denominador": d,
        "estado_calculo": ms07_summary.get("estado_calculo"),
        "que_mide": (
            "Evalúa la proporción de archivos analizados que no contienen "
            "secretos expuestos (Gitleaks)."
        ),
        "archivos_con_secretos": interpretacion_ms07.get("archivos_con_secretos", []),
        "conclusion": interpretacion_ms07.get("conclusion_ms07", ""),
        "resultado": (
            f"{n} de {d} archivos analizados no contienen secretos expuestos."
            if d else "No se evaluaron archivos (Gitleaks no aplicable o en error)."
        ),
    }


def _construir_trazabilidad_del_cod(codificacion_id, filas_matriz):
    implementados = []
    no_confirmados = []
    no_evaluados = []

    for fila in filas_matriz:
        if fila.get("Codificación") != codificacion_id:
            continue
        codigo = fila.get("Código requisito", "")
        estado = fila.get("Estado de implementación", "")
        if "Implementado" in estado:
            implementados.append(codigo)
        elif "sin confirmar" in estado:
            no_confirmados.append(codigo)
        elif "No evaluado" in estado:
            no_evaluados.append(codigo)

    return {
        "implementados": implementados,
        "no_confirmados": no_confirmados,
        "no_evaluados": no_evaluados,
    }


def construir_propuesta_maximo_codificacion(quality_result, security_result):
    propuesta = []
    quality_raw = quality_result["raw"]
    security_raw = security_result["raw"]

    for funcion in quality_raw.get("interpretacion_mc05", {}).get("funciones_criticas", []):
        if not isinstance(funcion, dict):
            continue
        nombre = funcion.get("nombre", "")
        recomendacion = funcion.get("recomendacion", "")
        if nombre:
            propuesta.append(
                f"Refactorizar la función {nombre}: {recomendacion}."
                if recomendacion else f"Refactorizar la función {nombre}."
            )

    for vulnerabilidad in security_raw.get("interpretacion_ms05", {}).get("vulnerabilidades_criticas", []):
        if not isinstance(vulnerabilidad, dict):
            continue
        archivo = vulnerabilidad.get("archivo", "")
        regla = vulnerabilidad.get("regla", "")
        if archivo:
            propuesta.append(
                f"Corregir la vulnerabilidad crítica detectada en {archivo} ({regla})."
                if regla else f"Corregir la vulnerabilidad crítica detectada en {archivo}."
            )

    for dependencia in security_raw.get("interpretacion_ms06", {}).get("dependencias_inseguras", []):
        if not isinstance(dependencia, dict):
            continue
        nombre = dependencia.get("nombre", "")
        if nombre:
            propuesta.append(f"Actualizar la dependencia insegura: {nombre}.")

    for archivo_secreto in security_raw.get("interpretacion_ms07", {}).get("archivos_con_secretos", []):
        if not isinstance(archivo_secreto, dict):
            continue
        archivo = archivo_secreto.get("archivo", "")
        if archivo:
            propuesta.append(f"Eliminar y rotar el secreto expuesto en {archivo}.")

    return propuesta
