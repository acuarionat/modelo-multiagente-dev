"""
Validación y versionado de la Matriz de Requerimientos como entrada de
Diseño. Todo el cómputo aquí es determinístico y local: no invoca LLM ni
GitLab. Trabaja siempre sobre filas ya normalizadas (codigo, nombre,
descripcion, tipo, historia_origen, estado), el mismo contrato que produce
core/design_context.py::normalizar_fila_trazabilidad.
"""

import re

ESTADO_MATRIZ_ORIGINAL = "ORIGINAL"
ESTADO_MATRIZ_EDITADA = "EDITADA"
ESTADO_MATRIZ_INVALIDA = "INVALIDA"

ESTADOS_MATRIZ_VALIDOS = {ESTADO_MATRIZ_ORIGINAL, ESTADO_MATRIZ_EDITADA, ESTADO_MATRIZ_INVALIDA}

_TIPOS_VALIDOS = {"funcional", "no funcional", "rf", "rnf"}


def validar_matriz_entrada_diseno(matriz_entrada: list) -> dict:
    """
    Valida estructuralmente la matriz de entrada de Diseño (ya normalizada).
    No evalúa calidad ni seguridad: solo integridad mínima de los datos.
    """
    errores = []
    codigos_vistos = set()

    if not matriz_entrada:
        errores.append("La matriz de entrada no contiene requisitos.")

    for fila in matriz_entrada:
        codigo = str(fila.get("codigo") or "").strip()
        if not codigo:
            errores.append("Existe una fila sin código de requisito.")
            continue
        if not re.fullmatch(r"RN?F-\d+", codigo):
            errores.append(f"{codigo}: el código no tiene el formato RF-### o RNF-###.")
        if codigo in codigos_vistos:
            errores.append(f"{codigo}: código duplicado en la matriz de entrada.")
        codigos_vistos.add(codigo)
        if not str(fila.get("nombre") or "").strip():
            errores.append(f"{codigo}: no tiene nombre.")
        if not str(fila.get("descripcion") or "").strip():
            errores.append(f"{codigo}: no tiene descripción.")
        if str(fila.get("tipo") or "").strip().casefold() not in _TIPOS_VALIDOS:
            errores.append(f"{codigo}: tipo no reconocido ({fila.get('tipo')!r}).")
        if not str(fila.get("historia_origen") or "").strip():
            errores.append(f"{codigo}: no tiene historia de origen.")

    return {
        "valida": not errores,
        "errores": errores,
    }


def comparar_matrices_requerimientos(matriz_original: list, matriz_entrada: list) -> dict:
    """
    Compara dos matrices ya normalizadas y detecta agregados, modificados y
    retirados. No decide ningún estado: solo reporta diferencias.
    """
    original_por_codigo = {fila["codigo"]: fila for fila in matriz_original if fila.get("codigo")}
    entrada_por_codigo = {fila["codigo"]: fila for fila in matriz_entrada if fila.get("codigo")}

    codigos_original = set(original_por_codigo)
    codigos_entrada = set(entrada_por_codigo)

    agregados = sorted(codigos_entrada - codigos_original)
    retirados = sorted(codigos_original - codigos_entrada)

    campos_comparables = ("nombre", "descripcion", "tipo", "historia_origen")
    modificados = []
    for codigo in sorted(codigos_entrada & codigos_original):
        fila_original = original_por_codigo[codigo]
        fila_entrada = entrada_por_codigo[codigo]
        cambios_campo = []
        for campo in campos_comparables:
            valor_original = str(fila_original.get(campo) or "").strip()
            valor_entrada = str(fila_entrada.get(campo) or "").strip()
            if valor_original != valor_entrada:
                cambios_campo.append({
                    "campo": campo,
                    "valor_anterior": valor_original,
                    "valor_vigente": valor_entrada,
                })
        if cambios_campo:
            modificados.append({"codigo": codigo, "cambios": cambios_campo})

    return {
        "agregados": agregados,
        "modificados": modificados,
        "retirados": retirados,
        "hay_cambios": bool(agregados or modificados or retirados),
    }


def preparar_matriz_entrada_diseno(matriz_original: list, matriz_entrada: list, fuente: str) -> dict:
    """
    Orquesta, sin recalcular nada por sí misma: valida → compara → determina
    el estado ORIGINAL/EDITADA/INVALIDA de la matriz de entrada de Diseño.
    """
    validacion = validar_matriz_entrada_diseno(matriz_entrada)
    comparacion = comparar_matrices_requerimientos(matriz_original, matriz_entrada)

    if not validacion["valida"]:
        estado = ESTADO_MATRIZ_INVALIDA
    elif comparacion["hay_cambios"]:
        estado = ESTADO_MATRIZ_EDITADA
    else:
        estado = ESTADO_MATRIZ_ORIGINAL

    return {
        "matriz_entrada_diseno": matriz_entrada,
        "matriz_estado": estado,
        "matriz_fuente": fuente,
        "matriz_validacion": validacion,
        "matriz_cambios_pre_diseno": comparacion,
        "requisitos_vigentes": len(matriz_entrada),
    }
