import re

VALORES_DESCONOCIDOS = {
    "", "desconocido", "desconocida", "n/a", "no especificado",
    "sin información", "ninguna", "ninguno",
    "no se identificaron aspectos pendientes",
    "no se detectaron fallos durante las pruebas realizadas",
    "no se adjuntaron evidencias adicionales",
}


_PATRON_ENCABEZADO = re.compile(r"^(#{1,6})\s*(.*)$")


def normalizar_titulo_seccion(texto: str) -> str:
    """
    Normaliza un encabezado Markdown a texto comparable, tolerando la
    numeración real de GitLab ("## 1. Implementación evaluada",
    "## 5.1 Controles de seguridad verificados"): quita los "#" y la
    numeración ("1.", "5.1", etc.), y homogeneiza mayúsculas/minúsculas.
    """
    valor = str(texto or "").strip()
    valor = re.sub(r"^#+\s*", "", valor)
    valor = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", valor)
    return valor.strip().casefold()


def _construir_mapa_secciones(description_text: str) -> dict:
    """
    Recorre la descripción una sola vez y construye un mapa
    {titulo_normalizado: cuerpo}, en lugar de un regex independiente por
    encabezado. Tolera encabezados numerados de cualquier nivel
    ("## 1. ...", "# 3. ...", "## 5.1 ...") y descarta líneas
    separadoras ("---").
    """
    mapa = {}
    titulo_actual = None
    cuerpo_actual = []

    for linea in (description_text or "").splitlines():
        coincidencia = _PATRON_ENCABEZADO.match(linea.strip())
        if coincidencia:
            if titulo_actual is not None:
                mapa[titulo_actual] = "\n".join(cuerpo_actual).strip()
            titulo_actual = normalizar_titulo_seccion(coincidencia.group(2))
            cuerpo_actual = []
            continue
        if titulo_actual is None:
            continue
        if re.fullmatch(r"\s*-{3,}\s*", linea):
            continue
        cuerpo_actual.append(linea)

    if titulo_actual is not None:
        mapa[titulo_actual] = "\n".join(cuerpo_actual).strip()

    return mapa


def _extraer_lista(text: str) -> list:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"-{3,}", line):
            continue
        clean_item = re.sub(r"^(?:[-*+](?:\s+|$)|\d+[.)]\s*)", "", line).strip()
        clean_item = clean_item.strip("*").strip()
        comparable = clean_item.casefold().rstrip(".")
        if not clean_item or comparable in VALORES_DESCONOCIDOS:
            continue
        items.append(clean_item)
    return items


def _es_fila_separadora(celdas: list) -> bool:
    return bool(celdas) and all(re.fullmatch(r":?-{2,}:?", celda) for celda in celdas)


def _parsear_tabla_markdown(text: str) -> list:
    filas_datos = []
    encabezado_visto = False
    for linea in text.splitlines():
        linea = linea.strip()
        if not linea.startswith("|"):
            continue
        celdas = [celda.strip() for celda in linea.strip("|").split("|")]
        if _es_fila_separadora(celdas):
            encabezado_visto = True
            continue
        if not encabezado_visto:
            continue
        filas_datos.append(celdas)
    return filas_datos


def _limpiar_codigo_inline(texto: str) -> str:
    valor = str(texto or "").strip()
    if len(valor) >= 2 and valor.startswith("`") and valor.endswith("`"):
        valor = valor[1:-1].strip()
    return valor


def _texto_es_afirmativo(value: str) -> bool:
    return str(value or "").strip().casefold().rstrip(".") in {"sí", "si"}


def _normalizar_estado_prueba(valor: str) -> str:
    normalizado = str(valor or "").strip().casefold().rstrip(".")
    if normalizado == "aprobada":
        return "APROBADA"
    if normalizado == "fallida":
        return "FALLIDA"
    return ""


COD_REGEX = re.compile(r"\bCOD-\d{3}\b", re.IGNORECASE)


def _extraer_codificaciones(text: str) -> list:
    """Extrae los COD-xxx mencionados en la sección, sin depender de una etiqueta ("Implementaciones evaluadas:")."""
    return sorted({codigo.upper() for codigo in COD_REGEX.findall(text)})


def _limpiar_descripcion(text: str) -> str:
    valor = text.strip()
    return "" if valor.casefold() in VALORES_DESCONOCIDOS else valor


def _extraer_pruebas_funcionales(text: str) -> list:
    resultado = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 6:
            continue
        funcionalidad = celdas[1].strip()
        if not funcionalidad:
            continue
        resultado.append({
            "id": _limpiar_codigo_inline(celdas[0]),
            "funcionalidad": funcionalidad,
            "prueba_realizada": celdas[2].strip(),
            "resultado_esperado": celdas[3].strip(),
            "resultado_obtenido": celdas[4].strip(),
            "estado": _normalizar_estado_prueba(celdas[5]),
        })
    return resultado


