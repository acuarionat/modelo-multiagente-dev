import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Set, Tuple

INVALID_TEXT_VALUES = {"", "...", "n/a", "no especificado", "sin información"}
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
            expected = coverage.get("elementos_evaluados", [])
            missing = coverage.get("elementos_con_problemas", [])
            evaluated = adequacy.get("elementos_evaluados", [])
            aligned = adequacy.get("elementos_alineados", [])
            expected = expected if isinstance(expected, list) else []
            missing = missing if isinstance(missing, list) else []
            evaluated = evaluated if isinstance(evaluated, list) else []
            aligned = aligned if isinstance(aligned, list) else []
            coverage["valor"] = max(0.0, 1 - len(missing) / max(len(expected), 1))
            adequacy["valor"] = min(1.0, len(aligned) / max(len(evaluated), 1))
            item["indice"] = (coverage["valor"] + adequacy["valor"]) / 2
            item["meta_cumplida"] = item["indice"] >= 0.95
        elif agent_name == "Seguridad":
            controls = metrics.get("controles_seguridad", {})
            lot = metrics.get("lot_asignado", {})
            if not isinstance(controls, dict) or not isinstance(lot, dict):
                continue
            evaluated = controls.get("requerimientos_evaluados", [])
            with_controls = controls.get("requerimientos_con_controles", [])
            lot_evaluated = lot.get("requerimientos_evaluados", evaluated)
            with_lot = lot.get("requerimientos_con_lot_justificado", [])
            evaluated = evaluated if isinstance(evaluated, list) else []
            with_controls = with_controls if isinstance(with_controls, list) else []
            lot_evaluated = lot_evaluated if isinstance(lot_evaluated, list) else []
            with_lot = with_lot if isinstance(with_lot, list) else []
            controls["valor"] = min(1.0, len(with_controls) / max(len(evaluated), 1))
            lot["valor"] = min(1.0, len(with_lot) / max(len(lot_evaluated), 1))
            item["indice"] = (controls["valor"] + lot["valor"]) / 2
            item["meta_cumplida"] = item["indice"] >= 0.85
            item["lot_recomendado"] = lot.get("lot_recomendado")


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
                required = ["temp_id", "nombre", "descripcion_formal", "tipo", "origen", "justificacion", "prioridad"]
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
            if not isinstance(indice, (int, float)) or isinstance(indice, bool) or not 0 <= indice <= 1:
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


def consolidar_lote(
    expected_issue_ids: Set[int], central: Dict[str, Any], quality: Dict[str, Any],
    security: Dict[str, Any], evaluation: Dict[str, Any], validation_errors: List[str] | None = None,
    content_validation_errors: Dict[int, List[str]] | None = None,
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
                if not isinstance(index, (int, float)) or isinstance(index, bool) or not 0 <= index <= 1:
                    errors.append(f"El Agente de {name} devolvió un índice inválido.")
        if evaluation_item is not None and evaluation_item.get("veredicto") not in {"APROBADO", "CORREGIR", "ALERTA"}:
            errors.append("El Agente Evaluador devolvió un veredicto inválido.")
        consolidated.append({
            "issue_iid": iid,
            "status": "error" if errors else "ok",
            "errors": errors,
            "central": central_item,
            "quality": quality_item,
            "security": security_item,
            "evaluation": evaluation_item,
        })
    valid = [x for x in consolidated if x["status"] == "ok"]
    quality_values = [x["quality"]["indice"] for x in valid]
    security_values = [x["security"]["indice"] for x in valid]
    verdicts = Counter(x["evaluation"].get("veredicto") for x in valid)
    requirements = [r for x in valid for r in x["central"].get("requerimientos", []) if isinstance(r, dict)]
    return {
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
