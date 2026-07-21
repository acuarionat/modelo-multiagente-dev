import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Set, Tuple

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
    return normalized in INVALID_TEXT_VALUES or any(fragment in normalized for fragment in GENERIC_TEXT_FRAGMENTS)


def _normalizar_lista_evidencia(values: Any) -> tuple[List[str], List[str]]:
    if not isinstance(values, list):
        return [], ["la evidencia no era una lista"]
    clean, warnings, seen = [], [], set()
    for value in values:
        if es_texto_invalido(value):
            warnings.append("se descartó evidencia vacía o genérica")
            continue
        text = " ".join(value.split()).strip()
        key = text.casefold()
        if key in seen:
            warnings.append(f"se eliminó evidencia duplicada: {text}")
            continue
        seen.add(key)
        clean.append(text)
    return clean, warnings


def _restringir_subconjunto(values: List[str], universe: List[str], label: str) -> tuple[List[str], List[str]]:
    by_key = {value.casefold(): value for value in universe}
    valid, removed = [], []
    for value in values:
        canonical = by_key.get(value.casefold())
        if canonical is None:
            removed.append(f"{label} fuera del universo evaluado: {value}")
        elif canonical not in valid:
            valid.append(canonical)
    return valid, removed


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


def calcular_metricas_agente(response: Dict[str, Any], agent_name: str) -> None:
    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        metrics = item.get("metricas")
        if not isinstance(metrics, dict):
            continue
        if agent_name == "Calidad":
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
            item["interpretacion_indice"] = "Índice parcial de apoyo para la revisión de calidad funcional."
        elif agent_name == "Seguridad":
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
            controls["interpretacion"] = "Cobertura documental estimada de controles de seguridad aplicables."
            lot["interpretacion"] = "Nivel de aseguramiento recomendado; no representa la confianza del modelo."
            item["interpretacion_indice"] = "Índice de cobertura documental de seguridad."


def validar_contenido_agente(response: Dict[str, Any], agent_name: str) -> Dict[int, List[str]]:
    errors: Dict[int, List[str]] = {}
    justifications: Dict[str, List[int]] = {}
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
                        (["elementos_evaluados", "elementos_con_problemas"] if metric_name == "cobertura_funcional" else
                         ["elementos_evaluados", "elementos_alineados"] if metric_name == "adecuacion_funcional" else
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
                        justifications.setdefault(justification.strip().casefold(), []).append(iid)
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
    for text, iids in justifications.items():
        unique_iids = sorted(set(iids))
        if len(unique_iids) > 1:
            for iid in unique_iids:
                errors.setdefault(iid, []).append("justificación repetida exactamente en varias historias")
    return errors


def recopilar_recomendaciones(result: Dict[str, Any]) -> List[str]:
    recommendations: List[str] = []
    for section in (result.get("quality") or {}, result.get("security") or {}):
        metrics = section.get("metricas", {})
        for metric in metrics.values() if isinstance(metrics, dict) else []:
            if isinstance(metric, dict) and not es_texto_invalido(metric.get("recomendacion")):
                recommendations.append(metric["recomendacion"].strip())
        recommendations.extend(x for x in section.get("recomendaciones", []) if not es_texto_invalido(x))
    evaluation = result.get("evaluation") or {}
    recommendations.extend(x for x in evaluation.get("correcciones_obligatorias", []) if not es_texto_invalido(x))
    central = result.get("central") or {}
    recommendations.extend(x for x in central.get("observaciones", []) if not es_texto_invalido(x))
    return list(dict.fromkeys(recommendations))


def construir_etiquetas_resultado(old_labels: list, estado_evaluacion: str, quality_index=None, security_index=None) -> list:
    """Calcula etiquetas coherentes sin crear etiquetas nuevas en GitLab."""
    removed = {"Pendiente", "En revisión", "Analizado", "Analizada", "Error de análisis"}
    labels = [
        label for label in old_labels
        if label not in removed and not label.startswith(("Calidad:", "Seguridad:", "Veredicto:"))
    ]
    labels.append("Analizada" if estado_evaluacion == "APROBADO" else "En revisión")
    if quality_index is not None:
        labels.append(f"Calidad:{round(quality_index * 100)} %")
    if security_index is not None:
        labels.append(f"Seguridad:{round(security_index * 100)} %")
    if estado_evaluacion != "NO_EVALUADO":
        labels.append(f"Veredicto:{estado_evaluacion}")
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


def renumerar_requerimientos(items: Iterable[Dict[str, Any]]) -> None:
    counters = {"RF": 0, "RNF": 0, "RS": 0, "RC": 0}
    for item in items:
        for requirement in item.get("requerimientos", []):
            if not isinstance(requirement, dict):
                continue
            kind = str(requirement.get("tipo", "RF")).upper()
            if kind not in counters:
                kind = "RF"
            counters[kind] += 1
            requirement["tipo"] = kind
            requirement["id"] = f"{kind}-{counters[kind]:03d}"
            requirement["descripcion"] = requirement.get("descripcion_formal")
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
        if isinstance(security.get("indice"), (int, float)) and security["indice"] < 0.85:
            reasons.append("Índice de cobertura documental de seguridad bajo la meta de apoyo.")
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
        errors.extend((content_validation_errors or {}).get(iid, []))
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
        if not errors:
            ajustar_veredicto_determinista(central_item, quality_item, security_item, evaluation_item, input_validation)
        estado_evaluacion = evaluation_item.get("veredicto", "NO_EVALUADO") if evaluation_item else "NO_EVALUADO"
        consolidated.append({
            "issue_iid": iid,
            "status": "error" if errors else "ok",
            "estado_procesamiento": "error" if errors else "completo",
            "estado_evaluacion": estado_evaluacion,
            "errors": errors,
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
