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


def _lista_metrica(metric: Dict[str, Any], canonical: str, *aliases: str) -> List[str]:
    for key in (canonical, *aliases):
        if key in metric:
            values, warnings = _normalizar_lista_evidencia(metric.get(key))
            if warnings:
                metric.setdefault("advertencias_tecnicas", []).extend(warnings)
            metric[canonical] = values
            for alias in aliases:
                if alias in metric:
                    metric[alias] = values
            return values
    metric[canonical] = []
    return []


def _invalidar_metrica(metric: Dict[str, Any], message: str, error: bool = False) -> None:
    metric.update({"estado_calculo": "No evaluado", "valor": None, "porcentaje": None, "calculo": "No evaluado"})
    key = "errores_validacion" if error else "advertencias_tecnicas"
    messages = metric.setdefault(key, [])
    if message not in messages:
        messages.append(message)
        logger.warning(message)


def _calcular_proporcion(
    metric: Dict[str, Any], numerator: int, denominator: int, formula: str,
    calculation: str, zero_message: str,
) -> None:
    if denominator < 0 or numerator < 0 or numerator > denominator:
        _invalidar_metrica(
            metric,
            f"Variables contradictorias: numerador={numerator}, denominador={denominator}.",
            error=True,
        )
    elif denominator == 0:
        metric.update({
            "estado_calculo": "No aplica", "valor": None, "porcentaje": None,
            "calculo": "No aplica",
        })
        if es_texto_invalido(metric.get("justificacion")):
            metric["justificacion"] = zero_message
    else:
        value = numerator / denominator
        metric.update({
            "estado_calculo": "Calculada", "formula": formula, "calculo": calculation,
            "valor": round(value, 4), "porcentaje": round(value * 100, 2),
        })


def _indicador(metricas: List[Dict[str, Any]], domain: str, lot: str | None = None) -> Dict[str, Any]:
    codes = ["MC-01", "MC-02"] if domain == "Calidad" else ["MS-01", "MS-02"]
    values = [metric.get("valor") for metric in metricas]
    name = "Índice de Calidad de Requerimientos" if domain == "Calidad" else "Índice de Seguridad en Requerimientos"
    result = {
        "nombre": name, "metricas_utilizadas": codes,
        "formula": f"({codes[0]} + {codes[1]}) / 2",
        "valor": None, "porcentaje": None, "estado": "No evaluado",
    }
    if domain == "Calidad":
        meta = 0.95
    else:
        result["lot"] = lot
        meta = {"LoT-2": 0.90, "LoT-3": 0.95}.get(lot)
    result["meta"] = meta
    result["meta_porcentaje"] = round(meta * 100, 2) if meta is not None else None
    if len(values) != 2 or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values):
        result["calculo"] = "No evaluado"
        result["recomendacion"] = "Completar la evidencia necesaria para calcular ambas métricas."
        return result
    if meta is None:
        result["calculo"] = f"({values[0]:.2f} + {values[1]:.2f}) / 2"
        result["recomendacion"] = "Determinar explícitamente un LoT-2 o LoT-3 antes de evaluar el índice."
        return result
    value = round((values[0] + values[1]) / 2, 4)
    result.update({
        "calculo": f"({values[0]:.2f} + {values[1]:.2f}) / 2",
        "valor": value, "porcentaje": round(value * 100, 2),
        "estado": "Cumple" if value >= meta else "No cumple",
    })
    recommendations = [
        metric.get("recomendacion", "").strip() for metric in metricas
        if isinstance(metric.get("recomendacion"), str) and metric.get("recomendacion", "").strip()
    ]
    result["recomendacion"] = (
        "Atender de forma conjunta las mejoras específicas de las métricas: " + " ".join(dict.fromkeys(recommendations))
        if recommendations else "Mantener la evidencia explícita que sustenta ambas métricas."
    )
    return result


