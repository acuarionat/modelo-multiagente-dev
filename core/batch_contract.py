import json
import logging
import re
import unicodedata
from collections import Counter
from datetime import datetime
from typing import Any, Dict, Iterable, List, Set, Tuple

logger = logging.getLogger(__name__)

INVALID_TEXT_VALUES = {
    "", "...", "n/a", "ninguno", "ninguna", "desconocido", "desconocida",
    "no especificado", "sin información",
}
GENERIC_TEXT_FRAGMENTS = {
    "explicación específica", "función concreta", "texto real de origen",
    "título real", "actor real", "objetivo real", "riesgo concreto",
    "corrección concreta", "control concreto", "dato o impacto concreto",
}
PROCEDENCIAS_EXPLICITAS = {
    "explícita — funcionalidad", "explícita — criterio de aceptación",
    "explícita — restricción", "explícita — observación",
}
PROCEDENCIAS_VALIDAS = PROCEDENCIAS_EXPLICITAS | {"inferida"}


def calcular_num_predict(agent: str, issue_count: int) -> int:
    limits = {
        "Central_Init": min(500 + issue_count * 280, 2100),
        "Quality": min(450 + issue_count * 260, 1750),
        "Security": min(500 + issue_count * 300, 2000),
        "Evaluator": min(200 + issue_count * 110, 850),
    }
    return limits[agent]


