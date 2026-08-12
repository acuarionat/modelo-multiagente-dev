"""
Validadores de salida de los agentes de Pruebas (Central, Calidad,
Seguridad, Evaluador). Verifican que el agente respetó el contrato
"interpreta, no recalcula": ningún agente puede devolver campos de
métrica (valor/porcentaje/numerador/denominador/umbral/cumple) ni
inventar COD-xxx que no formen parte del contexto real recibido.

La validación de entrada de un Issue PRU-xxx (antes de cualquier agente)
vive en core/testing_validation.py, no aquí.
"""

import re

_PATRON_CODIFICACION = re.compile(r"\bCOD-\d+\b")
CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION = {"valor", "porcentaje", "numerador", "denominador", "cumple", "umbral"}
CAMPOS_LISTA_EVALUADOR_PRUEBAS = (
    "correcciones_necesarias", "precisiones_necesarias",
    "oportunidades_mejora", "hallazgos_prioritarios",
)


def _texto_presente(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validar_salida_central_pruebas(
    result: dict,
    expected_issue_ids: list,
    valid_codificaciones: set,
) -> dict:
    """Verifica que el Central de Pruebas no haya inventado COD ni descuadrado códigos."""
    errores = []

    issue_iid = result.get("issue_iid")
    if issue_iid not in expected_issue_ids:
        errores.append(f"issue_iid inesperado: {issue_iid!r}.")

    if not _texto_presente(result.get("prueba_id")):
        errores.append("prueba_id no fue conservado en la salida.")

    coherencia = result.get("coherencia_declarado_vs_evidencia") or {}
    if coherencia.get("estado") not in {"coherente", "incoherente", "parcialmente_coherente"}:
        errores.append(f"coherencia_declarado_vs_evidencia.estado inválido: {coherencia.get('estado')!r}.")

    if not isinstance(result.get("inconsistencias_detectadas"), list):
        errores.append("inconsistencias_detectadas debe ser una lista.")

    trazabilidad_confirmada = result.get("trazabilidad_confirmada") or {}
    if not isinstance(trazabilidad_confirmada, dict):
        errores.append("trazabilidad_confirmada debe ser un objeto.")
    else:
        for codificacion_id in trazabilidad_confirmada:
            if codificacion_id not in valid_codificaciones:
                errores.append(f"trazabilidad_confirmada referencia una Codificación inexistente: {codificacion_id!r}.")

    return {
        "valido": not errores,
        "errores": errores,
    }


def validar_salida_calidad_pruebas(resultado: dict) -> dict:
    """Verifica que Calidad de Pruebas no haya recalculado MC-07 ni MC-08."""
    errores = []

    interpretacion_mc07 = resultado.get("interpretacion_mc07") or {}
    interpretacion_mc08 = resultado.get("interpretacion_mc08") or {}

    for campo_interpretacion, interpretacion in (
        ("interpretacion_mc07", interpretacion_mc07),
        ("interpretacion_mc08", interpretacion_mc08),
    ):
        campos_prohibidos = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(interpretacion.keys())
        if campos_prohibidos:
            errores.append(f"{campo_interpretacion} no debe devolver campos de métrica recalculada: {sorted(campos_prohibidos)}.")

    if not isinstance(interpretacion_mc07.get("funcionalidades_con_brecha"), list):
        errores.append("interpretacion_mc07.funcionalidades_con_brecha debe ser una lista.")
    if not _texto_presente(interpretacion_mc07.get("conclusion")):
        errores.append("interpretacion_mc07.conclusion no puede estar vacía.")

    if not isinstance(interpretacion_mc08.get("fallos_pendientes"), list):
        errores.append("interpretacion_mc08.fallos_pendientes debe ser una lista.")
    if not _texto_presente(interpretacion_mc08.get("conclusion")):
        errores.append("interpretacion_mc08.conclusion no puede estar vacía.")

    for campo in ("precisiones_necesarias", "oportunidades_adicionales"):
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista.")

    return {
        "valido": not errores,
        "errores": errores,
    }


def validar_salida_seguridad_pruebas(resultado: dict) -> dict:
    """Verifica que Seguridad de Pruebas no haya recalculado MS-08 ni MS-09."""
    errores = []

    interpretacion_ms08 = resultado.get("interpretacion_ms08") or {}
    interpretacion_ms09 = resultado.get("interpretacion_ms09") or {}

    for campo_interpretacion, interpretacion in (
        ("interpretacion_ms08", interpretacion_ms08),
        ("interpretacion_ms09", interpretacion_ms09),
    ):
        campos_prohibidos = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(interpretacion.keys())
        if campos_prohibidos:
            errores.append(f"{campo_interpretacion} no debe devolver campos de métrica recalculada: {sorted(campos_prohibidos)}.")

    if not isinstance(interpretacion_ms08.get("controles_no_verificados"), list):
        errores.append("interpretacion_ms08.controles_no_verificados debe ser una lista.")
    if not _texto_presente(interpretacion_ms08.get("conclusion_ms08")):
        errores.append("interpretacion_ms08.conclusion_ms08 no puede estar vacía.")

    if not isinstance(interpretacion_ms09.get("pruebas_fallidas"), list):
        errores.append("interpretacion_ms09.pruebas_fallidas debe ser una lista.")
    if not _texto_presente(interpretacion_ms09.get("conclusion_ms09")):
        errores.append("interpretacion_ms09.conclusion_ms09 no puede estar vacía.")

    for campo in ("precisiones_necesarias", "oportunidades_adicionales"):
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista.")

    return {
        "valido": not errores,
        "errores": errores,
    }


def _recolectar_textos_evaluador(value) -> list:
    textos = []
    if isinstance(value, str):
        textos.append(value)
    elif isinstance(value, dict):
        for sub_value in value.values():
            textos.extend(_recolectar_textos_evaluador(sub_value))
    elif isinstance(value, list):
        for sub_value in value:
            textos.extend(_recolectar_textos_evaluador(sub_value))
    return textos


def validar_salida_evaluador_pruebas(
    resultado: dict,
    expected_issue_id: int,
    expected_prueba_id: str,
    valid_codificaciones: set,
) -> dict:
    """Verifica la salida del Agente Evaluador de Pruebas contra el PRU real."""
    errores = []

    if resultado.get("issue_iid") != expected_issue_id:
        errores.append(f"issue_iid inesperado: {resultado.get('issue_iid')!r}.")
    if resultado.get("prueba_id") != expected_prueba_id:
        errores.append(f"prueba_id inesperado: {resultado.get('prueba_id')!r}.")

    campos_porcentaje_presentes = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(resultado.keys())
    if campos_porcentaje_presentes:
        errores.append(f"El Evaluador no debe devolver campos de métrica recalculada: {sorted(campos_porcentaje_presentes)}.")

    for campo in CAMPOS_LISTA_EVALUADOR_PRUEBAS:
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista para diferenciarse de los demás hallazgos.")

    textos = _recolectar_textos_evaluador(resultado)
    cod_mencionados = set()
    for texto in textos:
        cod_mencionados.update(_PATRON_CODIFICACION.findall(texto))

    cod_inventados = cod_mencionados - valid_codificaciones
    if cod_inventados:
        errores.append(f"El Evaluador menciona otras Codificaciones que no le corresponden: {sorted(cod_inventados)}.")

    return {
        "valido": not errores,
        "errores": errores,
    }
