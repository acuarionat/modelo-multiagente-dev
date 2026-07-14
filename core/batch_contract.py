import json
from collections import Counter
from typing import Any, Dict, Iterable, List, Set, Tuple


def normalize_iid(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        text = str(value).strip().upper().removeprefix("HU-")
        return int(text)
    except (TypeError, ValueError):
        return None


def parse_batch_response(raw: Any, agent_name: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"{agent_name}: la respuesta no es JSON válido.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("resultados"), list):
        raise ValueError(f"{agent_name}: falta el arreglo 'resultados'.")
    return data


def reconcile_issue_ids(
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
        iid = normalize_iid(item.get("issue_iid"))
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
    returned_unresolved = [normalize_iid(item.get("issue_iid")) for _, item in unresolved]
    ordinal_map = {ordinal: iid for ordinal, iid in enumerate(expected, 1)}
    can_use_ordinals = (
        len(unresolved) == len(remaining)
        and all(iid in ordinal_map for iid in returned_unresolved)
        and len(set(returned_unresolved)) == len(returned_unresolved)
        and {ordinal_map[iid] for iid in returned_unresolved} == set(remaining)
    )
    if can_use_ordinals:
        for _, item in unresolved:
            old_iid = normalize_iid(item.get("issue_iid"))
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


def validate_batch_response(
    response: Dict[str, Any], expected_issue_ids: Set[int], agent_name: str
) -> List[str]:
    results = response["resultados"]
    errors: List[str] = []
    returned: List[int] = []
    for position, item in enumerate(results, 1):
        if not isinstance(item, dict):
            errors.append(f"{agent_name}: resultado {position} no es un objeto.")
            continue
        iid = normalize_iid(item.get("issue_iid"))
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


def index_results(response: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}
    for item in response.get("resultados", []):
        if isinstance(item, dict):
            iid = normalize_iid(item.get("issue_iid"))
            if iid is not None and iid not in indexed:
                indexed[iid] = item
    return indexed


def renumber_requirements(items: Iterable[Dict[str, Any]]) -> None:
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


def consolidate_batch(
    expected_issue_ids: Set[int], central: Dict[str, Any], quality: Dict[str, Any],
    security: Dict[str, Any], evaluation: Dict[str, Any], validation_errors: List[str] | None = None,
) -> Dict[str, Any]:
    maps = [index_results(x) for x in (central, quality, security, evaluation)]
    names = ["Central", "Calidad", "Seguridad", "Evaluador"]
    renumber_requirements(maps[0][iid] for iid in sorted(maps[0]))
    consolidated = []
    for iid in sorted(expected_issue_ids):
        missing = [name for name, mapping in zip(names, maps) if iid not in mapping]
        errors = [f"Falta la salida del Agente {name}." for name in missing]
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
