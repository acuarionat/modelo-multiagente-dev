import re

_PATRON_ELEMENTO_DISENO = re.compile(r"\bED-\d+\b")
_PATRON_CODIFICACION = re.compile(r"\bCOD-\d+\b")

CONFIANZAS_VALIDAS = {"alta", "media", "baja"}
CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION = {"valor", "porcentaje", "numerador", "denominador", "numero_criticas"}
CAMPOS_LISTA_EVALUADOR_CODIFICACION = (
    "correcciones_necesarias", "precisiones_necesarias",
    "oportunidades_mejora", "hallazgos_prioritarios",
)


def _texto_presente(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validar_entrada_codificacion(issue: dict, elementos_diseno_validos: set) -> dict:
    """
    Clasifica la entrada de un Issue COD-xxx según reglas determinísticas,
    ANTES de ejecutar cualquier herramienta de análisis o agente LLM.

    elementos_diseno_validos es el universo de ED-xx que existen en la
    matriz de Diseño heredada (ya confirmada). Si el Issue declara un ED
    que no existe ahí, la entrada queda inválida y el COD no continúa.
    """
    campos_faltantes = []
    referencias_invalidas = []

    if not issue.get("issue_iid"):
        campos_faltantes.append("issue_iid")
    if not _texto_presente(issue.get("codificacion_id")):
        campos_faltantes.append("codificacion_id")
    if not _texto_presente(issue.get("titulo")):
        campos_faltantes.append("titulo")
    if not _texto_presente(issue.get("descripcion")):
        campos_faltantes.append("descripcion")

    elementos_declarados = issue.get("elementos_diseno_declarados") or []
    if not elementos_declarados:
        campos_faltantes.append("elementos_diseno_declarados")
    else:
        for elemento_id in elementos_declarados:
            if elemento_id not in elementos_diseno_validos:
                referencias_invalidas.append(elemento_id)

    archivos_declarados = issue.get("archivos_declarados") or []
    if not archivos_declarados:
        campos_faltantes.append("archivos_declarados")
    else:
        for archivo in archivos_declarados:
            if not _texto_presente(archivo.get("ruta")):
                campos_faltantes.append("archivos_declarados.ruta")
                break

    if campos_faltantes:
        estado = "informacion_insuficiente"
    elif referencias_invalidas:
        estado = "referencias_invalidas"
    else:
        estado = "entrada_valida"

    return {
        "estado": estado,
        "entrada_valida": estado == "entrada_valida",
        "campos_faltantes": campos_faltantes,
        "referencias_invalidas": referencias_invalidas,
    }


def validar_salida_central_codificacion(
    result: dict,
    expected_issue_ids: list,
    valid_element_ids: set,
    valid_archivos: set,
) -> dict:
    """Verifica que el Central de Codificación no haya inventado ED, archivos ni descuadrado códigos."""
    errores = []

    issue_iid = result.get("issue_iid")
    if issue_iid not in expected_issue_ids:
        errores.append(f"issue_iid inesperado: {issue_iid!r}.")

    if not _texto_presente(result.get("codificacion_id")):
        errores.append("codificacion_id no fue conservado en la salida.")

    implementados = result.get("elementos_implementados") or []
    no_confirmados = result.get("elementos_no_confirmados") or []

    for elemento_id in implementados:
        if elemento_id not in valid_element_ids:
            errores.append(f"Elemento de diseño inventado en elementos_implementados: {elemento_id!r}.")
    for elemento_id in no_confirmados:
        if elemento_id not in valid_element_ids:
            errores.append(f"Elemento de diseño inventado en elementos_no_confirmados: {elemento_id!r}.")

    implementados_set = set(implementados)
    no_confirmados_set = set(no_confirmados)
    interseccion = implementados_set & no_confirmados_set
    if interseccion:
        errores.append(f"Elementos clasificados en ambos grupos a la vez: {sorted(interseccion)}.")

    for archivo in result.get("archivos_consolidados") or []:
        ruta = archivo.get("ruta")
        if ruta not in valid_archivos:
            errores.append(f"archivos_consolidados referencia una ruta no localizada: {ruta!r}.")
        for elemento_id in archivo.get("elementos_diseno_implementados") or []:
            if elemento_id not in valid_element_ids:
                errores.append(f"archivos_consolidados referencia un elemento_id inexistente: {elemento_id!r}.")

    coherencia = result.get("coherencia_declarado_vs_evidencia") or {}
    if coherencia.get("estado") not in {"coherente", "incoherente", "parcialmente_coherente"}:
        errores.append(f"coherencia_declarado_vs_evidencia.estado inválido: {coherencia.get('estado')!r}.")

    for relacion in result.get("trazabilidad_heredada") or []:
        elemento_id = relacion.get("elemento_diseno")
        if elemento_id not in valid_element_ids:
            errores.append(f"trazabilidad_heredada referencia un elemento_id inexistente: {elemento_id!r}.")

    return {
        "valido": not errores,
        "errores": errores,
    }


def validar_salida_calidad_codificacion(resultado: dict) -> dict:
    """Verifica que Calidad de Codificación no haya recalculado MC-05."""
    errores = []

    interpretacion = resultado.get("interpretacion_mc05") or {}
    campos_prohibidos = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(interpretacion.keys())
    if campos_prohibidos:
        errores.append(f"Calidad no debe devolver campos de métrica recalculada: {sorted(campos_prohibidos)}.")

    if not isinstance(interpretacion.get("funciones_criticas"), list):
        errores.append("interpretacion_mc05.funciones_criticas debe ser una lista.")
    if not _texto_presente(interpretacion.get("conclusion")):
        errores.append("interpretacion_mc05.conclusion no puede estar vacía.")

    for campo in ("precisiones_necesarias", "oportunidades_adicionales"):
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista.")

    return {
        "valido": not errores,
        "errores": errores,
    }


def validar_salida_seguridad_codificacion(resultado: dict) -> dict:
    """Verifica que Seguridad de Codificación no haya recalculado MS-05/MS-06/MS-07."""
    errores = []

    for campo_interpretacion in ("interpretacion_ms05", "interpretacion_ms06", "interpretacion_ms07"):
        bloque = resultado.get(campo_interpretacion) or {}
        campos_prohibidos = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(bloque.keys())
        if campos_prohibidos:
            errores.append(
                f"{campo_interpretacion} no debe devolver campos de métrica recalculada: {sorted(campos_prohibidos)}."
            )

    interpretacion_ms05 = resultado.get("interpretacion_ms05") or {}
    if not isinstance(interpretacion_ms05.get("vulnerabilidades_criticas"), list):
        errores.append("interpretacion_ms05.vulnerabilidades_criticas debe ser una lista.")

    interpretacion_ms06 = resultado.get("interpretacion_ms06") or {}
    if not isinstance(interpretacion_ms06.get("dependencias_inseguras"), list):
        errores.append("interpretacion_ms06.dependencias_inseguras debe ser una lista.")

    interpretacion_ms07 = resultado.get("interpretacion_ms07") or {}
    if not isinstance(interpretacion_ms07.get("archivos_con_secretos"), list):
        errores.append("interpretacion_ms07.archivos_con_secretos debe ser una lista.")

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


def validar_salida_evaluador_codificacion(
    resultado: dict,
    expected_issue_id: int,
    expected_codificacion_id: str,
    valid_element_ids: set,
) -> dict:
    """Verifica la salida del Agente Evaluador de Codificación contra el COD real."""
    errores = []

    if resultado.get("issue_iid") != expected_issue_id:
        errores.append(f"issue_iid inesperado: {resultado.get('issue_iid')!r}.")
    if resultado.get("codificacion_id") != expected_codificacion_id:
        errores.append(f"codificacion_id inesperado: {resultado.get('codificacion_id')!r}.")

    campos_porcentaje_presentes = CAMPOS_METRICA_PROHIBIDOS_EN_INTERPRETACION & set(resultado.keys())
    if campos_porcentaje_presentes:
        errores.append(
            f"El Evaluador no debe devolver campos de métrica recalculada: {sorted(campos_porcentaje_presentes)}."
        )

    for campo in CAMPOS_LISTA_EVALUADOR_CODIFICACION:
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista para diferenciarse de los demás hallazgos.")

    textos = _recolectar_textos_evaluador(resultado)
    ed_mencionados = set()
    cod_mencionados = set()
    for texto in textos:
        ed_mencionados.update(_PATRON_ELEMENTO_DISENO.findall(texto))
        cod_mencionados.update(_PATRON_CODIFICACION.findall(texto))

    ed_inventados = ed_mencionados - valid_element_ids
    if ed_inventados:
        errores.append(f"El Evaluador menciona elementos ED inexistentes: {sorted(ed_inventados)}.")

    cod_inventados = cod_mencionados - {expected_codificacion_id}
    if cod_inventados:
        errores.append(f"El Evaluador menciona otros COD que no le corresponden: {sorted(cod_inventados)}.")

    return {
        "valido": not errores,
        "errores": errores,
    }