def normalizar_metricas_resultado(item: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    """Normaliza evidencia y calcula métricas/indicador; fuente única para flujo, UI y PDF."""
    metrics = item.get("metricas")
    if isinstance(metrics, list):
        metrics = {str(metric.get("codigo", index)): metric for index, metric in enumerate(metrics) if isinstance(metric, dict)}
    if not isinstance(metrics, dict):
        metrics = {}
    if agent_name == "Calidad":
        mc1 = metrics.get("cobertura_funcional") or metrics.get("MC-01") or {}
        mc2 = metrics.get("adecuacion_funcional") or metrics.get("MC-02") or {}
        mc1 = mc1 if isinstance(mc1, dict) else {}
        mc2 = mc2 if isinstance(mc2, dict) else {}
        specified = _lista_metrica(mc1, "funciones_especificadas", "elementos_evaluados")
        included = _lista_metrica(mc1, "funciones_incluidas")
        missing = _lista_metrica(mc1, "funciones_faltantes", "elementos_con_problemas")
        mc1.update({
            "codigo": "MC-01", "nombre": "Cobertura Funcional",
            "variables": {"A_funciones_faltantes": len(missing), "B_total_funciones_especificadas": len(specified)},
            "formula": "1 - (A / B)",
        })
        specified_keys = {_clave_texto(x) for x in specified}
        invalid = [value for value in included + missing if _clave_texto(value) not in specified_keys]
        if mc1.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
            _invalidar_metrica(mc1, "La evidencia disponible no permite calcular MC-01.")
        elif invalid:
            _invalidar_metrica(mc1, f"Funciones fuera del universo especificado: {', '.join(invalid)}.", error=True)
        elif included:
            _calcular_proporcion(
                mc1, len(specified) - len(missing), len(specified), "1 - (A / B)",
                f"1 - ({len(missing)} / {len(specified)})",
                "No existen funciones especificadas que permitan aplicar la métrica.",
            )
        else:
            included = [value for value in specified if _clave_texto(value) not in {_clave_texto(x) for x in missing}]
            mc1["funciones_incluidas"] = included
            _calcular_proporcion(
                mc1, len(specified) - len(missing), len(specified), "1 - (A / B)",
                f"1 - ({len(missing)} / {len(specified)})",
                "No existen funciones especificadas que permitan aplicar la métrica.",
            )

        evaluated = _lista_metrica(mc2, "funciones_evaluables", "elementos_evaluados")
        aligned = _lista_metrica(mc2, "funciones_alineadas_detalle", "elementos_alineados")
        not_aligned = _lista_metrica(mc2, "funciones_no_alineadas", "elementos_con_problemas")
        ambiguous = _lista_metrica(mc2, "funciones_ambiguas")
        mc2.update({
            "codigo": "MC-02", "nombre": "Adecuación Funcional de Objetivos de Uso",
            "variables": {"funciones_alineadas": len(aligned), "funciones_evaluables": len(evaluated)},
            "formula": "Funciones alineadas / Funciones evaluables",
        })
        invalid = [value for value in aligned if _clave_texto(value) not in {_clave_texto(x) for x in evaluated}]
        if mc2.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
            _invalidar_metrica(mc2, "La evidencia disponible no permite calcular MC-02.")
        elif invalid:
            _invalidar_metrica(mc2, f"Funciones alineadas fuera del universo evaluable: {', '.join(invalid)}.", error=True)
        else:
            _calcular_proporcion(
                mc2, len(aligned), len(evaluated), mc2["formula"],
                f"{len(aligned)} / {len(evaluated)}",
                "No existen funciones evaluables para relacionarlas con el objetivo.",
            )
        mc2["funciones_no_alineadas"] = not_aligned
        mc2["funciones_ambiguas"] = ambiguous
        _asegurar_recomendacion(mc1, "cobertura_funcional")
        _asegurar_recomendacion(mc2, "adecuacion_funcional")
        canonical = {"cobertura_funcional": mc1, "adecuacion_funcional": mc2}
        indicator = _indicador([mc1, mc2], "Calidad")
    else:
        ms1 = metrics.get("cobertura_seguridad") or metrics.get("MS-01")
        ms2 = metrics.get("clasificacion_datos") or metrics.get("MS-02")
        legacy = bool(item.get("_seguridad_historica")) or ms1 is None or ms2 is None
        if legacy:
            item["_seguridad_historica"] = True
        ms1 = ms1 if isinstance(ms1, dict) else {}
        ms2 = ms2 if isinstance(ms2, dict) else {}
        applicable = _lista_metrica(ms1, "aspectos_aplicables")
        documented = _lista_metrica(ms1, "aspectos_documentados")
        partial = _lista_metrica(ms1, "aspectos_parciales")
        missing = _lista_metrica(ms1, "aspectos_faltantes")
        inferred = _lista_metrica(ms1, "aspectos_inferidos")
        ms1.update({
            "codigo": "MS-01", "nombre": "Cobertura de Requisitos de Seguridad Aplicables",
            "variables": {"requisitos_seguridad_documentados": len(documented), "aspectos_seguridad_aplicables": len(applicable)},
            "formula": "Requisitos documentados / Aspectos aplicables",
        })
        identified = _lista_metrica(ms2, "datos_identificados_detalle")
        classified_raw = ms2.get("datos_clasificados_detalle", [])
        classified = classified_raw if isinstance(classified_raw, list) else []
        classified_names = [
            str(value.get("dato", "")).strip() if isinstance(value, dict) else str(value).strip()
            for value in classified if (isinstance(value, dict) and value.get("dato")) or (isinstance(value, str) and value.strip())
        ]
        unclassified = _lista_metrica(ms2, "datos_sin_clasificacion")
        inferred_classes = _lista_metrica(ms2, "clasificaciones_inferidas")
        ms2.update({
            "codigo": "MS-02", "nombre": "Cobertura de Clasificación de Datos",
            "variables": {"datos_clasificados": len(classified_names), "datos_identificados": len(identified)},
            "formula": "Datos clasificados / Datos identificados",
            "datos_clasificados_detalle": classified,
            "datos_sin_clasificacion": unclassified,
            "clasificaciones_inferidas": inferred_classes,
        })
        if legacy:
            _invalidar_metrica(ms1, "El resultado histórico no contiene evidencia reconstruible para MS-01.")
            _invalidar_metrica(ms2, "El resultado histórico no contiene evidencia reconstruible para MS-02.")
        else:
            invalid = [value for value in documented if _clave_texto(value) not in {_clave_texto(x) for x in applicable}]
            if invalid:
                _invalidar_metrica(ms1, f"Aspectos documentados fuera del universo aplicable: {', '.join(invalid)}.", error=True)
            else:
                _calcular_proporcion(ms1, len(documented), len(applicable), ms1["formula"], f"{len(documented)} / {len(applicable)}", "No existen aspectos de seguridad aplicables.")
            invalid = [value for value in classified_names if _clave_texto(value) not in {_clave_texto(x) for x in identified}]
            if invalid:
                _invalidar_metrica(ms2, f"Datos clasificados fuera del universo identificado: {', '.join(invalid)}.", error=True)
            else:
                _calcular_proporcion(ms2, len(classified_names), len(identified), ms2["formula"], f"{len(classified_names)} / {len(identified)}", "No existen datos identificados que permitan aplicar la métrica.")
        ms1.update({"aspectos_parciales": partial, "aspectos_faltantes": missing, "aspectos_inferidos": inferred})
        lot = item.get("lot") or item.get("lot_recomendado")
        if not lot and isinstance(metrics.get("lot_asignado"), dict):
            lot = metrics["lot_asignado"].get("lot_recomendado")
        item["lot"] = lot
        item["lot_recomendado"] = lot
        canonical = {"cobertura_seguridad": ms1, "clasificacion_datos": ms2}
        indicator = _indicador([ms1, ms2], "Seguridad", lot)
    item["metricas"] = canonical
    item["indicador"] = indicator
    item["indice"] = indicator.get("valor")
    item["estado_medicion"] = "evaluable" if indicator.get("valor") is not None else "evidencia_insuficiente"
    item["meta_cumplida"] = indicator.get("estado") == "Cumple"
    item["recomendaciones"] = normalizar_lista_textos(item.get("recomendaciones"))
    return item


def calcular_metricas_agente(response: Dict[str, Any], agent_name: str) -> None:
    for item in response.get("resultados", []):
        if isinstance(item, dict) and agent_name in {"Calidad", "Seguridad"}:
            normalizar_metricas_resultado(item, agent_name)


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
                    if requirement.get("procedencia") not in {"extraido", "inferido", "recomendado"}:
                        current.append(f"requerimiento {index} tiene procedencia inválida")
        elif agent_name in {"Calidad", "Seguridad"}:
            metrics = item.get("metricas")
            expected_names = (
                ["cobertura_funcional", "adecuacion_funcional"] if agent_name == "Calidad"
                else ["cobertura_seguridad", "clasificacion_datos"]
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
                        (["funciones_especificadas", "funciones_incluidas", "funciones_faltantes"] if metric_name == "cobertura_funcional" else
                         ["funciones_evaluables", "funciones_alineadas_detalle", "funciones_no_alineadas"] if metric_name == "adecuacion_funcional" else
                         ["aspectos_aplicables", "aspectos_documentados", "aspectos_faltantes", "aspectos_inferidos"] if metric_name == "cobertura_seguridad" else
                         ["datos_identificados_detalle", "datos_clasificados_detalle", "datos_sin_clasificacion", "clasificaciones_inferidas"])
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
            item.setdefault("historia_id", f"HU-{iid:03d}")
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
            if requirement.get("procedencia") not in {"extraido", "inferido", "recomendado"}:
                requirement["procedencia"] = "inferido"


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
            reasons.append("Índice parcial de calidad bajo la meta de apoyo.")
        security_indicator = security.get("indicador") if isinstance(security.get("indicador"), dict) else {}
        if security_indicator.get("estado") == "No cumple":
            reasons.append("Índice de Seguridad en Requerimientos bajo la meta correspondiente al LoT.")
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
) -> Dict[str, Any]:
    maps = [indexar_resultados(x) for x in (central, quality, security, evaluation)]
    names = ["Central", "Calidad", "Seguridad", "Evaluador"]
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
