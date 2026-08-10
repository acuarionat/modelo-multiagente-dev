def normalizar_fila_trazabilidad(row):
    return {
        "codigo": (
            row.get("codigo")
            or row.get("Código")
        ),
        "nombre": (
            row.get("nombre")
            or row.get("Nombre")
        ),
        "descripcion": (
            row.get("descripcion")
            or row.get("Descripción")
            or row.get("descripcion_formal")
        ),
        "tipo": (
            row.get("tipo")
            or row.get("Tipo")
        ),
        "historia_origen": (
            row.get("historia_origen")
            or row.get("Historia de origen")
        ),
        "estado": (
            row.get("estado")
            or row.get("Estado de revisión")
            or row.get("Estado")
        ),
    }


def construir_contexto_diseno(issue_diseno: dict, matriz_entrada_diseno: list) -> dict:
    """
    matriz_entrada_diseno es la matriz vigente para Diseño (ya validada y
    confirmada por el responsable del proyecto), no necesariamente idéntica
    a la matriz original de Requerimientos: puede haber sido editada en
    GitLab (TRZ-001) o mediante Excel antes de iniciar el análisis.
    """
    filas_normalizadas = [normalizar_fila_trazabilidad(row) for row in matriz_entrada_diseno]
    requisitos_por_codigo = {
        fila["codigo"]: fila
        for fila in filas_normalizadas
    }

    requerimientos_contextualizados = []
    referencias_validas = []
    referencias_invalidas = []

    for codigo in issue_diseno.get("requerimientos_relacionados", []):
        fila = requisitos_por_codigo.get(codigo)
        if fila is None:
            referencias_invalidas.append(codigo)
            continue
        referencias_validas.append(codigo)
        requerimientos_contextualizados.append({
            "codigo": fila.get("codigo"),
            "nombre": fila.get("nombre"),
            "descripcion_formal": fila.get("descripcion"),
            "tipo": fila.get("tipo"),
            "prioridad": fila.get("prioridad", ""),
            "historia_origen": fila.get("historia_origen"),
        })

    return {
        **issue_diseno,
        "requerimientos_contextualizados": requerimientos_contextualizados,
        "validacion_trazabilidad": {
            "referencias_validas": referencias_validas,
            "referencias_invalidas": referencias_invalidas,
        },
    }