def _extraer_fallos(text: str) -> list:
    resultado = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 6:
            continue
        fallo = celdas[1].strip()
        if not fallo:
            continue
        resultado.append({
            "id": _limpiar_codigo_inline(celdas[0]),
            "fallo": fallo,
            "detectado_en": celdas[2].strip(),
            "corregido": _texto_es_afirmativo(celdas[3]),
            "verificado": _texto_es_afirmativo(celdas[4]),
            "resultado_verificacion": celdas[5].strip(),
        })
    return resultado


def _extraer_controles_seguridad(text: str) -> list:
    resultado = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 6:
            continue
        control = celdas[1].strip()
        if not control:
            continue
        resultado.append({
            "id": _limpiar_codigo_inline(celdas[0]),
            "control": control,
            "aplica": _texto_es_afirmativo(celdas[2]),
            "verificado": _texto_es_afirmativo(celdas[3]),
            "forma_verificacion": celdas[4].strip(),
            "resultado": celdas[5].strip(),
        })
    return resultado


def _extraer_pruebas_seguridad(text: str) -> list:
    resultado = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 5:
            continue
        prueba = celdas[1].strip()
        if not prueba:
            continue
        resultado.append({
            "id": _limpiar_codigo_inline(celdas[0]),
            "prueba_realizada": prueba,
            "resultado_esperado": celdas[2].strip(),
            "resultado_obtenido": celdas[3].strip(),
            "estado": _normalizar_estado_prueba(celdas[4]),
        })
    return resultado


def _extraer_evidencias(text: str) -> list:
    resultado = []
    for celdas in _parsear_tabla_markdown(text):
        if len(celdas) < 4:
            continue
        tipo = celdas[2].strip()
        descripcion = celdas[3].strip()
        if not tipo and not descripcion:
            continue
        resultado.append({
            "id": _limpiar_codigo_inline(celdas[0]),
            "prueba_o_fallo_relacionado": celdas[1].strip(),
            "tipo_evidencia": tipo,
            "descripcion": descripcion,
        })
    return resultado


def mapear_issue_pruebas(issue) -> dict:
    """
    Convierte la descripción Markdown de un Issue PRU-xxx (plantilla ya
    vigente en GitLab: Implementación evaluada, Descripción general,
    Pruebas funcionales, Fallos, Verificación de seguridad, Evidencias,
    Aspectos pendientes, Observaciones) en un diccionario estructurado.
    No evalúa, no calcula métricas, no resuelve trazabilidad: eso
    corresponde a core/testing_validation.py, core/testing_traceability.py
    y core/testing_metrics.py.
    """
    description_text = issue.description or ""

    prueba_match = re.search(r"\bPRU\s*[-_ ]\s*(\d+)\b", issue.title, re.IGNORECASE)
    prueba_id = f"PRU-{int(prueba_match.group(1)):03d}" if prueba_match else ""

    mapa_secciones = _construir_mapa_secciones(description_text)

    def _seccion(header: str) -> str:
        return mapa_secciones.get(normalizar_titulo_seccion(header), "")

    seccion_implementacion = _seccion("Implementación evaluada")
    seccion_descripcion = _seccion("Descripción general de las pruebas")
    seccion_funcionales = _seccion("Pruebas funcionales realizadas")
    seccion_fallos = _seccion("Fallos detectados y correcciones")
    seccion_controles = _seccion("Controles de seguridad verificados")
    seccion_pruebas_seguridad = _seccion("Pruebas de seguridad realizadas")
    seccion_evidencias = _seccion("Evidencias de las pruebas")
    seccion_pendientes = _seccion("Aspectos pendientes")
    seccion_observaciones = _seccion("Observaciones adicionales")

    return {
        "id": str(issue.iid),
        "issue_iid": int(issue.iid),
        "prueba_id": prueba_id,
        "titulo": issue.title,

        "codificaciones_relacionadas": _extraer_codificaciones(seccion_implementacion),

        "descripcion": _limpiar_descripcion(seccion_descripcion),

        "pruebas_funcionales": _extraer_pruebas_funcionales(seccion_funcionales),
        "fallos": _extraer_fallos(seccion_fallos),
        "controles_seguridad": _extraer_controles_seguridad(seccion_controles),
        "pruebas_seguridad": _extraer_pruebas_seguridad(seccion_pruebas_seguridad),
        "evidencias": _extraer_evidencias(seccion_evidencias),
        "pendientes": _extraer_lista(seccion_pendientes),
        "observaciones": _extraer_lista(seccion_observaciones),

        "labels": issue.labels,

        "validacion_entrada": {
            "estado": "",
            "campos_faltantes": [],
            "advertencias": [],
        },
    }
