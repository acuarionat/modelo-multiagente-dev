import re

CAMPOS_OBLIGATORIOS_DISENO = {
    "issue_iid",
    "diseno_id",
    "titulo",
    "requerimientos_relacionados",
    "descripcion_general",
    "elementos_diseno",
}


def _texto_presente(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validar_entrada_diseno(issue: dict) -> dict:
    """Clasifica la entrada de un Issue DIS-xxx según reglas determinísticas."""
    campos_faltantes = []
    advertencias = []

    if not issue.get("issue_iid"):
        campos_faltantes.append("issue_iid")
    if not _texto_presente(issue.get("diseno_id")):
        campos_faltantes.append("diseno_id")
    if not _texto_presente(issue.get("titulo")):
        campos_faltantes.append("titulo")
    if not issue.get("requerimientos_relacionados"):
        campos_faltantes.append("requerimientos_relacionados")
    if not _texto_presente(issue.get("descripcion_general")):
        campos_faltantes.append("descripcion_general")

    elementos = issue.get("elementos_diseno") or []
    if not elementos:
        campos_faltantes.append("elementos_diseno")
    else:
        if any(not _texto_presente(elemento.get("elemento_id")) for elemento in elementos):
            campos_faltantes.append("elementos_diseno.elemento_id")
        if any(not _texto_presente(elemento.get("nombre")) for elemento in elementos):
            campos_faltantes.append("elementos_diseno.nombre")
        if any(not _texto_presente(elemento.get("responsabilidad")) for elemento in elementos):
            campos_faltantes.append("elementos_diseno.responsabilidad")

    ids_elementos = {
        elemento.get("elemento_id")
        for elemento in elementos
        if _texto_presente(elemento.get("elemento_id"))
    }
    relaciones = issue.get("relaciones") or []
    if not relaciones:
        # La ausencia de relaciones no es información insuficiente: solo implica
        # que MC-04 (acoplamiento) será no evaluable más adelante.
        advertencias.append("No se documentaron relaciones entre elementos.")
    else:
        for relacion in relaciones:
            origen = relacion.get("origen")
            destino = relacion.get("destino")
            if origen not in ids_elementos or destino not in ids_elementos:
                advertencias.append(
                    f"La relación {origen} → {destino} referencia un elemento de diseño no declarado."
                )

    if campos_faltantes:
        estado = "informacion_insuficiente"
    elif advertencias:
        estado = "entrada_con_advertencias"
    else:
        estado = "entrada_valida"

    return {
        "estado": estado,
        "campos_faltantes": campos_faltantes,
        "advertencias": advertencias,
    }


def validar_salida_central_diseno(
    result: dict,
    expected_issue_ids: list,
    valid_requirement_codes: set,
    valid_element_ids: set,
) -> dict:
    """Verifica que el Central de Diseño no haya inventado ni descuadrado códigos."""
    errores = []

    issue_iid = result.get("issue_iid")
    if issue_iid not in expected_issue_ids:
        errores.append(f"issue_iid inesperado: {issue_iid!r}.")

    if not _texto_presente(result.get("diseno_id")):
        errores.append("diseno_id no fue conservado en la salida.")

    trazabilidad = result.get("trazabilidad_diseno") or []
    sin_relacion = result.get("requisitos_sin_relacion_evidente") or []

    related = []
    for item in trazabilidad:
        requisito = item.get("requisito")
        if requisito in related:
            errores.append(f"Requisito duplicado en trazabilidad_diseno: {requisito!r}.")
        related.append(requisito)
        if requisito not in valid_requirement_codes:
            errores.append(f"Requisito inventado en trazabilidad_diseno: {requisito!r}.")
        for elemento_id in item.get("elementos_relacionados") or []:
            if elemento_id not in valid_element_ids:
                errores.append(
                    f"Elemento de diseño inventado: {elemento_id!r} (requisito {requisito!r})."
                )

    unrelated = []
    for item in sin_relacion:
        requisito = item.get("requisito")
        if requisito in unrelated:
            errores.append(f"Requisito duplicado en requisitos_sin_relacion_evidente: {requisito!r}.")
        unrelated.append(requisito)
        if requisito not in valid_requirement_codes:
            errores.append(f"Requisito inventado en requisitos_sin_relacion_evidente: {requisito!r}.")

    related_set = set(related)
    unrelated_set = set(unrelated)

    interseccion = related_set & unrelated_set
    if interseccion:
        errores.append(f"Requisitos clasificados en ambos grupos a la vez: {sorted(interseccion)}.")

    expected_requirements = set(valid_requirement_codes)
    clasificados = related_set | unrelated_set
    faltantes = expected_requirements - clasificados
    if faltantes:
        errores.append(f"Requisitos válidos sin clasificar: {sorted(faltantes)}.")

    return {
        "valido": not errores,
        "errores": errores,
    }


ESTADOS_ACOPLAMIENTO_VALIDOS = {"aceptable", "no_aceptable", "no_evaluable"}


def validar_salida_calidad_diseno(metricas: dict, valid_element_ids: set) -> dict:
    """Verifica MC-03 y MC-04 del Agente de Calidad de Diseño contra el Issue real."""
    errores = []

    mc03 = metricas.get("completitud_descripcion") or {}
    documentados = mc03.get("elementos_documentados") or []
    faltantes = mc03.get("elementos_necesarios_faltantes") or []

    documentados_ids = set()
    for item in documentados:
        elemento_id = item.get("elemento_id")
        if elemento_id not in valid_element_ids:
            errores.append(f"MC-03: elementos_documentados referencia un elemento_id inexistente: {elemento_id!r}.")
        documentados_ids.add(elemento_id)

    for item in faltantes:
        elemento = item.get("elemento")
        if elemento in valid_element_ids:
            errores.append(
                f"MC-03: elementos_necesarios_faltantes reutiliza un elemento_id ya existente: {elemento!r}."
            )
        if elemento in documentados_ids:
            errores.append(
                f"MC-03: el elemento {elemento!r} aparece simultáneamente como documentado y como faltante."
            )
        confianza = str(item.get("confianza", "")).casefold()
        if confianza not in {"alta", "media", "baja"}:
            errores.append(f"MC-03: confianza inválida en elementos_necesarios_faltantes: {item.get('confianza')!r}.")

    mc04 = metricas.get("acoplamiento_componentes") or {}
    for item in mc04.get("componentes_evaluados") or []:
        elemento_id = item.get("elemento_id")
        if elemento_id not in valid_element_ids:
            errores.append(f"MC-04: componentes_evaluados referencia un elemento_id inexistente: {elemento_id!r}.")

        estado = item.get("estado_acoplamiento")
        if estado not in ESTADOS_ACOPLAMIENTO_VALIDOS:
            errores.append(f"MC-04: estado_acoplamiento inválido para {elemento_id!r}: {estado!r}.")

        for dependencia in item.get("dependencias_consideradas") or []:
            if dependencia not in valid_element_ids:
                errores.append(
                    f"MC-04: dependencias_consideradas de {elemento_id!r} referencia un elemento_id inexistente: {dependencia!r}."
                )

    return {
        "valido": not errores,
        "errores": errores,
    }


CONFIANZAS_VALIDAS = {"alta", "media", "baja"}


def normalizar_elementos_responsables(control: dict) -> list:
    """Normaliza elemento_responsable (string legacy) o elementos_responsables (lista canónica)."""
    responsables = control.get("elementos_responsables")

    if isinstance(responsables, list):
        return [
            str(item).strip()
            for item in responsables
            if str(item).strip()
        ]

    legacy = control.get("elemento_responsable")

    if not legacy:
        return []

    if isinstance(legacy, list):
        return [
            str(item).strip()
            for item in legacy
            if str(item).strip()
        ]

    return [
        item.strip()
        for item in str(legacy).split(",")
        if item.strip()
    ]


def validar_salida_seguridad_diseno(
    resultado: dict,
    expected_issue_id: int,
    expected_diseno_id: str,
    valid_element_ids: set,
) -> dict:
    """Verifica MS-03 y MS-04 del Agente de Seguridad de Diseño contra el Issue real."""
    errores = []

    if resultado.get("issue_iid") != expected_issue_id:
        errores.append(f"issue_iid inesperado: {resultado.get('issue_iid')!r}.")
    if resultado.get("diseno_id") != expected_diseno_id:
        errores.append(f"diseno_id inesperado: {resultado.get('diseno_id')!r}.")

    # ---------------- MS-03 — Cobertura de Amenazas ----------------

    ms03 = resultado.get("cobertura_amenazas") or {}
    amenazas_identificadas = ms03.get("amenazas_identificadas") or []
    con_tratamiento = ms03.get("amenazas_con_tratamiento") or []
    sin_tratamiento = ms03.get("amenazas_sin_tratamiento") or []

    identidades = set()
    for item in amenazas_identificadas:
        identidades.add(item.get("identidad"))
        for elemento_id in item.get("elementos_afectados") or []:
            if elemento_id not in valid_element_ids:
                errores.append(f"MS-03: elemento_afectado inexistente: {elemento_id!r}.")

    con_set = set(con_tratamiento)
    sin_set = set(sin_tratamiento)

    interseccion_amenazas = con_set & sin_set
    if interseccion_amenazas:
        errores.append(f"MS-03: amenazas clasificadas en ambos grupos a la vez: {sorted(interseccion_amenazas)}.")

    clasificadas_amenazas = con_set | sin_set
    amenazas_sin_clasificar = identidades - clasificadas_amenazas
    if amenazas_sin_clasificar:
        errores.append(f"MS-03: amenazas identificadas sin clasificar en con/sin tratamiento: {sorted(amenazas_sin_clasificar)}.")

    amenazas_clasificadas_invalidas = clasificadas_amenazas - identidades
    if amenazas_clasificadas_invalidas:
        errores.append(f"MS-03: amenazas clasificadas que no aparecen en amenazas_identificadas: {sorted(amenazas_clasificadas_invalidas)}.")

    for item in ms03.get("amenazas_necesarias_faltantes") or []:
        confianza = str(item.get("confianza", "")).casefold()
        if confianza not in CONFIANZAS_VALIDAS:
            errores.append(f"MS-03: confianza inválida en amenazas_necesarias_faltantes: {item.get('confianza')!r}.")

    # ---------------- MS-04 — Cobertura de Controles ----------------

    ms04 = resultado.get("cobertura_controles") or {}
    controles_aplicables = ms04.get("controles_aplicables") or []
    controles_definidos = ms04.get("controles_definidos") or []
    controles_faltantes = ms04.get("controles_faltantes") or []

    nombres_aplicables = set()
    for item in controles_aplicables:
        nombres_aplicables.add(item.get("control"))
        confianza = str(item.get("confianza", "")).casefold()
        if confianza not in CONFIANZAS_VALIDAS:
            errores.append(f"MS-04: confianza inválida en controles_aplicables: {item.get('confianza')!r}.")

    nombres_definidos = []
    for item in controles_definidos:
        control = item.get("control")
        if control not in nombres_aplicables:
            errores.append(f"MS-04: control_definido fuera del universo de controles_aplicables: {control!r}.")
        if control in nombres_definidos:
            errores.append(f"MS-04: control duplicado en controles_definidos: {control!r}.")
        nombres_definidos.append(control)
        responsables = item.get("elementos_responsables", [])
        if not isinstance(responsables, list):
            errores.append(
                f"MS-04: elementos_responsables debe ser una lista."
            )
        else:
            for responsable in responsables:
                if responsable not in valid_element_ids:
                    errores.append(
                        f"MS-04: elemento responsable inexistente: {responsable!r}."
                    )

    nombres_faltantes = []
    for item in controles_faltantes:
        control = item.get("control")
        if control not in nombres_aplicables:
            errores.append(f"MS-04: control_faltante fuera del universo de controles_aplicables: {control!r}.")
        if control in nombres_faltantes:
            errores.append(f"MS-04: control duplicado en controles_faltantes: {control!r}.")
        nombres_faltantes.append(control)
        confianza = str(item.get("confianza", "")).casefold()
        if confianza not in CONFIANZAS_VALIDAS:
            errores.append(f"MS-04: confianza inválida en controles_faltantes: {item.get('confianza')!r}.")

    definidos_set = set(nombres_definidos)
    faltantes_set = set(nombres_faltantes)

    interseccion_controles = definidos_set & faltantes_set
    if interseccion_controles:
        errores.append(f"MS-04: controles clasificados en ambos grupos a la vez: {sorted(interseccion_controles)}.")

    clasificados_controles = definidos_set | faltantes_set
    aplicables_sin_clasificar = nombres_aplicables - clasificados_controles
    if aplicables_sin_clasificar:
        errores.append(f"MS-04: controles aplicables sin clasificar: {sorted(aplicables_sin_clasificar)}.")

    return {
        "valido": not errores,
        "errores": errores,
    }


_PATRON_ELEMENTO_DISENO = re.compile(r"\bED-\d+\b")
_PATRON_REQUISITO = re.compile(r"\bRN?F-\d+\b")

CAMPOS_METRICA_PROHIBIDOS_EN_EVALUADOR = {"valor", "porcentaje", "numerador", "denominador"}
CAMPOS_LISTA_EVALUADOR_DISENO = (
    "correcciones_necesarias", "precisiones_necesarias",
    "oportunidades_mejora", "hallazgos_prioritarios",
)


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


def validar_salida_evaluador_diseno(
    resultado: dict,
    expected_issue_id: int,
    expected_diseno_id: str,
    valid_element_ids: set,
    valid_requirement_codes: set,
) -> dict:
    """Verifica la salida del Agente Evaluador de Diseño contra el Issue real."""
    errores = []

    if resultado.get("issue_iid") != expected_issue_id:
        errores.append(f"issue_iid inesperado: {resultado.get('issue_iid')!r}.")
    if resultado.get("diseno_id") != expected_diseno_id:
        errores.append(f"diseno_id inesperado: {resultado.get('diseno_id')!r}.")

    campos_porcentaje_presentes = CAMPOS_METRICA_PROHIBIDOS_EN_EVALUADOR & set(resultado.keys())
    if campos_porcentaje_presentes:
        errores.append(
            f"El Evaluador no debe devolver campos de porcentaje recalculado: {sorted(campos_porcentaje_presentes)}."
        )

    for campo in CAMPOS_LISTA_EVALUADOR_DISENO:
        if not isinstance(resultado.get(campo), list):
            errores.append(f"{campo} debe ser una lista para diferenciarse de los demás hallazgos.")

    textos = _recolectar_textos_evaluador(resultado)
    ed_mencionados = set()
    requisitos_mencionados = set()
    for texto in textos:
        ed_mencionados.update(_PATRON_ELEMENTO_DISENO.findall(texto))
        requisitos_mencionados.update(_PATRON_REQUISITO.findall(texto))

    ed_inventados = ed_mencionados - valid_element_ids
    if ed_inventados:
        errores.append(f"El Evaluador menciona elementos ED inexistentes: {sorted(ed_inventados)}.")

    requisitos_inventados = requisitos_mencionados - valid_requirement_codes
    if requisitos_inventados:
        errores.append(f"El Evaluador menciona requisitos inexistentes: {sorted(requisitos_inventados)}.")

    return {
        "valido": not errores,
        "errores": errores,
    }