def es_texto_invalido(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip().casefold()
    normalized_placeholder = normalized.rstrip(".:")
    return normalized in INVALID_TEXT_VALUES or normalized_placeholder in GENERIC_TEXT_FRAGMENTS


def explicar_texto_invalido(value: Any) -> str:
    """Devuelve la regla concreta que rechazó un texto, sin endurecer el contrato."""
    if not isinstance(value, str):
        return f"debe ser texto y se recibió {type(value).__name__}"
    normalized = value.strip().casefold()
    if normalized in INVALID_TEXT_VALUES:
        return f"no puede ser un valor vacío o marcador prohibido ({normalized!r})"
    normalized_placeholder = normalized.rstrip(".:")
    if normalized_placeholder in GENERIC_TEXT_FRAGMENTS:
        return f"no puede ser el texto genérico de ejemplo {normalized_placeholder!r}"
    return "debe ser un texto específico basado en la evidencia de la historia"


def _normalizar_lista_evidencia(values: Any) -> tuple[List[str], List[str]]:
    if isinstance(values, str):
        values = [values] if values.strip() else []
    elif values is None:
        values = []
    elif not isinstance(values, list):
        values = [str(values)]
    clean, warnings, seen = [], [], set()
    for value in values:
        if es_texto_invalido(value):
            warnings.append("se descartó evidencia vacía o genérica")
            continue
        text = " ".join(value.split()).strip()
        key = _clave_texto(text)
        if key in seen:
            warnings.append(f"se eliminó evidencia duplicada: {text}")
            continue
        seen.add(key)
        clean.append(text)
    return clean, warnings


def _restringir_subconjunto(values: List[str], universe: List[str], label: str) -> tuple[List[str], List[str]]:
    by_key = {_clave_texto(value): value for value in universe}
    valid, removed = [], []
    for value in values:
        canonical = by_key.get(_clave_texto(value))
        if canonical is None:
            removed.append(f"{label} fuera del universo evaluado: {value}")
        elif canonical not in valid:
            valid.append(canonical)
    return valid, removed


def _clave_texto(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def normalizar_lista_textos(valor: Any) -> List[str]:
    """Convierte texto o colección en una lista sin iterar cadenas por carácter."""
    if valor is None:
        return []
    values = [valor] if isinstance(valor, str) else valor if isinstance(valor, list) else [valor]
    return [text for item in values if (text := str(item).strip())]


def _tipo_desde_texto(text: str) -> str:
    key = _clave_texto(text)
    return "RNF" if any(marker in key for marker in (
        "menos de", "segundo", "tiempo de respuesta", "en tiempo real",
        "rendimiento", "disponibilidad", "actualizacion inmediata",
    )) else "RF"


def _descripcion_requerimiento_explicito(text: str) -> str:
    clean = text.strip().strip("-*• ").rstrip(".")
    key = _clave_texto(clean)
    if "reportes deben poder imprimirse" in key:
        return "El sistema deberá permitir imprimir los reportes."
    if "menos de" in key and "segundo" in key:
        return "El sistema deberá responder en menos de tres segundos."
    if "tiempo real" in key:
        return "El sistema deberá mostrar la información en tiempo real."
    if "editar" in key and "informacion" in key and "paciente" in key:
        return "El sistema deberá permitir editar la información del paciente."
    if clean.casefold().startswith("el sistema deberá"):
        return f"{clean}."
    return f"El sistema deberá {clean[:1].lower() + clean[1:]}."


def completar_requerimientos_explicitos_faltantes(
    requerimientos_central: Any, issue_original: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Conserva la salida válida del Central y añade evidencia explícita omitida."""
    requirements = (
        [item for item in requerimientos_central if isinstance(item, dict)]
        if isinstance(requerimientos_central, list) else []
    )
    candidates: List[tuple[str, str]] = []
    functionality = str(issue_original.get("funcionalidad") or "").strip()
    if functionality and not _es_no_definido(functionality):
        candidates.append((functionality, "funcionalidad"))
    candidates.extend(
        (text, "criterio de aceptación")
        for text in normalizar_lista_textos(issue_original.get("criterios_aceptacion"))
        if not _es_no_definido(text)
    )
    candidates.extend(
        (text, "restricción")
        for text in normalizar_lista_textos(issue_original.get("restricciones"))
        if not _es_no_definido(text)
    )
    observations = normalizar_lista_textos(issue_original.get("observaciones"))
    for observation in observations:
        for text in (part.strip(" -*•") for part in re.split(r"[\r\n]+", observation)):
            key = _clave_texto(text)
            if text and not _es_no_definido(text) and any(marker in key for marker in (
                "imprimir", "editar", "actualizar", "tiempo de respuesta",
                "en tiempo real", "mostrar", "registrar", "permitir",
            )):
                candidates.append((text, "observación"))

    def semantic_key(value: Any) -> Set[str]:
        normalized = _clave_texto(value)
        replacements = {
            "imprimirse": "imprimir", "impresion": "imprimir",
            "mostrada": "mostrar", "mostrarse": "mostrar",
            "actualizada": "actualizar", "actualizacion": "actualizar",
            "edicion": "editar", "validacion": "validar",
        }
        ignored = {
            "el", "la", "los", "las", "un", "una", "de", "del", "al", "en",
            "y", "que", "se", "debe", "debera", "sistema", "permitir", "poder",
        }
        return {replacements.get(word, word) for word in normalized.split() if word not in ignored}

    def requirement_text(requirement: Dict[str, Any]) -> str:
        return " ".join(str(requirement.get(field) or "") for field in (
            "nombre", "descripcion_formal", "descripcion", "origen",
        ))

    def covers(requirement: Dict[str, Any], source_text: str) -> bool:
        source_words = semantic_key(source_text)
        requirement_words = semantic_key(requirement_text(requirement))
        return bool(source_words) and source_words.issubset(requirement_words)

    for text, origin_kind in candidates:
        matches = [requirement for requirement in requirements if covers(requirement, text)]
        if matches:
            for requirement in matches:
                requirement["tipo"] = _tipo_desde_texto(text)
                requirement["procedencia"] = f"explícita — {origin_kind}"
            continue
        requirements.append({
            "nombre": text.strip().rstrip("."),
            "descripcion_formal": _descripcion_requerimiento_explicito(text),
            "tipo": _tipo_desde_texto(text),
            "origen": text.strip(),
            "justificacion": f"Formalizado desde texto explícito de {origin_kind}.",
            "prioridad": issue_original.get("prioridad"),
            "procedencia": f"explícita — {origin_kind}",
        })
    return requirements


def _preparar_metrica(metric: Dict[str, Any], fields: List[str]) -> List[str]:
    warnings: List[str] = []
    for field in fields:
        metric[field], notes = _normalizar_lista_evidencia(metric.get(field, []))
        warnings.extend(notes)
    return warnings


def _marcar_no_evaluable(metric: Dict[str, Any], message: str) -> None:
    metric["valor"] = None
    metric["estado_medicion"] = "evidencia_insuficiente"
    metric.setdefault("advertencias_tecnicas", []).append(message)


def _promedio_evaluable(values: Iterable[Any]) -> float | None:
    valid = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return sum(valid) / len(valid) if valid else None


def _asegurar_recomendacion(metric: Dict[str, Any], metric_name: str) -> None:
    """Evita que una omisión textual del LLM invalide toda la historia."""
    value = metric.get("valor")
    if not isinstance(value, (int, float)) or value >= 1 or not es_texto_invalido(metric.get("recomendacion")):
        return
    defaults = {
        "cobertura_funcional": "Completar o aclarar los elementos funcionales identificados con problemas.",
        "adecuacion_funcional": "Revisar las funciones no alineadas y ajustar su relación con el objetivo declarado.",
        "controles_seguridad": "Definir los controles de seguridad faltantes para los requerimientos evaluados.",
        "lot_asignado": "Completar y justificar el nivel de aseguramiento recomendado para los requerimientos evaluados.",
    }
    metric["recomendacion"] = defaults[metric_name]
    metric.setdefault("advertencias_tecnicas", []).append(
        "El agente omitió una recomendación requerida; Python agregó una recomendación conservadora."
    )


def _calcular_proporcion_metrica(
    metric: Dict[str, Any], numerator: int, denominator: int,
    formula: str, calculation: str,
) -> Dict[str, Any]:
    """Completa una métrica sin convertir ausencia de evidencia en cero."""
    metric["formula"] = formula
    metric["variables"] = {"numerador": numerator, "denominador": denominator}
    if denominator == 0:
        metric.update({
            "estado_calculo": "No aplica", "estado_medicion": "no_aplicable",
            "valor": None, "porcentaje": None, "calculo": "No aplica",
        })
    elif numerator < 0 or numerator > denominator:
        metric.update({
            "estado_calculo": "No evaluado", "estado_medicion": "evidencia_insuficiente",
            "valor": None, "porcentaje": None, "calculo": "No evaluado",
        })
        metric.setdefault("advertencias_tecnicas", []).append(
            "El numerador no puede superar el denominador."
        )
    else:
        value = numerator / denominator
        metric.update({
            "estado_calculo": "Calculada", "estado_medicion": "evaluable",
            "valor": round(value, 4), "porcentaje": round(value * 100, 2),
            "calculo": calculation,
        })
    return metric


def _completar_indicador(
    first: Dict[str, Any], second: Dict[str, Any],
    name: str, meta: float | None, lot: str | None = None,
) -> Dict[str, Any]:
    indicator = {
        "nombre": name, "valor": None, "porcentaje": None,
        "meta": meta, "meta_porcentaje": round(meta * 100, 2) if meta is not None else None,
        "estado": "No evaluado", "calculo": "No evaluado",
    }
    if lot is not None:
        indicator["lot"] = lot
    if (
        first.get("estado_calculo") != "Calculada"
        or second.get("estado_calculo") != "Calculada"
        or meta is None
    ):
        return indicator
    value = round((first["valor"] + second["valor"]) / 2, 4)
    indicator.update({
        "valor": value, "porcentaje": round(value * 100, 2),
        "calculo": f"({first['valor']:.4f} + {second['valor']:.4f}) / 2",
        "estado": "Cumple" if value >= meta else "No cumple",
    })
    return indicator


def _justificacion_proporcion(
    nombre: str, universo: List[str], incluidos: List[str], faltantes: List[str],
) -> str:
    total = len(universo)
    return (
        f"{nombre}: A={total} elementos especificados y B={len(faltantes)} faltantes. "
        f"Incluidos: {', '.join(incluidos) if incluidos else 'ninguno'}. "
        f"Faltantes: {', '.join(faltantes) if faltantes else 'ninguno'}."
    )


def completar_resultado_calidad(
    item: Dict[str, Any], context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Normaliza evidencia y calcula MC-01, MC-02 e Índice de Calidad."""
    metrics = item.get("metricas")
    metrics = metrics if isinstance(metrics, dict) else {}
    mc01 = metrics.get("cobertura_funcional")
    mc02 = metrics.get("adecuacion_funcional")
    mc01 = mc01 if isinstance(mc01, dict) else {}
    mc02 = mc02 if isinstance(mc02, dict) else {}
    _preparar_metrica(mc01, ["funciones_especificadas", "funciones_incluidas", "funciones_faltantes"])
    _preparar_metrica(mc02, ["funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas"])
    specified = mc01["funciones_especificadas"]
    included, notes = _restringir_subconjunto(
        mc01["funciones_incluidas"], specified, "función incluida",
    )
    missing, missing_notes = _restringir_subconjunto(
        mc01["funciones_faltantes"], specified, "función faltante",
    )
    mc01["funciones_incluidas"] = included
    mc01["funciones_faltantes"] = missing
    if notes or missing_notes:
        mc01.setdefault("advertencias_tecnicas", []).extend(notes + missing_notes)

    # MC-02 usa exactamente el universo de MC-01; el agente solo aporta alineación.
    evaluable = list(specified)
    aligned, alignment_notes = _restringir_subconjunto(
        mc02["funciones_alineadas"], evaluable, "función alineada",
    )
    not_aligned = [function for function in evaluable if function not in aligned]
    mc02["funciones_evaluables"] = evaluable
    mc02["funciones_alineadas"] = aligned
    mc02["funciones_no_alineadas"] = not_aligned
    if alignment_notes:
        mc02.setdefault("advertencias_tecnicas", []).extend(alignment_notes)
    if context and isinstance(context.get("objetivo"), str):
        mc02["objetivo_evaluado"] = context["objetivo"].strip()
    mc01.update({"codigo": "MC-01", "nombre": "Cobertura Funcional"})
    _calcular_proporcion_metrica(
        mc01, len(missing), len(specified),
        "1 - (funciones_faltantes / funciones_especificadas)",
        f"1 - ({len(missing)} / {len(specified)})",
    )
    if mc01.get("estado_calculo") == "Calculada":
        value = round(1 - len(missing) / len(specified), 4)
        mc01.update({"valor": value, "porcentaje": round(value * 100, 2)})
    if specified and not included and not missing:
        mc01.update({
            "estado_calculo": "No evaluado", "estado_medicion": "evidencia_insuficiente",
            "valor": None, "porcentaje": None, "calculo": "No evaluado",
        })
    mc01["justificacion"] = _justificacion_proporcion(
        "MC-01", specified, included, missing,
    )
    mc01["recomendacion"] = (
        "Clasificar las funciones especificadas como incluidas o faltantes."
        if specified and not included and not missing else
        f"Incorporar o aclarar las funciones faltantes: {', '.join(missing)}."
        if missing else ""
    )
    mc02.update({"codigo": "MC-02", "nombre": "Adecuación Funcional"})
    _calcular_proporcion_metrica(
        mc02, len(aligned), len(evaluable),
        "funciones_alineadas / funciones_evaluables",
        f"{len(aligned)} / {len(evaluable)}",
    )
    objective = str(mc02.get("objetivo_evaluado") or "no definido").strip()
    mc02["justificacion"] = (
        f"MC-02: {len(aligned)} de {len(evaluable)} funciones especificadas se alinean "
        f"con el objetivo '{objective}'. Alineadas: "
        f"{', '.join(aligned) if aligned else 'ninguna'}. No alineadas: "
        f"{', '.join(not_aligned) if not_aligned else 'ninguna'}."
    )
    mc02["recomendacion"] = (
        f"Alinear con el objetivo las funciones: {', '.join(not_aligned)}."
        if not_aligned else ""
    )
    metrics = {"cobertura_funcional": mc01, "adecuacion_funcional": mc02}
    indicator = _completar_indicador(
        mc01, mc02, "Índice de Calidad de Requerimientos", 0.95,
    )
    item.update({
        "metricas": metrics, "indicador": indicator, "indice": indicator["valor"],
        "meta_cumplida": indicator["estado"] == "Cumple",
        "estado_medicion": "evaluable" if indicator["valor"] is not None else "evidencia_insuficiente",
    })
    item["recomendaciones"] = [
        text for text in (mc01["recomendacion"], mc02["recomendacion"]) if text
    ]
    return item


def _es_no_definido(value: Any) -> bool:
    return _clave_texto(value) in {
        "", "no", "no definido", "no definida", "desconocido", "desconocida", "n a",
    }


def _evidencia_seguridad_contexto(context: Dict[str, Any]) -> tuple[List[str], List[str], List[str], List[str]]:
    security = context.get("seguridad") if isinstance(context.get("seguridad"), dict) else {}
    applicable = ["Autenticación", "Autorización", "Auditoría"]
    documented = []
    for label, field in (
        ("Autenticación", "autenticacion"),
        ("Autorización", "autorizacion_roles"),
        ("Auditoría", "auditoria"),
    ):
        if not _es_no_definido(security.get(field)):
            documented.append(label)

    sensitive_text = str(security.get("maneja_datos_sensibles") or security.get("descripcion") or "")
    normalized_sensitive = _clave_texto(sensitive_text)
    data = []
    if normalized_sensitive and not normalized_sensitive.startswith("no"):
        for line in re.split(r"[\n,;]+", sensitive_text):
            clean = line.strip().strip(".-")
            key = _clave_texto(clean)
            if key and key not in {"si", "datos sensibles"}:
                data.append(clean)
    data = list(dict.fromkeys(data))
    classified = [
        value for value in data
        if any(marker in _clave_texto(value) for marker in (
            "personal", "sensible", "clinico", "salud", "biometrico", "financiero",
        ))
    ]
    return applicable, documented, data, classified


def _determinar_lot(context: Dict[str, Any] | None) -> tuple[str, str]:
    context_text = _clave_texto(str(context or {}))
    high_impact = any(marker in context_text for marker in (
        "datos clinicos", "historial clinico", "diagnostico", "datos de salud",
        "biometrico", "alto impacto", "riesgo critico",
    ))
    if high_impact:
        return "LoT-3", "LoT-3 asignado por evidencia explícita de alto impacto o datos altamente sensibles."
    return "LoT-2", "LoT-2 asignado por defecto al no existir una regla explícita de alto impacto."


def completar_resultado_seguridad(
    item: Dict[str, Any], context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Normaliza evidencia y calcula MS-01, MS-02 e Índice de Seguridad."""
    metrics = item.get("metricas")
    metrics = metrics if isinstance(metrics, dict) else {}
    ms01 = metrics.get("cobertura_seguridad")
    ms02 = metrics.get("clasificacion_datos")
    ms01 = ms01 if isinstance(ms01, dict) else {}
    ms02 = ms02 if isinstance(ms02, dict) else {}
    _preparar_metrica(ms01, [
        "aspectos_aplicables", "aspectos_documentados", "aspectos_parciales",
        "aspectos_faltantes", "aspectos_inferidos",
    ])
    _preparar_metrica(ms02, [
        "datos_identificados", "datos_clasificados", "datos_sin_clasificacion",
        "clasificaciones_inferidas",
    ])
    if context:
        applicable, documented, identified, classified = _evidencia_seguridad_contexto(context)
        ms01["aspectos_aplicables"] = applicable
        ms01["aspectos_documentados"] = documented
        ms01["aspectos_faltantes"] = [x for x in applicable if x not in documented]
        ms02["datos_identificados"] = identified
        ms02["datos_clasificados"] = classified
        ms02["datos_sin_clasificacion"] = [x for x in identified if x not in classified]
    else:
        applicable = ms01["aspectos_aplicables"]
        documented = ms01["aspectos_documentados"]
        identified = ms02["datos_identificados"]
        classified = ms02["datos_clasificados"]
    ms01.update({"codigo": "MS-01", "nombre": "Cobertura de Seguridad"})
    _calcular_proporcion_metrica(
        ms01, len(documented), len(applicable),
        "aspectos_documentados / aspectos_aplicables",
        f"{len(documented)} / {len(applicable)}",
    )
    missing_aspects = [x for x in applicable if x not in documented]
    ms01["justificacion"] = (
        f"MS-01: {len(documented)} de {len(applicable)} aspectos aplicables están "
        f"documentados. Documentados: {', '.join(documented) if documented else 'ninguno'}. "
        f"Faltantes: {', '.join(missing_aspects) if missing_aspects else 'ninguno'}."
    )
    ms01["recomendacion"] = (
        f"Documentar los aspectos faltantes: {', '.join(missing_aspects)}."
        if missing_aspects else ""
    )
    ms02.update({"codigo": "MS-02", "nombre": "Clasificación de Datos"})
    _calcular_proporcion_metrica(
        ms02, len(classified), len(identified),
        "datos_clasificados / datos_identificados",
        f"{len(classified)} / {len(identified)}",
    )
    unclassified = [x for x in identified if x not in classified]
    ms02["justificacion"] = (
        "MS-02: No aplica porque la historia no identifica datos." if not identified else
        f"MS-02: {len(classified)} de {len(identified)} datos identificados tienen "
        f"clasificación explícita. Clasificados: "
        f"{', '.join(classified) if classified else 'ninguno'}. Sin clasificación: "
        f"{', '.join(unclassified) if unclassified else 'ninguno'}."
    )
    ms02["recomendacion"] = (
        f"Clasificar explícitamente los datos identificados: {', '.join(unclassified)}."
        if unclassified else ""
    )
    lot, lot_reason = _determinar_lot(context)
    item["lot_recomendado"] = lot
    item["justificacion_lot"] = lot_reason
    meta = {"LoT-2": 0.90, "LoT-3": 0.95}.get(lot)
    indicator = _completar_indicador(
        ms01, ms02, "Índice de Seguridad en Requerimientos", meta, lot,
    )
    item.update({
        "metricas": {"cobertura_seguridad": ms01, "clasificacion_datos": ms02},
        "indicador": indicator, "indice": indicator["valor"],
        "meta_cumplida": indicator["estado"] == "Cumple",
        "estado_medicion": "evaluable" if indicator["valor"] is not None else "evidencia_insuficiente",
    })
    item["recomendaciones"] = [
        text for text in (ms01["recomendacion"], ms02["recomendacion"]) if text
    ]
    return item


def calcular_metricas_agente(
    response: Dict[str, Any], agent_name: str,
    context_by_iid: Dict[int, Dict[str, Any]] | None = None,
) -> None:
    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        context = (context_by_iid or {}).get(normalizar_iid(item.get("issue_iid")))
        item["recomendaciones"] = normalizar_lista_textos(item.get("recomendaciones"))
        metrics = item.get("metricas")
        if not isinstance(metrics, dict):
            continue
        if agent_name == "Calidad":
            coverage_candidate = metrics.get("cobertura_funcional")
            if isinstance(coverage_candidate, dict) and "funciones_especificadas" in coverage_candidate:
                completar_resultado_calidad(item, context)
                continue
            coverage = metrics.get("cobertura_funcional", {})
            adequacy = metrics.get("adecuacion_funcional", {})
            if not isinstance(coverage, dict) or not isinstance(adequacy, dict):
                continue
            coverage_warnings = _preparar_metrica(coverage, ["elementos_evaluados", "elementos_con_problemas"])
            adequacy_warnings = _preparar_metrica(adequacy, ["elementos_evaluados", "elementos_alineados", "elementos_con_problemas"])
            expected = coverage["elementos_evaluados"]
            missing = coverage["elementos_con_problemas"]
            evaluated = adequacy["elementos_evaluados"]
            aligned, membership_notes = _restringir_subconjunto(adequacy["elementos_alineados"], evaluated, "elemento alineado")
            adequacy["elementos_alineados"] = aligned
            adequacy_warnings.extend(membership_notes)
            if coverage.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
                _marcar_no_evaluable(coverage, "La cobertura funcional fue declarada sin evidencia suficiente.")
            elif coverage.get("estado_medicion") == "no_aplicable":
                coverage["valor"] = None
            elif not expected:
                _marcar_no_evaluable(coverage, "No existen elementos para calcular cobertura funcional.")
            else:
                coverage["valor"] = max(0.0, 1 - len(missing) / len(expected))
                coverage["estado_medicion"] = "evaluable"
            if adequacy.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
                _marcar_no_evaluable(adequacy, "La adecuación funcional fue declarada sin evidencia suficiente.")
            elif adequacy.get("estado_medicion") == "no_aplicable":
                adequacy["valor"] = None
            elif not evaluated:
                _marcar_no_evaluable(adequacy, "No existen elementos para calcular adecuación funcional.")
            else:
                adequacy["valor"] = min(1.0, len(aligned) / len(evaluated))
                adequacy["estado_medicion"] = "evaluable"
            if coverage_warnings:
                coverage.setdefault("advertencias_tecnicas", []).extend(dict.fromkeys(coverage_warnings))
            if adequacy_warnings:
                adequacy.setdefault("advertencias_tecnicas", []).extend(dict.fromkeys(adequacy_warnings))
            _asegurar_recomendacion(coverage, "cobertura_funcional")
            _asegurar_recomendacion(adequacy, "adecuacion_funcional")
            item["indice"] = _promedio_evaluable([coverage.get("valor"), adequacy.get("valor")])
            metric_states = {coverage.get("estado_medicion"), adequacy.get("estado_medicion")}
            item["estado_medicion"] = (
                "evaluable" if item["indice"] is not None
                else "no_aplicable" if metric_states == {"no_aplicable"}
                else "evidencia_insuficiente"
            )
            item["meta_cumplida"] = item["indice"] is not None and item["indice"] >= 0.95
            coverage["interpretacion"] = "Cobertura funcional estimada según los elementos identificados y formalizados."
            adequacy["interpretacion"] = "Adecuación funcional estimada según las funciones identificadas y el objetivo declarado."
            item["interpretacion_indice"] = "Índice de Calidad de Requerimientos."
        elif agent_name == "Seguridad":
            if "cobertura_seguridad" in metrics or "clasificacion_datos" in metrics:
                completar_resultado_seguridad(item, context)
                continue
            controls = metrics.get("controles_seguridad", {})
            lot = metrics.get("lot_asignado", {})
            if not isinstance(controls, dict) or not isinstance(lot, dict):
                continue
            control_warnings = _preparar_metrica(controls, ["requerimientos_evaluados", "requerimientos_con_controles", "controles_identificados", "controles_ausentes"])
            if "requerimientos_evaluados" not in lot:
                lot["requerimientos_evaluados"] = list(controls["requerimientos_evaluados"])
            lot_warnings = _preparar_metrica(lot, ["requerimientos_evaluados", "requerimientos_con_lot_justificado", "factores_considerados"])
            evaluated = controls["requerimientos_evaluados"]
            with_controls, notes = _restringir_subconjunto(controls["requerimientos_con_controles"], evaluated, "requerimiento con control")
            controls["requerimientos_con_controles"] = with_controls
            control_warnings.extend(notes)
            lot_evaluated = lot["requerimientos_evaluados"]
            with_lot, notes = _restringir_subconjunto(lot["requerimientos_con_lot_justificado"], lot_evaluated, "requerimiento con LoT")
            lot["requerimientos_con_lot_justificado"] = with_lot
            lot_warnings.extend(notes)
            if controls.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
                _marcar_no_evaluable(controls, "Los controles fueron declarados sin evidencia suficiente.")
            elif controls.get("estado_medicion") == "no_aplicable":
                controls["valor"] = None
            elif not evaluated:
                _marcar_no_evaluable(controls, "No existen requerimientos para evaluar controles de seguridad.")
            else:
                controls["valor"] = len(with_controls) / len(evaluated)
                controls["estado_medicion"] = "evaluable"
            if lot.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
                _marcar_no_evaluable(lot, "El LoT fue declarado sin evidencia suficiente.")
            elif lot.get("estado_medicion") == "no_aplicable":
                lot["valor"] = None
            elif not lot_evaluated:
                _marcar_no_evaluable(lot, "No existen requerimientos para justificar el LoT.")
            else:
                lot["valor"] = len(with_lot) / len(lot_evaluated)
                lot["estado_medicion"] = "evaluable"
            if control_warnings:
                controls.setdefault("advertencias_tecnicas", []).extend(dict.fromkeys(control_warnings))
            if lot_warnings:
                lot.setdefault("advertencias_tecnicas", []).extend(dict.fromkeys(lot_warnings))
            _asegurar_recomendacion(controls, "controles_seguridad")
            _asegurar_recomendacion(lot, "lot_asignado")
            item["indice"] = _promedio_evaluable([controls.get("valor"), lot.get("valor")])
            metric_states = {controls.get("estado_medicion"), lot.get("estado_medicion")}
            item["estado_medicion"] = (
                "evaluable" if item["indice"] is not None
                else "no_aplicable" if metric_states == {"no_aplicable"}
                else "evidencia_insuficiente"
            )
            item["meta_cumplida"] = item["indice"] is not None and item["indice"] >= 0.85
            item["lot_recomendado"] = lot.get("lot_recomendado")
            if context is not None:
                item["lot_recomendado"], item["justificacion_lot"] = _determinar_lot(context)
            controls["interpretacion"] = "Cobertura documental estimada de controles de seguridad aplicables."
            lot["interpretacion"] = "Nivel de aseguramiento recomendado; no representa la confianza del modelo."
            item["interpretacion_indice"] = "Índice de Seguridad en Requerimientos."


def validar_contenido_agente(response: Dict[str, Any], agent_name: str) -> Dict[int, List[str]]:
    errors: Dict[int, List[str]] = {}
    justifications: Dict[str, List[Tuple[int, str]]] = {}
    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        if iid is None:
            continue
        current: List[str] = []
        if agent_name == "Central":
            requirements = item.get("requerimientos")
            if not isinstance(requirements, list) or not requirements:
                current.append("no contiene requerimientos formales")
            else:
                required = ["temp_id", "nombre", "descripcion_formal", "tipo", "origen", "justificacion", "prioridad", "procedencia"]
                for index, requirement in enumerate(requirements, 1):
                    if not isinstance(requirement, dict):
                        current.append(f"requerimiento {index} no es un objeto")
                        continue
                    missing = [field for field in required if es_texto_invalido(requirement.get(field))]
                    if missing:
                        current.append(f"requerimiento {index} tiene campos inválidos: {', '.join(missing)}")
                    description = requirement.get("descripcion_formal", "")
                    if isinstance(description, str) and not description.strip().casefold().startswith("el sistema deberá"):
                        current.append(f"requerimiento {index} no comienza con 'El sistema deberá'")
                    if requirement.get("procedencia") not in PROCEDENCIAS_VALIDAS:
                        current.append(f"requerimiento {index} tiene procedencia inválida")
        elif agent_name in {"Calidad", "Seguridad"}:
            metrics = item.get("metricas")
            new_quality = (
                agent_name == "Calidad" and isinstance(metrics, dict)
                and isinstance(metrics.get("cobertura_funcional"), dict)
                and "funciones_especificadas" in metrics["cobertura_funcional"]
            )
            new_security = (
                agent_name == "Seguridad" and isinstance(metrics, dict)
                and ("cobertura_seguridad" in metrics or "clasificacion_datos" in metrics)
            )
            expected_names = (
                ["cobertura_funcional", "adecuacion_funcional"] if agent_name == "Calidad"
                else ["cobertura_seguridad", "clasificacion_datos"] if new_security
                else ["controles_seguridad", "lot_asignado"]
            )
            if not isinstance(metrics, dict):
                current.append("falta el objeto metricas")
            else:
                for metric_name in expected_names:
                    metric = metrics.get(metric_name)
                    if not isinstance(metric, dict):
                        current.append(f"falta la métrica {metric_name}")
                        continue
                    evidence_fields = (
                        (["funciones_especificadas", "funciones_incluidas", "funciones_faltantes"] if metric_name == "cobertura_funcional" and new_quality else
                         ["funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas"] if metric_name == "adecuacion_funcional" and new_quality else
                         ["elementos_evaluados", "elementos_con_problemas"] if metric_name == "cobertura_funcional" else
                         ["elementos_evaluados", "elementos_alineados"] if metric_name == "adecuacion_funcional" else
                         ["aspectos_aplicables", "aspectos_documentados", "aspectos_parciales", "aspectos_faltantes", "aspectos_inferidos"] if metric_name == "cobertura_seguridad" else
                         ["datos_identificados", "datos_clasificados", "datos_sin_clasificacion", "clasificaciones_inferidas"] if metric_name == "clasificacion_datos" else
                         ["requerimientos_evaluados", "requerimientos_con_controles", "controles_identificados", "controles_ausentes"] if metric_name == "controles_seguridad" else
                         ["requerimientos_evaluados", "requerimientos_con_lot_justificado", "factores_considerados"])
                    )
                    invalid_lists = [field for field in evidence_fields if not isinstance(metric.get(field), list)]
                    if invalid_lists:
                        current.append(f"{metric_name}: listas de evidencia inválidas: {', '.join(invalid_lists)}")
                    justification = metric.get("justificacion")
                    if es_texto_invalido(justification):
                        current.append(f"{metric_name}: justificación inválida")
                    else:
                        justifications.setdefault(justification.strip().casefold(), []).append((iid, metric_name))
                    value = metric.get("valor")
                    if isinstance(value, (int, float)) and value < 1 and es_texto_invalido(metric.get("recomendacion")):
                        current.append(f"{metric_name}: recomendación requerida para valor menor que 1")
        elif agent_name == "Evaluador":
            if item.get("veredicto") not in {"APROBADO", "CORREGIR", "ALERTA"}:
                current.append("veredicto inválido")
            if es_texto_invalido(item.get("conclusion")):
                current.append("conclusión inválida")
        if current:
            errors[iid] = current
    for text, occurrences in justifications.items():
        unique_iids = sorted({iid for iid, _ in occurrences})
        if len(unique_iids) > 1:
            for iid, metric_name in set(occurrences):
                errors.setdefault(iid, []).append(
                    f"{metric_name}: justificación repetida exactamente en varias historias"
                )
    return errors


def recopilar_recomendaciones(result: Dict[str, Any]) -> List[str]:
    recommendations: List[str] = []
    for section in (result.get("quality") or {}, result.get("security") or {}):
        metrics = section.get("metricas", {})
        for metric in metrics.values() if isinstance(metrics, dict) else []:
            if isinstance(metric, dict) and not es_texto_invalido(metric.get("recomendacion")):
                recommendations.append(metric["recomendacion"].strip())
        recommendations.extend(x for x in normalizar_lista_textos(section.get("recomendaciones")) if not es_texto_invalido(x))
    evaluation = result.get("evaluation") or {}
    recommendations.extend(x for x in normalizar_lista_textos(evaluation.get("correcciones_obligatorias")) if not es_texto_invalido(x))
    central = result.get("central") or {}
    recommendations.extend(x for x in normalizar_lista_textos(central.get("observaciones")) if not es_texto_invalido(x))
    return list(dict.fromkeys(recommendations))


def construir_etiquetas_resultado(old_labels: list, estado_evaluacion: str, quality_index=None, security_index=None) -> list:
    """Calcula el siguiente estado GitLab conservando etiquetas ajenas al flujo."""
    if estado_evaluacion not in {"APROBADO", "CORREGIR", "ALERTA", "NO_PROCESABLE", "NO_EVALUADO"}:
        return list(dict.fromkeys(old_labels))
    removed = {
        "Pendiente", "Revisada", "Requiere modificación",
        "En revisión", "Analizado", "Analizada", "Error de análisis",
    }
    labels = [
        label for label in old_labels
        if label not in removed and not label.startswith(("Calidad:", "Seguridad:", "Veredicto:"))
    ]
    if estado_evaluacion == "APROBADO":
        labels.append("Revisada")
    elif estado_evaluacion in {"CORREGIR", "ALERTA", "NO_PROCESABLE", "NO_EVALUADO"}:
        labels.append("Requiere modificación")
    return list(dict.fromkeys(labels))


def normalizar_iid(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        text = str(value).strip().upper().removeprefix("HU-")
        return int(text)
    except (TypeError, ValueError):
        return None


def analizar_respuesta_lote(raw: Any, agent_name: str) -> Dict[str, Any]:
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError as first_error:
            # Recupera un objeto JSON completo aunque el modelo haya añadido prosa.
            data = None
            decoder = json.JSONDecoder()
            for position, char in enumerate(text):
                if char != "{":
                    continue
                try:
                    candidate, _ = decoder.raw_decode(text[position:])
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict):
                    data = candidate
                    break
            if data is None:
                raise ValueError(f"{agent_name}: la respuesta no es JSON válido o quedó truncada.") from first_error
    else:
        data = raw
    if not isinstance(data, dict) or not isinstance(data.get("resultados"), list):
        raise ValueError(f"{agent_name}: falta el arreglo 'resultados'.")
    return data


def conciliar_ids_issues(
    response: Dict[str, Any], expected_issue_ids: List[int], agent_name: str,
    expected_titles: Dict[str, int] | None = None,
) -> List[str]:
    """Corrige IDs de ejemplo inventados por el LLM antes de validar el contrato.

    La consolidación sigue realizándose exclusivamente por issue_iid. Esta función
    actúa en el límite del agente y sólo reconcilia cuando la correspondencia es
    inequívoca: título único, ordinal 1..N, o cardinalidad completa sin IDs válidos.
    """
    results = response.get("resultados", [])
    expected = list(dict.fromkeys(expected_issue_ids))
    expected_set = set(expected)
    notes: List[str] = []
    if not results or len(results) != len(expected):
        return notes

    normalized_titles = {
        str(title).strip().casefold(): iid for title, iid in (expected_titles or {}).items()
    }
    assigned: Set[int] = set()
    unresolved: List[Tuple[int, Dict[str, Any]]] = []

    for position, item in enumerate(results):
        if not isinstance(item, dict):
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        if iid in expected_set and iid not in assigned:
            assigned.add(iid)
            item["issue_iid"] = iid
            item["historia_id"] = f"HU-{iid:03d}"
            continue
        title_iid = normalized_titles.get(str(item.get("titulo", "")).strip().casefold())
        if title_iid in expected_set and title_iid not in assigned:
            assigned.add(title_iid)
            item["issue_iid"] = title_iid
            item["historia_id"] = f"HU-{title_iid:03d}"
            notes.append(f"{agent_name}: issue_iid reconciliado por título a #{title_iid}.")
            continue
        unresolved.append((position, item))

    remaining = [iid for iid in expected if iid not in assigned]
    returned_unresolved = [normalizar_iid(item.get("issue_iid")) for _, item in unresolved]
    ordinal_map = {ordinal: iid for ordinal, iid in enumerate(expected, 1)}
    can_use_ordinals = (
        len(unresolved) == len(remaining)
        and all(iid in ordinal_map for iid in returned_unresolved)
        and len(set(returned_unresolved)) == len(returned_unresolved)
        and {ordinal_map[iid] for iid in returned_unresolved} == set(remaining)
    )
    if can_use_ordinals:
        for _, item in unresolved:
            old_iid = normalizar_iid(item.get("issue_iid"))
            new_iid = ordinal_map[old_iid]
            item["issue_iid"] = new_iid
            item["historia_id"] = f"HU-{new_iid:03d}"
            notes.append(f"{agent_name}: issue_iid de ejemplo #{old_iid} corregido a #{new_iid}.")
        return notes

    # Último recurso seguro para una respuesta completa: conserva la asociación
    # de cada salida con la misma posición de entrada, antes de cualquier cruce.
    positional_targets = [expected[position] for position, _ in unresolved]
    if (
        len(unresolved) == len(remaining)
        and set(positional_targets) == set(remaining)
        and not (set(returned_unresolved) & expected_set)
    ):
        for (position, item), new_iid in zip(unresolved, positional_targets):
            item["issue_iid"] = new_iid
            item["historia_id"] = f"HU-{new_iid:03d}"
            notes.append(f"{agent_name}: salida {position + 1} anclada al Issue #{new_iid}.")
    return notes


def validar_respuesta_lote(
    response: Dict[str, Any], expected_issue_ids: Set[int], agent_name: str
) -> List[str]:
    results = response["resultados"]
    errors: List[str] = []
    returned: List[int] = []
    for position, item in enumerate(results, 1):
        if not isinstance(item, dict):
            errors.append(f"{agent_name}: resultado {position} no es un objeto.")
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        if iid is None:
            errors.append(f"{agent_name}: resultado {position} no incluye issue_iid válido.")
            continue
        item["issue_iid"] = iid
        item.setdefault("historia_id", f"HU-{iid:03d}")
        returned.append(iid)
        if agent_name == "Central" and not isinstance(item.get("requerimientos"), list):
            errors.append(f"Central: 'requerimientos' no es una lista para Issue #{iid}.")
        if agent_name in {"Calidad", "Seguridad"}:
            indice = item.get("indice")
            no_evaluable = indice is None and item.get("estado_medicion") in {
                "no_evaluable", "no_aplicable", "evidencia_insuficiente",
            }
            if not no_evaluable and (not isinstance(indice, (int, float)) or isinstance(indice, bool) or not 0 <= indice <= 1):
                errors.append(f"{agent_name}: índice inválido para Issue #{iid}.")
    duplicates = sorted(iid for iid, count in Counter(returned).items() if count > 1)
    if duplicates:
        errors.append(f"{agent_name}: IDs duplicados {duplicates}.")
    missing = sorted(expected_issue_ids - set(returned))
    if missing:
        errors.append(f"{agent_name}: faltan resultados para Issues {missing}.")
    unexpected = sorted(set(returned) - expected_issue_ids)
    if unexpected:
        errors.append(f"{agent_name}: devolvió Issues no solicitados {unexpected}.")
    return errors


def indexar_resultados(response: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}
    for item in response.get("resultados", []):
        if isinstance(item, dict):
            iid = normalizar_iid(item.get("issue_iid"))
            if iid is not None and iid not in indexed:
                indexed[iid] = item
    return indexed


def normalizar_tipo_requerimiento(requirement: Dict[str, Any]) -> str:
    """Reduce tipos actuales y heredados a RF/RNF usando el contenido."""
    kind = str(requirement.get("tipo", "")).strip().upper()
    if kind in {"RF", "RNF"}:
        return kind

    text = " ".join(str(requirement.get(key, "")) for key in (
        "nombre", "descripcion", "descripcion_formal", "origen", "justificacion",
    )).casefold()
    functional_markers = (
        "permitir", "registrar", "mostrar", "generar", "filtrar", "autenticar",
        "validar", "evitar", "cancelar", "consultar", "actualizar", "notificar",
        "calcular", "enviar", "crear", "eliminar", "modificar", "almacenar",
    )
    nonfunctional_markers = (
        "menos de", "tiempo de respuesta", "rendimiento", "confidencial",
        "integridad", "disponibilidad", "confiabilidad", "usabilidad",
        "mantenibilidad", "trazabilidad", "proteg", "restrin", "autorizad",
        "seguridad", "en tiempo real", "calidad", "deberá garantizar",
    )
    functional = any(marker in text for marker in functional_markers)
    nonfunctional = any(marker in text for marker in nonfunctional_markers)
    if functional:
        normalized = "RF"
    elif nonfunctional:
        normalized = "RNF"
    else:
        normalized = "RNF"
        requirement["_normalizacion_tipo_pendiente"] = True
        logger.warning(
            "Tipo heredado o inesperado %r normalizado conservadoramente a RNF; "
            "requiere revisión humana. Requerimiento=%r",
            kind or None, requirement.get("nombre") or requirement.get("id"),
        )
    if kind not in {"RC", "RS", ""}:
        logger.warning("Tipo de requerimiento inesperado %r normalizado a %s.", kind, normalized)
    requirement["_tipo_original"] = kind or None
    return normalized


def renumerar_requerimientos(items: Iterable[Dict[str, Any]]) -> None:
    counters = {"RF": 0, "RNF": 0}
    generation_date = datetime.now().date().isoformat()
    for item in items:
        for requirement in item.get("requerimientos", []):
            if not isinstance(requirement, dict):
                continue
            kind = normalizar_tipo_requerimiento(requirement)
            counters[kind] += 1
            requirement["tipo"] = kind
            requirement["id"] = f"{kind}-{counters[kind]:03d}"
            requirement["descripcion"] = requirement.get("descripcion_formal") or requirement.get("descripcion", "")
            requirement.setdefault("fecha_generacion", generation_date)
            if requirement.get("procedencia") not in PROCEDENCIAS_VALIDAS:
                requirement["procedencia"] = "inferida"


def ajustar_veredicto_determinista(
    central: Dict[str, Any], quality: Dict[str, Any], security: Dict[str, Any],
    evaluation: Dict[str, Any], input_validation: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Valida el veredicto del LLM sin reemplazar su explicación ni sus hallazgos."""
    original = evaluation.get("veredicto")
    reasons: List[str] = []
    alert_reasons: List[str] = []
    input_validation = input_validation or {"estado": "entrada_valida", "campos_faltantes": []}
    if input_validation.get("estado") == "informacion_insuficiente":
        alert_reasons.append("La información de entrada es insuficiente.")
    if evaluation.get("riesgos_criticos"):
        alert_reasons.append("Se identificaron riesgos críticos.")
    for label, report in (("calidad", quality), ("seguridad", security)):
        if report.get("indice") is None or report.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
            alert_reasons.append(f"La métrica esencial de {label} no es evaluable.")
        if any(
            isinstance(metric, dict) and metric.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}
            for metric in report.get("metricas", {}).values()
        ):
            alert_reasons.append(f"Existe evidencia insuficiente en una métrica esencial de {label}.")

    if alert_reasons:
        adjusted = "ALERTA"
        reasons = alert_reasons
    else:
        if isinstance(quality.get("indice"), (int, float)) and quality["indice"] < 0.95:
            reasons.append("Índice de Calidad de Requerimientos bajo la meta de apoyo.")
        if isinstance(security.get("indice"), (int, float)) and security["indice"] < 0.85:
            reasons.append("Índice de Seguridad en Requerimientos bajo la meta de apoyo.")
        if evaluation.get("correcciones_obligatorias"):
            reasons.append("Existen correcciones obligatorias.")
        if central.get("ambiguedades") or central.get("informacion_faltante"):
            reasons.append("Existen ambigüedades o información faltante.")
        metric_recommendations = []
        for report in (quality, security):
            for metric in report.get("metricas", {}).values():
                if isinstance(metric, dict) and not es_texto_invalido(metric.get("recomendacion")):
                    metric_recommendations.append(metric["recomendacion"])
            metric_recommendations.extend(
                value for value in report.get("recomendaciones", []) if not es_texto_invalido(value)
            )
        if metric_recommendations:
            reasons.append("Existen recomendaciones necesarias antes de continuar.")
        adjusted = "CORREGIR" if reasons else "APROBADO"

    evaluation["veredicto_ajustado"] = adjusted
    if adjusted != original:
        evaluation["veredicto_original"] = original
        evaluation["motivo_ajuste"] = " ".join(dict.fromkeys(reasons))
    evaluation["veredicto"] = adjusted
    evaluation["es_decision_formal"] = False
    return evaluation


def consolidar_lote(
    expected_issue_ids: Set[int], central: Dict[str, Any], quality: Dict[str, Any],
    security: Dict[str, Any], evaluation: Dict[str, Any], validation_errors: List[str] | None = None,
    content_validation_errors: Dict[int, List[str]] | None = None,
    input_validations: Dict[int, Dict[str, Any]] | None = None,
    original_issues: Dict[int, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    maps = [indexar_resultados(x) for x in (central, quality, security, evaluation)]
    names = ["Central", "Calidad", "Seguridad", "Evaluador"]
    for iid, central_item in maps[0].items():
        source = (original_issues or {}).get(iid)
        if not source:
            continue
        for field in ("actor", "funcionalidad", "objetivo"):
            if not _es_no_definido(source.get(field)):
                central_item[field] = source[field]
        central_item["requerimientos"] = completar_requerimientos_explicitos_faltantes(
            central_item.get("requerimientos"), source,
        )
    renumerar_requerimientos(maps[0][iid] for iid in sorted(maps[0]))
    consolidated = []
    for iid in sorted(expected_issue_ids):
        missing = [name for name, mapping in zip(names, maps) if iid not in mapping]
        errors = [f"Falta la salida del Agente {name}." for name in missing]
        warnings = list((content_validation_errors or {}).get(iid, []))
        central_item, quality_item, security_item, evaluation_item = (mapping.get(iid) for mapping in maps)
        if central_item is not None and not isinstance(central_item.get("requerimientos"), list):
            errors.append("El Agente Central devolvió requerimientos inválidos.")
        for name, item in (("Calidad", quality_item), ("Seguridad", security_item)):
            if item is not None:
                index = item.get("indice")
                no_evaluable = index is None and item.get("estado_medicion") in {"no_evaluable", "no_aplicable", "evidencia_insuficiente"}
                if not no_evaluable and (not isinstance(index, (int, float)) or isinstance(index, bool) or not 0 <= index <= 1):
                    errors.append(f"El Agente de {name} devolvió un índice inválido.")
        if evaluation_item is not None and evaluation_item.get("veredicto") not in {"APROBADO", "CORREGIR", "ALERTA"}:
            errors.append("El Agente Evaluador devolvió un veredicto inválido.")
        if evaluation_item is not None:
            derived_risks = []
            security_metrics = security_item.get("metricas", {}) if isinstance(security_item, dict) else {}
            ms01 = security_metrics.get("cobertura_seguridad", {})
            ms02 = security_metrics.get("clasificacion_datos", {})
            for aspect in normalizar_lista_textos(ms01.get("aspectos_faltantes")):
                derived_risks.append(f"Aspecto de seguridad sin documentar: {aspect}.")
            for datum in normalizar_lista_textos(ms02.get("datos_sin_clasificacion")):
                derived_risks.append(f"Dato identificado sin clasificación: {datum}.")
            evaluation_item["riesgos_criticos"] = list(dict.fromkeys(derived_risks))
        input_validation = (input_validations or {}).get(iid, {"estado": "entrada_valida", "advertencias": [], "campos_faltantes": []})
        estado_evaluacion = evaluation_item.get("veredicto", "NO_EVALUADO") if evaluation_item else "NO_EVALUADO"
        consolidated.append({
            "issue_iid": iid,
            "status": "error" if errors else "ok",
            "estado_procesamiento": "error" if errors else "completo",
            "estado_evaluacion": estado_evaluacion,
            "errors": errors,
            "warnings": warnings,
            "validacion_entrada": input_validation,
            "central": central_item,
            "quality": quality_item,
            "security": security_item,
            "evaluation": evaluation_item,
            "revision_humana_requerida": True,
            "estado_revision_humana": "pendiente",
            "responsable_revision": None,
        })
    valid = [x for x in consolidated if x["status"] == "ok"]
    quality_values = [x["quality"]["indice"] for x in valid if isinstance(x["quality"].get("indice"), (int, float))]
    security_values = [x["security"]["indice"] for x in valid if isinstance(x["security"].get("indice"), (int, float))]
    verdicts = Counter(x["evaluation"].get("veredicto") for x in valid)
    requirements = [r for x in valid for r in x["central"].get("requerimientos", []) if isinstance(r, dict)]
    return {
        "descripcion_resultado": (
            "Evaluación asistida para apoyar el control, seguimiento y trazabilidad; no constituye "
            "certificación ni aceptación automática y requiere revisión humana."
        ),
        "revision_humana_requerida": True,
        "resultados": consolidated,
        "errores_validacion": validation_errors or [],
        "resumen_global": {
            "historias_solicitadas": len(expected_issue_ids),
            "historias_procesadas": len(valid),
            "historias_con_error": len(consolidated) - len(valid),
            "total_por_veredicto": dict(verdicts),
            "calidad_promedio": sum(quality_values) / len(quality_values) if quality_values else None,
            "seguridad_promedio": sum(security_values) / len(security_values) if security_values else None,
            "requerimientos_sugeridos": len(requirements),
        },
    }
