def calcular_mc03(elementos_documentados: list, elementos_necesarios_faltantes: list) -> dict:
    """MC-03 Completitud de la Descripción, a partir de la salida estructurada del Agente de Calidad de Diseño."""
    documentados = [x for x in elementos_documentados if isinstance(x, dict)]
    faltantes_validos = [
        x for x in elementos_necesarios_faltantes
        if isinstance(x, dict) and str(x.get("confianza", "")).casefold() == "alta"
    ]

    esperados = len(documentados) + len(faltantes_validos)
    valor = len(documentados) / esperados if esperados > 0 else None

    return {
        "codigo": "MC-03",
        "valor": valor,
        "documentados": len(documentados),
        "faltantes_validos": len(faltantes_validos),
        "esperados": esperados,
    }


def calcular_mc04(componentes_evaluados: list) -> dict:
    """MC-04 Acoplamiento de Componentes, a partir de la salida estructurada del Agente de Calidad de Diseño."""
    componentes = [c for c in componentes_evaluados if isinstance(c, dict)]

    evaluables = [
        c for c in componentes
        if c.get("estado_acoplamiento") in {"aceptable", "no_aceptable"}
    ]
    aceptables = [c for c in evaluables if c.get("estado_acoplamiento") == "aceptable"]
    no_aceptables = [c for c in evaluables if c.get("estado_acoplamiento") == "no_aceptable"]
    no_evaluables = [c for c in componentes if c.get("estado_acoplamiento") == "no_evaluable"]

    valor = len(aceptables) / len(evaluables) if evaluables else None

    return {
        "codigo": "MC-04",
        "valor": valor,
        "evaluables": len(evaluables),
        "aceptables": len(aceptables),
        "no_aceptables": len(no_aceptables),
        "no_evaluables": len(no_evaluables),
    }


def calcular_ms03(resultado_seguridad: dict) -> dict:
    """MS-03 Cobertura de Amenazas con Tratamiento Definido, a partir de la salida estructurada del Agente de Seguridad de Diseño."""
    amenazas_originales = resultado_seguridad.get("amenazas_identificadas") or []
    faltantes_alta = [
        x for x in (resultado_seguridad.get("amenazas_necesarias_faltantes") or [])
        if isinstance(x, dict) and str(x.get("confianza", "")).casefold() == "alta"
    ]

    total_amenazas = len(amenazas_originales) + len(faltantes_alta)
    tratadas = len(resultado_seguridad.get("amenazas_con_tratamiento") or [])

    valor = tratadas / total_amenazas if total_amenazas > 0 else None

    return {
        "codigo": "MS-03",
        "valor": valor,
        "numerador": tratadas,
        "denominador": total_amenazas,
        "estado_calculo": "calculada" if total_amenazas > 0 else "no_aplicable",
    }


def calcular_ms04(resultado_seguridad: dict) -> dict:
    """MS-04 Cobertura de Controles de Seguridad Definidos, a partir de la salida estructurada del Agente de Seguridad de Diseño."""
    aplicables = [
        c for c in (resultado_seguridad.get("controles_aplicables") or [])
        if isinstance(c, dict) and str(c.get("confianza", "")).casefold() == "alta"
    ]
    definidos = resultado_seguridad.get("controles_definidos") or []

    valor = len(definidos) / len(aplicables) if aplicables else None

    return {
        "codigo": "MS-04",
        "valor": valor,
        "numerador": len(definidos),
        "denominador": len(aplicables),
        "estado_calculo": "calculada" if aplicables else "no_aplicable",
    }


def calcular_indice_calidad_diseno(mc03, mc04):
    """Índice de Calidad de Diseño: promedio de MC-03 y MC-04. Una métrica no_evaluable (None) no se convierte en 0."""
    valores = [
        valor
        for valor in (mc03, mc04)
        if valor is not None
    ]

    if not valores:
        return None

    return sum(valores) / len(valores)


def calcular_indice_seguridad_diseno(ms03, ms04):
    """Índice de Seguridad de Diseño: promedio de MS-03 y MS-04. Una métrica no_evaluable (None) no se convierte en 0."""
    valores = [
        valor
        for valor in (ms03, ms04)
        if valor is not None
    ]

    if not valores:
        return None

    return sum(valores) / len(valores)


def determinar_estado_diseno(
    *,
    correcciones_necesarias: list,
    precisiones_necesarias: list,
    oportunidades_mejora: list,
    error_tecnico: bool = False,
):
    """Estado orientativo determinístico: el Evaluador solo entrega categorías, Python decide el estado oficial."""
    if error_tecnico:
        return "ERROR"

    if correcciones_necesarias:
        return "CORREGIR"

    if precisiones_necesarias or oportunidades_mejora:
        return "CONFORME CON MEJORAS"

    return "CONFORME"
