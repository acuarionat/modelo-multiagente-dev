import json
import hashlib
import logging
import re
import unicodedata
from collections import Counter
from copy import deepcopy
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
ACRONIMOS_PRESENTACION = {"PDF", "API", "URL", "HTTP", "JSON", "RF", "RNF"}
CORRECCIONES_MAYUSCULAS_OBSERVADAS = {"CANCELLE": "cancele"}
CORRECCIONES_PRESENTACION_EXACTAS = {
    "El sistema deberá actualizar la disponibilidad después del paciente de haber programado una cita.":
        "El sistema deberá actualizar la disponibilidad después de que el paciente programe una cita.",
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


_VERBOS_FUNCIONALES = {
    "cancelar": "cancelar", "cancela": "cancelar", "cancele": "cancelar",
    "cancelacion": "cancelar",
    "registrar": "registrar", "registra": "registrar", "registro": "registrar",
    "consultar": "consultar", "consulta": "consultar",
    "mostrar": "consultar", "muestra": "consultar", "mostrarse": "consultar",
    "visualizar": "consultar", "visualiza": "consultar", "visualizacion": "consultar",
    "actualizar": "actualizar", "actualiza": "actualizar", "actualizarse": "actualizar",
    "actualizacion": "actualizar",
    "generar": "generar", "genera": "generar", "generacion": "generar",
    "exportar": "exportar", "exporta": "exportar", "exportacion": "exportar",
    "filtrar": "filtrar", "filtra": "filtrar", "filtrado": "filtrar",
    "validar": "validar", "valida": "validar", "validacion": "validar",
    "editar": "editar", "edita": "editar", "edicion": "editar",
    "imprimir": "imprimir", "imprime": "imprimir", "impresion": "imprimir",
    "impedir": "impedir", "impide": "impedir",
    "aprobar": "aprobar", "aprueba": "aprobar", "aprobacion": "aprobar",
    "calcular": "calcular", "calcula": "calcular", "calculo": "calcular",
}

_AUXILIARES_FUNCIONALES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "al", "en", "y", "o", "que", "se", "su", "sus", "como", "para", "por",
    "permitir", "permite", "puede", "podra", "poder", "debe", "debera",
    "sistema", "actor", "unicamente", "posteriormente",
}

_MORFOLOGIA_FUNCIONAL = {
    "citas": "cita", "medicas": "medica", "medicos": "medico",
    "horarios": "horario", "disponibles": "disponible",
    "pacientes": "paciente", "reportes": "reporte",
    "calendario": "agenda", "calendarios": "agenda",
    "existencia": "inventario", "existencias": "inventario",
}


def _firma_funcional(value: Any) -> tuple[str | None, tuple[str, ...]]:
    """Extrae acción y objeto sin estimar similitud ni cruzar historias."""
    tokens = _clave_texto(value).split()
    action_index = next((index for index, token in enumerate(tokens) if token in _VERBOS_FUNCIONALES), None)
    action = _VERBOS_FUNCIONALES[tokens[action_index]] if action_index is not None else None
    objects: List[str] = []
    for index, token in enumerate(tokens):
        if token in _AUXILIARES_FUNCIONALES or token in _VERBOS_FUNCIONALES:
            continue
        if token in {"paciente", "usuario"} and action_index is not None and index < action_index:
            continue
        normalized = _MORFOLOGIA_FUNCIONAL.get(token, token)
        if normalized.endswith("es") and len(normalized) > 5:
            normalized = normalized[:-2]
        elif normalized.endswith("s") and len(normalized) > 4:
            normalized = normalized[:-1]
        if normalized not in objects:
            objects.append(normalized)
    return action, tuple(objects)


def funciones_equivalentes(left: Any, right: Any) -> bool:
    """Compara una función por acción y objeto compuesto, dentro de una HU."""
    if _clave_texto(left) == _clave_texto(right):
        return True
    left_action, left_objects = _firma_funcional(left)
    right_action, right_objects = _firma_funcional(right)
    if not left_action or left_action != right_action or not left_objects or not right_objects:
        return False
    left_core = set(left_objects)
    right_core = set(right_objects)
    if left_action == "consultar":
        def agenda_core(values: Set[str]) -> Set[str]:
            normalized = set(values)
            if "cita" in normalized:
                normalized.remove("cita")
                normalized.add("agenda")
                normalized.discard("dia")
            return normalized
        left_agenda = agenda_core(left_core)
        right_agenda = agenda_core(right_core)
        if (
            "agenda" in left_agenda and "agenda" in right_agenda
            and left_agenda <= {"agenda", "medica", "medico"}
            and right_agenda <= {"agenda", "medica", "medico"}
        ):
            return True
    if len(left_objects) == 1 and left_objects[0] in right_core:
        return True
    if len(right_objects) == 1 and right_objects[0] in left_core:
        return True
    if left_objects[0] != right_objects[0]:
        return False
    # El objeto principal debe coincidir; los complementos pueden ampliar una
    # redacción, pero nunca sustituirlo por otro comportamiento funcional.
    return bool(left_core & right_core)


def _restringir_funciones(
    values: List[str], universe: List[str], label: str,
    representations: Dict[str, List[str]] | None = None,
) -> tuple[List[str], List[str]]:
    valid, removed = [], []
    for value in values:
        canonical = next(
            (
                candidate for candidate in universe
                if any(
                    funciones_equivalentes(value, representation)
                    for representation in (representations or {}).get(candidate, [candidate])
                )
            ),
            None,
        )
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


def normalizar_capitalizacion_requerimiento(texto: Any) -> Any:
    """Corrige palabras enfáticas en mayúsculas conservando acrónimos técnicos."""
    if not isinstance(texto, str):
        return texto
    texto = CORRECCIONES_PRESENTACION_EXACTAS.get(texto, texto)
    texto = re.sub(
        r"\bel nombre y especialidad\b", "el nombre y la especialidad", texto,
        flags=re.IGNORECASE,
    )
    subjuntivos = {
        "cancela": "cancele", "registra": "registre", "genera": "genere",
        "solicita": "solicite", "actualiza": "actualice", "consulta": "consulte",
        "muestra": "muestre", "exporta": "exporte", "filtra": "filtre",
        "valida": "valide", "edita": "edite", "imprime": "imprima",
    }

    def corregir_permitir_que(match: re.Match[str]) -> str:
        prefix, verb = match.group(1), match.group(2)
        replacement = subjuntivos.get(verb.casefold(), verb)
        return prefix + replacement

    texto = re.sub(
        r"(\bpermitir\s+que\s+(?:(?:el|la|los|las)\s+)?(?:[\wáéíóúüñ-]+\s+){0,4}?)("
        + "|".join(subjuntivos)
        + r")\b",
        corregir_permitir_que, texto, flags=re.IGNORECASE,
    )

    def reemplazar(match: re.Match[str]) -> str:
        word = match.group(0)
        if word in CORRECCIONES_MAYUSCULAS_OBSERVADAS:
            return CORRECCIONES_MAYUSCULAS_OBSERVADAS[word]
        return word if word in ACRONIMOS_PRESENTACION else word.lower()

    return re.sub(r"\b[A-ZÁÉÍÓÚÜÑ]{2,}\b", reemplazar, texto)


def normalizar_presentacion_requerimientos(requirements: Any) -> Any:
    """Normaliza una vez el texto consolidado consumido por todas las salidas."""
    if not isinstance(requirements, list):
        return requirements
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for field in ("nombre", "descripcion_formal", "descripcion"):
            if field in requirement:
                requirement[field] = normalizar_capitalizacion_requerimiento(requirement[field])
    return requirements


def _tipo_desde_texto(text: str) -> str:
    key = _clave_texto(text)
    if "cancel" in key and "24 horas" in key:
        return "RF"
    if "actualizar" in key and "disponibilidad" in key and "tiempo real" not in key:
        return "RF"
    return "RNF" if any(marker in key for marker in (
        "menos de", "maximo de", "dentro de", "inferior a", "segundo",
        "tiempo de respuesta", "en tiempo real",
        "rendimiento", "garantizar disponibilidad", "actualizacion inmediata",
        "seguridad", "usabilidad", "confiabilidad", "compatibilidad", "mantenibilidad",
    )) else "RF"


def _tipo_efectivo_requerimiento(requirement: Dict[str, Any]) -> str:
    content = " ".join(str(requirement.get(field) or "") for field in (
        "nombre", "descripcion_formal", "descripcion",
    ))
    inferred = _tipo_desde_texto(content)
    declared = normalizar_tipo_requerimiento(requirement.get("tipo"))
    return inferred if declared and declared != inferred else declared or inferred


def es_funcion_principal_evaluable(
    requirement: Dict[str, Any], funcionalidad_principal: Any = "",
) -> bool:
    """Distingue capacidades principales de reglas RF que sólo las condicionan."""
    if not isinstance(requirement, dict) or _tipo_efectivo_requerimiento(requirement) != "RF":
        return False
    text = " ".join(str(requirement.get(field) or "") for field in (
        "nombre", "descripcion_formal", "descripcion", "origen",
    ))
    key = _clave_texto(text)
    conditional = bool(re.search(r"\b(?:cuando|si|sin|menos de|siempre que)\b", key))
    blocking = any(marker in key for marker in (
        "impedir", "no permitir", "restringir", "limitar", "bloquear",
    ))
    main_action, _ = _firma_funcional(funcionalidad_principal)
    actions = set()
    for token in key.split():
        candidates = [token]
        for suffix in ("las", "los", "la", "lo", "se"):
            if token.endswith(suffix) and len(token) > len(suffix) + 3:
                candidates.append(token[:-len(suffix)])
        actions.update(
            _VERBOS_FUNCIONALES[candidate]
            for candidate in candidates if candidate in _VERBOS_FUNCIONALES
        )
    mentions_main_action = bool(main_action) and main_action in actions
    return not (conditional and blocking and mentions_main_action)


def obtener_universo_funcional_calidad(
    resultado_preparado: Dict[str, Any], issue_original: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Construye o recupera la fuente única del universo MC-01/MC-02."""
    requirements = resultado_preparado.get("requerimientos")
    if not isinstance(requirements, list):
        requirements = resultado_preparado.get("requerimientos_preparados", [])
    requirements = [item for item in requirements if isinstance(item, dict)]
    explicit_main = resultado_preparado.get("funciones_principales_evaluables")
    explicit_rules = resultado_preparado.get("reglas_funcionales_contextuales")
    functionality = str(
        (issue_original or {}).get("funcionalidad")
        or resultado_preparado.get("funcionalidad") or ""
    ).strip()

    if isinstance(explicit_main, list) and isinstance(explicit_rules, list):
        main_before_dedup = normalizar_lista_textos(explicit_main)
        rules = normalizar_lista_textos(explicit_rules)
    else:
        main_before_dedup, rules = [], []
        for requirement in requirements:
            if normalizar_tipo_requerimiento(requirement) != "RF":
                continue
            name = str(requirement.get("nombre") or requirement.get("descripcion_formal") or "").strip()
            if not name:
                continue
            target = main_before_dedup if es_funcion_principal_evaluable(requirement, functionality) else rules
            if name not in target:
                target.append(name)

    main: List[str] = []
    source_indices: List[List[int]] = []
    for source_index, candidate in enumerate(main_before_dedup):
        match_index = next((
            index for index, canonical in enumerate(main)
            if funciones_equivalentes(candidate, canonical)
        ), None)
        if match_index is None:
            main.append(candidate)
            source_indices.append([source_index])
        else:
            source_indices[match_index].append(source_index)

    evidence_groups = []
    for canonical_index, indices in enumerate(source_indices):
        related = [
            requirement for requirement in requirements
            if any(funciones_equivalentes(
                main_before_dedup[index],
                str(requirement.get("nombre") or requirement.get("descripcion_formal") or ""),
            ) for index in indices)
        ]
        evidence_groups.append({
            "canonical_index": canonical_index,
            "source_indices": indices,
            "requirement_ids": [
                str(item.get("id") or item.get("temp_id"))
                for item in related if item.get("id") or item.get("temp_id")
            ],
            "origin_hashes": [
                hashlib.sha256(_clave_texto(item.get("origen")).encode("utf-8")).hexdigest()[:12]
                for item in related if str(item.get("origen") or "").strip()
            ],
            "procedencias": list(dict.fromkeys(
                str(item.get("procedencia")) for item in related
                if str(item.get("procedencia") or "").strip()
            )),
        })
    return {
        "funciones_principales_evaluables": main,
        "reglas_funcionales_contextuales": rules,
        "evidencias_funciones_equivalentes": evidence_groups,
        "documentary_rf_count": sum(normalizar_tipo_requerimiento(item) == "RF" for item in requirements),
        "documentary_rnf_count": sum(normalizar_tipo_requerimiento(item) == "RNF" for item in requirements),
        "main_functions_before_dedup": len(main_before_dedup),
        "main_functions_after_dedup": len(main),
        "equivalent_functions_merged": len(main_before_dedup) - len(main),
        "main_function_count": len(main),
        "conditional_rule_count": len(rules),
    }


def _descripcion_requerimiento_explicito(text: str, actor: str = "") -> str:
    clean = text.strip().strip("-*• ").rstrip(".")
    key = _clave_texto(clean)
    if "reportes deben poder imprimirse" in key:
        return "El sistema deberá permitir imprimir los reportes."
    timing = re.search(
        r"(?:responder|completar(?:se)?|procesar|finalizar).{0,60}?(menos\s+de|(?:un\s+)?m[aá]ximo\s+de|dentro\s+de|inferior\s+a)\s+(.+?segundos?)",
        clean, flags=re.IGNORECASE,
    )
    if not timing and "tiempo de respuesta" in key:
        timing = re.search(
            r"(?:menos\s+de|menor\s+a|(?:un\s+)?m[aá]ximo\s+de|dentro\s+de|inferior\s+a)\s+(.+?segundos?)",
            clean, flags=re.IGNORECASE,
        )
        if timing:
            limit = timing.group(0).lower()
            limit = re.sub(r"^menor\s+a\b", "menos de", limit, flags=re.IGNORECASE)
            return f"El sistema deberá responder a la consulta en {limit}."
    if timing:
        limit = f"{timing.group(1).lower()} {timing.group(2).lower()}"
        if "consulta" in key:
            return f"El sistema deberá responder a la consulta en {limit}."
        if "operacion" in key:
            return f"El sistema deberá completar la operación en {limit}."
        if "procesamiento" in key:
            return f"El sistema deberá finalizar el procesamiento {limit}."
        return f"El sistema deberá completar el procesamiento en {limit}."
    if "tiempo real" in key:
        temporal = re.match(
            r"(?:la|el|los|las)\s+(.+?)\s+deber(?:á|a|án|an)\s+(actualizarse|mostrarse)\s+en\s+tiempo\s+real$",
            clean, flags=re.IGNORECASE,
        )
        if temporal:
            verb = "actualizar" if temporal.group(2).casefold().startswith("actual") else "mostrar"
            return f"El sistema deberá {verb} {temporal.group(1)} en tiempo real."
    if "cancel" in key and "24 horas" in key:
        return (
            "El sistema deberá impedir la cancelación de una cita cuando falten menos "
            "de 24 horas para su realización."
        )
    if clean.casefold().startswith("el sistema deberá"):
        return f"{clean}."
    coordinated = re.match(r"mostrar\s+nombre\s+y\s+especialidad(.*)$", clean, flags=re.IGNORECASE)
    if coordinated:
        return f"El sistema deberá mostrar el nombre y la especialidad{coordinated.group(1)}."
    sequence = re.match(r"(.+?)\s+despu[eé]s\s+de\s+([a-záéíóúñ]+)(.*)$", clean, flags=re.IGNORECASE)
    if sequence and actor and sequence.group(2).casefold().endswith(("ar", "er", "ir")):
        infinitive = sequence.group(2).casefold()
        conjugated = infinitive[:-2] + ("e" if infinitive.endswith("ar") else "a")
        action = sequence.group(1)[:1].lower() + sequence.group(1)[1:]
        return (
            f"El sistema deberá {action} después de que el {actor.strip().casefold()} "
            f"{conjugated}{sequence.group(3)}."
        )
    obligation = re.match(r"(?:el|la|los|las)\s+(.+?)\s+deber(?:á|a|án|an)\s+(.+)$", clean, flags=re.IGNORECASE)
    if obligation:
        action = re.sub(r"^(actualizar|mostrar)se\b", r"\1", obligation.group(2), flags=re.IGNORECASE)
        return f"El sistema deberá {action} {obligation.group(1)}."
    return f"El sistema deberá {clean[:1].lower() + clean[1:]}."


def completar_requerimientos_explicitos_faltantes(
    requerimientos_central: Any, issue_original: Dict[str, Any],
    diagnostico: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Conserva la salida válida del Central y añade evidencia explícita omitida."""
    requirements = (
        [item for item in requerimientos_central if isinstance(item, dict)]
        if isinstance(requerimientos_central, list) else []
    )
    candidates: List[tuple[str, str]] = []

    def add_candidate(text: str, origin_kind: str) -> None:
        clean = str(text or "").strip().strip("-*• ")
        key = _clave_texto(clean)
        if not clean or _es_no_definido(clean) or key in {"si", "no", "ninguna", "ninguno"}:
            return
        if "tiempo real" in key and any(action in key for action in ("actualizar", "actualizacion", "actualizarse")):
            base = re.sub(r"\s+en\s+tiempo\s+real\b", "", clean, flags=re.IGNORECASE).strip(" .")
            if base and _clave_texto(base) != key:
                candidates.append((base, origin_kind))
        candidates.append((clean, origin_kind))

    functionality = str(issue_original.get("funcionalidad") or "").strip()
    if functionality and not _es_no_definido(functionality):
        add_candidate(functionality, "funcionalidad")
    for text in normalizar_lista_textos(issue_original.get("criterios_aceptacion")):
        add_candidate(text, "criterio de aceptación")
    for text in normalizar_lista_textos(issue_original.get("restricciones")):
        add_candidate(text, "restricción")
    observations = normalizar_lista_textos(issue_original.get("observaciones"))
    for observation in observations:
        for text in (part.strip(" -*•") for part in re.split(r"[\r\n]+", observation)):
            key = _clave_texto(text)
            if text and not _es_no_definido(text) and any(marker in key for marker in (
                "imprimir", "editar", "actualizar", "tiempo de respuesta",
                "en tiempo real", "mostrar", "registrar", "permitir", "impedir",
                "consultar", "generar", "exportar", "filtrar", "validar", "calcular",
                "responder", "completar", "procesar", "tiempo de respuesta",
            )):
                add_candidate(text, "observación")

    def semantic_key(value: Any) -> Set[str]:
        normalized = _clave_texto(value)
        replacements = {
            "imprimirse": "imprimir", "impresion": "imprimir",
            "mostrada": "mostrar", "mostrarse": "mostrar",
            "actualizada": "actualizar", "actualizacion": "actualizar",
            "edicion": "editar", "validacion": "validar",
            "cancelacion": "cancelar", "cancele": "cancelar",
        }
        ignored = {
            "el", "la", "los", "las", "un", "una", "de", "del", "al", "en",
            "y", "que", "se", "debe", "debera", "sistema", "permitir", "poder",
            "paciente", "usuario", "medica", "medico", "puede", "su", "no", "podra",
        }
        return {replacements.get(word, word) for word in normalized.split() if word not in ignored}

    def requirement_text(requirement: Dict[str, Any]) -> str:
        return " ".join(str(requirement.get(field) or "") for field in (
            "nombre", "descripcion_formal", "descripcion",
        ))

    def representations(requirement: Dict[str, Any]) -> List[str]:
        return [
            str(requirement.get(field) or "").strip()
            for field in ("nombre", "descripcion_formal", "descripcion", "origen")
            if str(requirement.get(field) or "").strip()
        ]

    def trace(event: str, text: str, origin_kind: str, **details: Any) -> None:
        if diagnostico is None:
            return
        action, objects = _firma_funcional(text)
        diagnostico.append({
            "event": event,
            "source_id": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
            "source_kind": origin_kind,
            "normalized_type": _tipo_desde_texto(text),
            "functional_signature": {"action": action, "objects": list(objects)},
            **details,
        })

    def covers(requirement: Dict[str, Any], source_text: str, origin_kind: str) -> bool:
        requirement_value = requirement_text(requirement)
        source_key = _clave_texto(source_text)
        requirement_key = _clave_texto(requirement_value)
        rule_markers = ("impedir", "no se podra", "sin ", "menos de", "menor a")
        if any(marker in requirement_key for marker in rule_markers) and not any(
            marker in source_key for marker in rule_markers
        ):
            return False
        source_type = _tipo_desde_texto(source_text)
        if _tipo_efectivo_requerimiento(requirement) != source_type:
            return False
        if source_key and source_key in _clave_texto(requirement.get("origen")):
            return True
        if source_type == "RNF" and "tiempo real" in source_key and "tiempo real" not in requirement_key:
            return False
        current_kind = str(requirement.get("procedencia") or "").split("—")[-1].strip()
        source_action, _ = _firma_funcional(source_text)
        name_action, _ = _firma_funcional(requirement.get("nombre"))
        functional_words = set(_VERBOS_FUNCIONALES)
        source_surface = next((word for word in _clave_texto(source_text).split() if word in functional_words), None)
        name_surface = next((word for word in _clave_texto(requirement.get("nombre")).split() if word in functional_words), None)
        if (
            origin_kind == "criterio de aceptación"
            and current_kind == "funcionalidad"
            and source_action == name_action == "consultar"
            and source_surface in {"mostrar", "muestra", "mostrarse"}
            and name_surface in {"consultar", "consulta"}
            and "horario" in set(
                _firma_funcional(source_text)[1] + _firma_funcional(requirement.get("nombre"))[1]
            )
        ):
            return False
        if any(funciones_equivalentes(source_text, value) for value in representations(requirement)):
            return True
        represented_actions = [_firma_funcional(value)[0] for value in representations(requirement)]
        if source_action and any(represented_actions):
            return False
        source_words = semantic_key(source_text)
        return any(
            bool(source_words) and source_words.issubset(semantic_key(value))
            for value in representations(requirement)
        )

    for text, origin_kind in candidates:
        matches = [requirement for requirement in requirements if covers(requirement, text, origin_kind)]
        same_origin = [
            requirement for requirement in matches
            if str(requirement.get("procedencia") or "").split("—")[-1].strip() == origin_kind
        ]
        if same_origin:
            matches = same_origin[:1]
        elif matches:
            matches = matches[:1]
        if matches:
            trace(
                "source_merged_into_requirement", text, origin_kind,
                target_index=requirements.index(matches[0]), rule="same_type_action_and_compound_object",
            )
            for requirement in matches:
                source_type = _tipo_desde_texto(text)
                requirement["tipo"] = source_type
                source = text.strip()
                previous_origin = str(requirement.get("origen") or "").strip()
                if source and _clave_texto(source) not in _clave_texto(previous_origin):
                    requirement["origen"] = "; ".join(x for x in (previous_origin, source) if x)
                provenance_rank = {
                    "funcionalidad": 0, "criterio de aceptación": 1,
                    "observación": 2, "restricción": 3,
                }
                current_kind = str(requirement.get("procedencia") or "").split("—")[-1].strip()
                if (
                    requirement.get("procedencia") not in PROCEDENCIAS_VALIDAS
                    or requirement.get("procedencia") == "inferida"
                    or provenance_rank.get(origin_kind, 9) < provenance_rank.get(current_kind, 9)
                ):
                    requirement["procedencia"] = f"explícita — {origin_kind}"
                malformed_description = str(requirement.get("descripcion_formal") or "")
                if source_type == "RF" and (
                    "despues del" in _clave_texto(malformed_description)
                    or re.search(
                        r"\b(?:mostrar|consultar|registrar|actualizar)(?=[a-záéíóúñ])",
                        malformed_description, flags=re.IGNORECASE,
                    )
                ):
                    requirement["descripcion_formal"] = _descripcion_requerimiento_explicito(
                        text, str(issue_original.get("actor") or ""),
                    )
            continue
        if requirements:
            trace(
                "merge_rejected", text, origin_kind,
                rejection_reason="no_same_type_action_and_compound_object",
            )
        source_type = _tipo_desde_texto(text)
        name = text.strip().rstrip(".")
        if source_type == "RNF" and any(marker in _clave_texto(text) for marker in (
            "responder", "completar", "procesar", "tiempo de respuesta",
        )):
            name = "Tiempo de respuesta de la consulta" if "consulta" in _clave_texto(text) else "Tiempo de respuesta"
        elif source_type == "RNF" and "tiempo real" in _clave_texto(text):
            name = (
                "Disponibilidad de información en tiempo real"
                if "disponibilidad" in _clave_texto(text) else "Información en tiempo real"
            )
        requirements.append({
            "nombre": name,
            "descripcion_formal": _descripcion_requerimiento_explicito(
                text, str(issue_original.get("actor") or ""),
            ),
            "tipo": source_type,
            "origen": text.strip(),
            "justificacion": f"Formalizado desde texto explícito de {origin_kind}.",
            "prioridad": issue_original.get("prioridad"),
            "procedencia": f"explícita — {origin_kind}",
        })
        trace(
            "source_created_requirement", text, origin_kind,
            target_index=len(requirements) - 1, rule="no_equivalent_requirement_found",
        )
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
        f"{nombre}: A={len(faltantes)} funciones faltantes y B={total} funciones especificadas. "
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
    prepared_requirements = context.get("requerimientos_preparados", []) if context else []
    universe_source = {"requerimientos_preparados": prepared_requirements}
    if context:
        universe_source["funciones_principales_evaluables"] = context.get("funciones_principales_evaluables")
        universe_source["reglas_funcionales_contextuales"] = context.get("reglas_funcionales_contextuales")
    universe = obtener_universo_funcional_calidad(universe_source, context)
    functional_universe = list(universe["funciones_principales_evaluables"])
    representations: Dict[str, List[str]] = {}
    for requirement in prepared_requirements:
        canonical = str(requirement.get("nombre") or requirement.get("descripcion_formal") or "").strip()
        if canonical not in functional_universe:
            continue
        if not canonical:
            continue
        variants = [canonical]
        variants.extend(
            str(requirement.get(field) or "").strip()
            for field in ("descripcion_formal", "descripcion")
            if str(requirement.get(field) or "").strip()
        )
        variants.extend(
            value.strip() for value in str(requirement.get("origen") or "").split(";")
            if value.strip()
        )
        representations[canonical] = list(dict.fromkeys(variants))
    explicit_sources = []
    if context:
        explicit_sources.extend(normalizar_lista_textos(context.get("funcionalidad")))
        explicit_sources.extend(normalizar_lista_textos(context.get("criterios_aceptacion")))
    for source in explicit_sources:
        matching = [
            canonical for canonical, variants in representations.items()
            if any(funciones_equivalentes(source, variant) for variant in variants)
        ]
        if len(matching) == 1 and source not in representations[matching[0]]:
            representations[matching[0]].append(source)
    if functional_universe:
        specified, universe_notes = _restringir_funciones(
            specified, functional_universe, "función especificada", representations,
        )
        mc01["funciones_especificadas"] = specified
        if universe_notes:
            mc01.setdefault("advertencias_tecnicas", []).extend(universe_notes)
    included, notes = _restringir_funciones(
        mc01["funciones_incluidas"], specified, "función incluida", representations,
    )
    _reported_missing, missing_notes = _restringir_funciones(
        mc01["funciones_faltantes"], specified, "función faltante", representations,
    )
    classified = bool(mc01["funciones_incluidas"] or mc01["funciones_faltantes"])
    missing = [function for function in specified if function not in included] if classified else []
    mc01["funciones_incluidas"] = included
    mc01["funciones_faltantes"] = missing
    if notes or missing_notes:
        mc01.setdefault("advertencias_tecnicas", []).extend(notes + missing_notes)

    # MC-02 usa exactamente el universo de MC-01; el agente solo aporta alineación.
    evaluable = list(specified)
    aligned, alignment_notes = _restringir_funciones(
        mc02["funciones_alineadas"], evaluable, "función alineada", representations,
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


def obtener_universo_datos_seguridad(
    issue_original: Dict[str, Any] | None,
    evidencia_seguridad: Dict[str, Any] | None = None,
) -> List[str]:
    """Obtiene identidades concretas únicamente desde la evidencia original."""
    issue = issue_original if isinstance(issue_original, dict) else {}
    evidence = evidencia_seguridad if isinstance(evidencia_seguridad, dict) else None
    if evidence is None:
        evidence = issue.get("evidencia_seguridad")
    if not isinstance(evidence, dict):
        evidence = issue.get("seguridad")
    evidence = evidence if isinstance(evidence, dict) else {}
    sensitive_marker = _clave_texto(evidence.get("maneja_datos_sensibles"))
    if sensitive_marker in {"no", "no definido", "no definida"}:
        return []
    values = evidence.get("tipos_datos_sensibles")
    if isinstance(values, dict):
        values = [{"dato": datum, "clasificacion": category} for datum, category in values.items()]
    elif not isinstance(values, list):
        values = []
    universe: List[str] = []
    seen: Set[str] = set()
    for value in values:
        normalized_value = value
        if isinstance(value, str):
            normalized_value = re.sub(
                r"^\s*(?:\[[ xX]\]\s*)?(?:sí|si|no)\b\s*:?\s*", "", value,
                flags=re.IGNORECASE,
            )
        identity = extraer_identidad_dato(normalized_value)
        if identity["data_identity_extracted"] and identity["signature"] not in seen:
            universe.append(identity["identity"])
            seen.add(identity["signature"])
    return universe


def descartar_grupos_genericos_sin_datos_canonicos(
    response: Dict[str, Any], prepared_input: Dict[str, Any],
) -> List[int]:
    """Descarta agrupaciones del LLM cuando la evidencia no aporta datos concretos.

    No flexibiliza la validación para historias que sí tienen datos canónicos:
    en esos casos las agrupaciones genéricas siguen siendo un error semántico.
    """
    sources = {
        normalizar_iid(item.get("issue_iid")): item
        for item in prepared_input.get("resultados", [])
        if isinstance(item, dict) and normalizar_iid(item.get("issue_iid")) is not None
    }
    generic_groups = {
        _clave_texto(value) for value in (
            "datos personales", "información sensible", "datos identificativos", "datos sensibles",
        )
    }
    normalized_issues = []
    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        source = sources.get(iid, {})
        evidence = source.get("evidencia_seguridad", {}) if isinstance(source, dict) else {}
        if obtener_universo_datos_seguridad(source, evidence):
            continue
        metrics = item.get("metricas", {})
        ms02 = metrics.get("clasificacion_datos", {}) if isinstance(metrics, dict) else {}
        if not isinstance(ms02, dict):
            continue
        removed = False
        for field in (
            "datos_identificados", "datos_clasificados", "datos_sin_clasificacion", "clasificaciones_inferidas",
        ):
            values = ms02.get(field)
            if not isinstance(values, list):
                continue
            filtered = [
                value for value in values
                if extraer_identidad_dato(value).get("signature") not in generic_groups
            ]
            if len(filtered) != len(values):
                ms02[field] = filtered
                removed = True
        if removed and iid is not None:
            normalized_issues.append(iid)
    return normalized_issues


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
    has_sensitive_data = bool(normalized_sensitive and not normalized_sensitive.startswith("no"))
    if has_sensitive_data:
        applicable.append("Protección de datos")
        documented.append("Protección de datos")

    def clean_datum(value: Any) -> str:
        clean = re.sub(
            r"^\s*(?:\[[ xX]\]\s*)?(?:sí|si|no)\b\s*:?\s*", "", str(value),
            flags=re.IGNORECASE,
        )
        return clean.strip().strip(".- ")

    explicit_types = security.get("tipos_datos_sensibles")
    source_values = (
        explicit_types if isinstance(explicit_types, list) and explicit_types
        else re.split(r"[\n,;]+", sensitive_text)
    )
    data = obtener_universo_datos_seguridad(context, security) if has_sensitive_data else []
    classified = []
    for value in source_values:
        clean = clean_datum(value)
        match = re.search(
            r"(?:^|:|→|->)\s*(PERSONAL|SENSIBLE|CLÍNICO|SALUD|BIOMÉTRICO|FINANCIERO)\s*$",
            clean, flags=re.IGNORECASE,
        )
        if match:
            datum = re.split(r"\s*(?::|→|->)\s*", clean, maxsplit=1)[0].strip()
            classified.append(f"{datum} → {match.group(1).upper()}")
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
    ms01_lists_valid = all(isinstance(ms01.get(field), list) for field in (
        "aspectos_aplicables", "aspectos_documentados", "aspectos_parciales",
        "aspectos_faltantes", "aspectos_inferidos",
    ))
    ms02_lists_valid = all(isinstance(ms02.get(field), list) for field in (
        "datos_identificados", "datos_clasificados", "datos_sin_clasificacion",
        "clasificaciones_inferidas",
    ))
    _preparar_metrica(ms01, [
        "aspectos_aplicables", "aspectos_documentados", "aspectos_parciales",
        "aspectos_faltantes", "aspectos_inferidos",
    ])
    _preparar_metrica(ms02, [
        "datos_identificados", "datos_clasificados", "datos_sin_clasificacion",
        "clasificaciones_inferidas",
    ])
    if context:
        context_applicable, context_documented, context_identified, context_classified = _evidencia_seguridad_contexto(context)
        ms01["aspectos_aplicables"] = context_applicable
        ms01["aspectos_documentados"] = context_documented
        ms01["aspectos_faltantes"] = [
            value for value in ms01["aspectos_aplicables"]
            if value not in ms01["aspectos_documentados"]
        ]

        def datum_name(value: Any) -> str:
            return re.split(r"\s*(?::|→|->)\s*", str(value), maxsplit=1)[0].strip()

        if context_identified:
            ms02["datos_identificados"] = context_identified
        elif not ms02_lists_valid:
            ms02["datos_identificados"] = []

        explicit_by_name = {
            _clave_texto(datum_name(value)): value for value in context_classified
        }
        formal_text = _clave_texto(context.get("requerimientos", []))
        for value in ms02["datos_identificados"]:
            name = datum_name(value)
            key = _clave_texto(name)
            if key and key in formal_text:
                category = next((category for category in (
                    "PERSONAL", "SENSIBLE", "CLINICO", "SALUD", "BIOMETRICO", "FINANCIERO",
                ) if category.casefold() in formal_text), None)
                if category:
                    explicit_by_name.setdefault(key, f"{name} → {category}")

        inferred = list(ms02["clasificaciones_inferidas"])
        for value in ms02["datos_clasificados"]:
            name = datum_name(value)
            key = _clave_texto(name)
            if key not in explicit_by_name:
                suggestion = str(value).replace(":", " →", 1)
                if suggestion not in inferred:
                    inferred.append(suggestion)
        ms02["datos_clasificados"] = list(explicit_by_name.values())
        ms02["clasificaciones_inferidas"] = inferred
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
    classified_names = {
        _clave_texto(re.split(r"\s*(?::|→|->)\s*", str(value), maxsplit=1)[0])
        for value in classified
    }
    unclassified = [x for x in identified if _clave_texto(x) not in classified_names]
    ms02["datos_sin_clasificacion"] = unclassified
    ms02["justificacion"] = (
        "MS-02: No aplica porque la historia no identifica datos." if not identified else
        f"MS-02: {len(classified)} de {len(identified)} datos identificados tienen "
        f"clasificación explícita. Clasificados explícitamente: "
        f"{', '.join(classified) if classified else 'ninguno'}. Sin clasificación explícita: "
        f"{', '.join(unclassified) if unclassified else 'ninguno'}. Clasificaciones sugeridas: "
        f"{', '.join(ms02['clasificaciones_inferidas']) if ms02['clasificaciones_inferidas'] else 'ninguna'}."
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
    if len(applicable) == len(documented) == 4 and len(identified) == 2 and not classified:
        item["observaciones"] = (
            "Los cuatro aspectos de seguridad aplicables están documentados. Sin embargo, "
            "los dos datos identificados no cuentan con clasificación explícita."
        )
    else:
        item["observaciones"] = (
            f"Seguridad evaluada con {len(documented)} de {len(applicable)} aspectos documentados; "
            f"{len(classified)} de {len(identified)} datos tienen clasificación explícita."
        )
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
    audit = {
        "recommendations_before": 0, "recommendations_after": 0,
        "malformed_recommendations_removed": 0,
        "non_actionable_recommendations_removed": 0,
        "duplicate_recommendations_removed": 0,
    }

    def extract(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, (list, tuple, set)):
            return [text for entry in value for text in extract(entry)]
        if isinstance(value, dict):
            recognized = ("recomendacion", "descripcion", "mensaje", "accion", "detalle")
            extracted = [text for key in recognized if key in value for text in extract(value.get(key))]
            if not extracted:
                audit["malformed_recommendations_removed"] += 1
            return extracted
        audit["malformed_recommendations_removed"] += 1
        return []

    for section in (result.get("quality") or {}, result.get("security") or {}):
        metrics = section.get("metricas", {})
        for metric in metrics.values() if isinstance(metrics, dict) else []:
            if isinstance(metric, dict):
                recommendations.extend(extract(metric.get("recomendacion")))
        recommendations.extend(extract(section.get("recomendaciones")))
    evaluation = result.get("evaluation") or {}
    recommendations.extend(extract(evaluation.get("correcciones_obligatorias")))
    audit["recommendations_before"] = len(recommendations)
    quality_metrics = (result.get("quality") or {}).get("metricas", {})
    mc01 = quality_metrics.get("cobertura_funcional", {}) if isinstance(quality_metrics, dict) else {}
    mc02 = quality_metrics.get("adecuacion_funcional", {}) if isinstance(quality_metrics, dict) else {}
    no_missing = isinstance(mc01, dict) and not normalizar_lista_textos(mc01.get("funciones_faltantes"))
    no_unaligned = isinstance(mc02, dict) and not normalizar_lista_textos(mc02.get("funciones_no_alineadas"))
    security_metrics = (result.get("security") or {}).get("metricas", {})
    ms01 = security_metrics.get("cobertura_seguridad", {}) if isinstance(security_metrics, dict) else {}
    ms02 = security_metrics.get("clasificacion_datos", {}) if isinstance(security_metrics, dict) else {}
    no_missing_aspects = isinstance(ms01, dict) and not (
        normalizar_lista_textos(ms01.get("aspectos_faltantes"))
        or normalizar_lista_textos(ms01.get("aspectos_parciales"))
    )
    identified_data = normalizar_lista_textos(ms02.get("datos_identificados")) if isinstance(ms02, dict) else []
    unclassified_data = normalizar_lista_textos(ms02.get("datos_sin_clasificacion")) if isinstance(ms02, dict) else []
    classification_complete = bool(identified_data) and not unclassified_data and ms02.get("valor") == 1
    actionable_markers = (
        "aclarar", "agregar", "alinear", "clasificar", "completar", "corregir", "definir",
        "detallar", "documentar", "establecer", "especificar", "incorporar",
        "indicar", "revisar", "resolver", "validar",
    )
    filtered: List[str] = []
    seen: Set[str] = set()
    for recommendation in recommendations:
        if es_texto_invalido(recommendation):
            audit["malformed_recommendations_removed"] += 1
            continue
        key = _clave_texto(recommendation)
        if no_missing and ("funciones faltantes" in key or key.startswith("incorporar o aclarar las funciones")):
            audit["non_actionable_recommendations_removed"] += 1
            continue
        if no_unaligned and key.startswith("alinear con el objetivo las funciones"):
            audit["non_actionable_recommendations_removed"] += 1
            continue
        if (classification_complete or not identified_data) and "clasific" in key and "dato" in key:
            audit["non_actionable_recommendations_removed"] += 1
            continue
        if no_missing_aspects and "document" in key and any(word in key for word in ("seguridad", "aspecto", "control")):
            audit["non_actionable_recommendations_removed"] += 1
            continue
        if not any(marker in key for marker in actionable_markers):
            audit["non_actionable_recommendations_removed"] += 1
            continue
        if key not in seen:
            seen.add(key)
            filtered.append(recommendation)
        else:
            audit["duplicate_recommendations_removed"] += 1
    if unclassified_data and not any("clasific" in _clave_texto(text) for text in filtered):
        filtered.append(
            "Clasificar explícitamente los datos identificados: " + ", ".join(unclassified_data) + "."
        )
    audit["recommendations_after"] = len(filtered)
    result.setdefault("auditoria_consolidacion_documental", {}).update(audit)
    return filtered


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


def diagnosticar_contrato_calidad_llm(response: Dict[str, Any]) -> Dict[str, Any]:
    """Valida sólo el contrato producido por Calidad, antes de cálculos Python."""
    missing, invalid, empty_valid, aliases = [], [], [], []
    premature = [
        "indice", "porcentaje", "estado", "meta", "A", "B",
        "metricas.cobertura_funcional.valor",
        "metricas.adecuacion_funcional.valor",
    ]
    alias_names = {
        "metricas_calidad": "metricas", "mc01": "cobertura_funcional",
        "mc02": "adecuacion_funcional", "funciones_alineadas_detalle": "funciones_alineadas",
    }

    def require(container, field, expected_types, path, *, allow_empty=False):
        if not isinstance(container, dict) or field not in container:
            missing.append(path)
            return
        value = container[field]
        if field == "issue_iid":
            if normalizar_iid(value) is None:
                invalid.append({"ruta": path, "tipo_esperado": "entero normalizable", "tipo_recibido": type(value).__name__})
            return
        if not isinstance(value, expected_types) or isinstance(value, bool):
            names = "/".join(kind.__name__ for kind in expected_types)
            invalid.append({"ruta": path, "tipo_esperado": names, "tipo_recibido": type(value).__name__})
        elif allow_empty and value in ([], ""):
            empty_valid.append(path)

    if not isinstance(response, dict):
        return {"valid": False, "missing_fields": ["raiz"], "invalid_types": [], "premature_fields": premature, "empty_but_valid_fields": [], "alias_fields_detected": [], "contract_stage": "llm_raw"}
    require(response, "agente", (str,), "agente")
    require(response, "resultados", (list,), "resultados")
    results = response.get("resultados") if isinstance(response.get("resultados"), list) else []
    for index, item in enumerate(results):
        base = f"resultados[{index}]"
        if not isinstance(item, dict):
            invalid.append({"ruta": base, "tipo_esperado": "dict", "tipo_recibido": type(item).__name__})
            continue
        for alias, current in alias_names.items():
            if alias in item:
                aliases.append({"ruta": f"{base}.{alias}", "campo_actual": current})
        require(item, "issue_iid", (int, str), f"{base}.issue_iid")
        require(item, "historia_id", (str,), f"{base}.historia_id")
        require(item, "metricas", (dict,), f"{base}.metricas")
        require(item, "observaciones", (str, list), f"{base}.observaciones", allow_empty=True)
        require(item, "recomendaciones", (str, list), f"{base}.recomendaciones", allow_empty=True)
        metrics = item.get("metricas") if isinstance(item.get("metricas"), dict) else {}
        for alias, current in (("mc01", "cobertura_funcional"), ("mc02", "adecuacion_funcional")):
            if alias in metrics:
                aliases.append({"ruta": f"{base}.metricas.{alias}", "campo_actual": current})
        specifications = (
            ("cobertura_funcional", ("funciones_especificadas", "funciones_incluidas", "funciones_faltantes")),
            ("adecuacion_funcional", ("funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas")),
        )
        for metric_name, fields in specifications:
            path = f"{base}.metricas.{metric_name}"
            require(metrics, metric_name, (dict,), path)
            metric = metrics.get(metric_name) if isinstance(metrics.get(metric_name), dict) else {}
            for field in fields:
                require(metric, field, (list,), f"{path}.{field}", allow_empty=True)
            require(metric, "recomendacion", (str, list), f"{path}.recomendacion", allow_empty=True)
            for alias, current in alias_names.items():
                if alias in metric:
                    aliases.append({"ruta": f"{path}.{alias}", "campo_actual": current})
    valid = not missing and not invalid and not aliases
    return {
        "valid": valid, "missing_fields": missing, "invalid_types": invalid,
        "premature_fields": premature, "empty_but_valid_fields": empty_valid,
        "alias_fields_detected": aliases, "contract_stage": "llm_raw",
    }


def validar_semantica_calidad_llm(
    response: Dict[str, Any], prepared_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Valida particiones de Calidad sin inferir clasificaciones omitidas."""
    sources = {
        normalizar_iid(item.get("issue_iid")): item
        for item in prepared_input.get("resultados", [])
        if isinstance(item, dict) and normalizar_iid(item.get("issue_iid")) is not None
    }
    diagnostics = []
    has_incomplete = False
    has_contradiction = False
    has_out_of_universe = False

    for result in response.get("resultados", []):
        iid = normalizar_iid(result.get("issue_iid"))
        source = sources.get(iid, {})
        requirements = source.get("requerimientos", []) if isinstance(source, dict) else []
        requirements = [item for item in requirements if isinstance(item, dict)]
        universe = obtener_universo_funcional_calidad(source)
        canonical = list(universe["funciones_principales_evaluables"])
        metrics = result.get("metricas", {})
        coverage = metrics.get("cobertura_funcional", {}) if isinstance(metrics, dict) else {}
        alignment = metrics.get("adecuacion_funcional", {}) if isinstance(metrics, dict) else {}

        outside = set()
        outside_by_field: Dict[str, set[str]] = {}
        outside_hashes = set()
        def classify(field: str, values: Any) -> tuple[List[str], int]:
            matched, duplicates = [], 0
            for value in normalizar_lista_textos(values):
                candidates = [item for item in canonical if funciones_equivalentes(value, item)]
                if len(candidates) != 1:
                    normalized = _clave_texto(value)
                    outside.add(normalized)
                    outside_by_field.setdefault(field, set()).add(normalized)
                    outside_hashes.add(hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12])
                    continue
                if candidates[0] in matched:
                    duplicates += 1
                else:
                    matched.append(candidates[0])
            return matched, duplicates

        classify("funciones_especificadas", coverage.get("funciones_especificadas"))
        included, dup_included = classify("funciones_incluidas", coverage.get("funciones_incluidas"))
        missing, dup_missing = classify("funciones_faltantes", coverage.get("funciones_faltantes"))
        classify("funciones_evaluables", alignment.get("funciones_evaluables"))
        aligned, dup_aligned = classify("funciones_alineadas", alignment.get("funciones_alineadas"))
        not_aligned, dup_not_aligned = classify("funciones_no_alineadas", alignment.get("funciones_no_alineadas"))
        overlap_coverage = set(included) & set(missing)
        overlap_alignment = set(aligned) & set(not_aligned)
        unclassified_coverage = [item for item in canonical if item not in included and item not in missing]
        unclassified_alignment = [item for item in canonical if item not in aligned and item not in not_aligned]

        coverage_explanation = " ".join(normalizar_lista_textos(coverage.get("justificacion")) + normalizar_lista_textos(coverage.get("recomendacion")) + normalizar_lista_textos(result.get("observaciones"))).strip()
        alignment_explanation = " ".join(normalizar_lista_textos(alignment.get("justificacion")) + normalizar_lista_textos(alignment.get("recomendacion")) + normalizar_lista_textos(result.get("observaciones"))).strip()
        explanations_required = int(bool(missing)) + int(bool(not_aligned))
        explanations_present = int(not missing or bool(coverage_explanation)) + int(not not_aligned or bool(alignment_explanation))

        contradictory = []
        if missing and not coverage_explanation:
            for function in missing:
                if any(funciones_equivalentes(function, str(req.get("nombre") or req.get("descripcion_formal") or "")) for req in requirements):
                    contradictory.append(function)
        incomplete = bool(
            unclassified_coverage or unclassified_alignment or overlap_coverage or overlap_alignment
            or dup_included or dup_missing or dup_aligned or dup_not_aligned
            or (missing and not coverage_explanation) or (not_aligned and not alignment_explanation)
        )
        has_contradiction = has_contradiction or bool(contradictory)
        has_incomplete = has_incomplete or incomplete
        has_out_of_universe = has_out_of_universe or bool(outside)
        diagnostics.append({
            "issue_iid": iid,
            "documentary_rf_count": universe["documentary_rf_count"],
            "documentary_rnf_count": universe["documentary_rnf_count"],
            "main_function_count": universe["main_function_count"],
            "conditional_rule_count": universe["conditional_rule_count"],
            "expected_functions": len(canonical),
            "classified_included": len(included), "classified_missing": len(missing),
            "unclassified_coverage": len(unclassified_coverage),
            "classified_aligned": len(aligned), "classified_not_aligned": len(not_aligned),
            "unclassified_alignment": len(unclassified_alignment),
            "contradictions": len(contradictory),
            "out_of_universe_count": len(outside),
            "out_of_universe_by_field": {
                field: len(values) for field, values in sorted(outside_by_field.items())
            },
            "out_of_universe_element_ids": sorted(outside_hashes),
            "contradiction_function_ids": [hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] for value in contradictory],
            "explanations_required": explanations_required,
            "explanations_present": explanations_present,
        })

    category = (
        "REMOTE_SEMANTIC_OUT_OF_UNIVERSE" if has_out_of_universe else
        "REMOTE_SEMANTIC_CONTRADICTION" if has_contradiction else
        "REMOTE_SEMANTIC_INCOMPLETE" if has_incomplete else None
    )
    return {
        "valid": category is None, "validation": "success" if category is None else "failed",
        "error_category": category, "by_issue": diagnostics,
    }


_SECURITY_METRIC_FIELDS = {
    "cobertura_seguridad": (
        "aspectos_aplicables", "aspectos_documentados", "aspectos_parciales",
        "aspectos_faltantes", "aspectos_inferidos",
    ),
    "clasificacion_datos": (
        "datos_identificados", "datos_clasificados", "datos_sin_clasificacion",
        "clasificaciones_inferidas",
    ),
}


def diagnosticar_contrato_seguridad_llm(response: Dict[str, Any]) -> Dict[str, Any]:
    """Valida el contrato previo al cÃ¡lculo sin exigir campos derivados en Python."""
    missing: List[str] = []
    invalid: List[Dict[str, str]] = []
    empty_valid: List[str] = []

    def require(container: Any, field: str, expected: Any, path: str, *, empty: bool = False) -> None:
        if not isinstance(container, dict) or field not in container:
            missing.append(path)
            return
        value = container[field]
        if not isinstance(value, expected):
            invalid.append({
                "ruta": path,
                "tipo_esperado": "/".join(t.__name__ for t in expected) if isinstance(expected, tuple) else expected.__name__,
                "tipo_recibido": type(value).__name__,
            })
        elif empty and value in ([], ""):
            empty_valid.append(path)

    if not isinstance(response, dict):
        return {
            "valid": False, "missing_fields": ["raiz"], "invalid_types": [],
            "premature_fields": [], "empty_but_valid_fields": [],
            "alias_fields_detected": [], "contract_stage": "llm_raw",
        }
    require(response, "agente", str, "agente")
    require(response, "resultados", list, "resultados")
    for index, item in enumerate(response.get("resultados", [])):
        base = f"resultados[{index}]"
        if not isinstance(item, dict):
            invalid.append({"ruta": base, "tipo_esperado": "dict", "tipo_recibido": type(item).__name__})
            continue
        require(item, "issue_iid", int, f"{base}.issue_iid")
        require(item, "historia_id", str, f"{base}.historia_id")
        require(item, "metricas", dict, f"{base}.metricas")
        require(item, "observaciones", (str, list), f"{base}.observaciones", empty=True)
        require(item, "recomendaciones", (str, list), f"{base}.recomendaciones", empty=True)
        metrics = item.get("metricas") if isinstance(item.get("metricas"), dict) else {}
        for metric_name, fields in _SECURITY_METRIC_FIELDS.items():
            metric_path = f"{base}.metricas.{metric_name}"
            require(metrics, metric_name, dict, metric_path)
            metric = metrics.get(metric_name) if isinstance(metrics.get(metric_name), dict) else {}
            for field in fields:
                require(metric, field, list, f"{metric_path}.{field}", empty=True)
            require(metric, "justificacion", str, f"{metric_path}.justificacion", empty=True)
            require(metric, "recomendacion", (str, list), f"{metric_path}.recomendacion", empty=True)
    return {
        "valid": not missing and not invalid, "missing_fields": missing,
        "invalid_types": invalid, "premature_fields": [],
        "empty_but_valid_fields": empty_valid, "alias_fields_detected": [],
        "contract_stage": "llm_raw",
    }


_DATA_IDENTITY_KEYS = ("dato", "nombre")
_DATA_CLASSIFICATION_KEYS = ("clasificacion", "categoria")
_DATA_COMPOSITE_SEPARATOR = re.compile(r"\s*(?::|â†’|->)\s*", re.IGNORECASE)


def _limpiar_identidad_dato(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(
        r"^\s*(?:\[[ xX]\]\s*)?(?:sÃ­|si|no)\b\s*:?\s*", "", text,
        flags=re.IGNORECASE,
    )
    return text.strip().strip(".,;:- ")


def extraer_identidad_dato(elemento: Any) -> Dict[str, Any]:
    """Extrae solo la identidad, sin incorporar claves, categorÃ­a o metadatos."""
    item_type = type(elemento).__name__
    keys = sorted(str(key) for key in elemento) if isinstance(elemento, dict) else []
    raw = None
    strategy = "unsupported"
    composite = False
    separator = None
    if isinstance(elemento, str):
        match = _DATA_COMPOSITE_SEPARATOR.search(elemento)
        raw = elemento[:match.start()] if match else elemento
        strategy = "composite_text" if match else "plain_text"
        composite = bool(match)
        separator = match.group(0).strip() if match else None
    elif isinstance(elemento, dict):
        identity_keys = [key for key in _DATA_IDENTITY_KEYS if key in elemento]
        if len(identity_keys) == 1 and isinstance(elemento.get(identity_keys[0]), str):
            raw = elemento[identity_keys[0]]
            strategy = f"dict:{identity_keys[0]}"
    cleaned = _limpiar_identidad_dato(raw) if raw is not None else ""
    return {
        "identity": cleaned, "signature": _clave_texto(cleaned) if cleaned else "",
        "item_type": item_type, "item_keys": keys, "field_count": len(keys),
        "data_identity_extracted": bool(cleaned), "extraction_strategy": strategy,
        "is_composite_text": composite, "recognized_separator": bool(separator),
        "category_embedded_in_text": composite,
    }


def extraer_clasificacion_dato(elemento: Any) -> Dict[str, Any]:
    """Extrae la categorÃ­a por separado y rechaza claves no declaradas como fuente."""
    raw = None
    strategy = "none"
    if isinstance(elemento, str):
        parts = _DATA_COMPOSITE_SEPARATOR.split(elemento, maxsplit=1)
        if len(parts) == 2:
            raw = parts[1]
            strategy = "composite_text"
    elif isinstance(elemento, dict):
        category_keys = [key for key in _DATA_CLASSIFICATION_KEYS if key in elemento]
        if len(category_keys) == 1 and isinstance(elemento.get(category_keys[0]), str):
            raw = elemento[category_keys[0]]
            strategy = f"dict:{category_keys[0]}"
    cleaned = str(raw or "").strip().strip(".,;:- ")
    return {
        "classification": cleaned,
        "signature": _clave_texto(cleaned) if cleaned else "",
        "classification_extracted": bool(cleaned),
        "extraction_strategy": strategy,
    }


def _firma_seguridad(value: Any, *, classification: bool = False) -> str:
    return extraer_identidad_dato(value)["signature"]


def _categoria_clasificacion(value: Any) -> str:
    return extraer_clasificacion_dato(value)["signature"]


def _hash_seguridad(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def clasificacion_explicita_confirmada(
    dato_normalizado: str, evidencia_original: Any, categoria_normalizada: str = "",
) -> Dict[str, Any]:
    """Contrasta una asociaciÃ³n dato-categorÃ­a sin inferirla por coexistencia textual."""
    evidence = evidencia_original if isinstance(evidencia_original, dict) else {}
    values = evidence.get("tipos_datos_sensibles")
    if isinstance(values, dict):
        values = [
            {"dato": datum, "clasificacion": category}
            for datum, category in values.items()
        ]
    elif not isinstance(values, list):
        values = []
    found_data = False
    found_categories: List[str] = []
    raw_by_signature: Dict[str, Set[str]] = {}
    for value in values:
        identity = extraer_identidad_dato(value)
        classification = extraer_clasificacion_dato(value)
        signature = identity["signature"]
        raw_by_signature.setdefault(signature, set()).add(identity["identity"].casefold())
        if signature == dato_normalizado:
            found_data = True
            if classification["signature"]:
                found_categories.append(classification["signature"])
    found_explicit = bool(
        found_categories and (
            not categoria_normalizada or categoria_normalizada in found_categories
        )
    )
    structured = {
        "data_found": found_data,
        "classification_found": bool(found_categories),
        "classification_matches_source": found_explicit,
        "normalization_collision": len(raw_by_signature.get(dato_normalizado, set())) > 1,
    }
    return {
        "found_data": found_data,
        "found_explicit_category": found_explicit,
        "category_source": "tipos_datos_sensibles" if found_explicit else None,
        "inferred_only": found_data and not found_explicit,
        "collision_detected": len(raw_by_signature.get(dato_normalizado, set())) > 1,
        "classification_mismatch": bool(
            found_categories and categoria_normalizada
            and categoria_normalizada not in found_categories
        ),
        **structured,
    }


def diagnosticar_estructura_seguridad_llm(
    response: Dict[str, Any], prepared_input: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Captura metadatos llm_raw sanitizados sin mutar ni persistir contenido."""
    sources = {
        normalizar_iid(item.get("issue_iid")): item
        for item in prepared_input.get("resultados", []) if isinstance(item, dict)
    }
    diagnostics: List[Dict[str, Any]] = []

    def type_counts(items: List[Any]) -> Dict[str, int]:
        return dict(sorted(Counter(type(item).__name__ for item in items).items()))

    def strategy_name(identity: Dict[str, Any], classification: Dict[str, Any] | None = None) -> str:
        if identity["item_type"] == "dict":
            return "structured_object"
        if classification and classification["classification_extracted"]:
            return "text_separator"
        return identity["extraction_strategy"]

    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        source = sources.get(iid, {})
        evidence = source.get("evidencia_seguridad", {}) if isinstance(source, dict) else {}
        canonical = obtener_universo_datos_seguridad(source, evidence)
        canonical_signatures = {_firma_seguridad(value) for value in canonical}
        metrics = item.get("metricas", {}) if isinstance(item.get("metricas"), dict) else {}
        ms02 = metrics.get("clasificacion_datos", {}) if isinstance(metrics.get("clasificacion_datos"), dict) else {}
        identified = list(ms02.get("datos_identificados", [])) if isinstance(ms02.get("datos_identificados"), list) else []
        classified = list(ms02.get("datos_clasificados", [])) if isinstance(ms02.get("datos_clasificados"), list) else []
        unclassified = list(ms02.get("datos_sin_clasificacion", [])) if isinstance(ms02.get("datos_sin_clasificacion"), list) else []
        identified_diag = [extraer_identidad_dato(value) for value in identified]
        classified_identity = [extraer_identidad_dato(value) for value in classified]
        classified_category = [extraer_clasificacion_dato(value) for value in classified]
        unclassified_diag = [extraer_identidad_dato(value) for value in unclassified]
        identified_signatures = {entry["signature"] for entry in identified_diag if entry["signature"]}
        classified_signatures = {entry["signature"] for entry in classified_identity if entry["signature"]}
        unclassified_signatures = {entry["signature"] for entry in unclassified_diag if entry["signature"]}
        source_matches = 0
        for identity, classification in zip(classified_identity, classified_category):
            confirmation = clasificacion_explicita_confirmada(
                identity["signature"], evidence, classification["signature"],
            )
            source_matches += int(confirmation["classification_matches_source"])
        raw_keys = Counter(
            key for entry in classified_identity if entry["item_type"] == "dict"
            for key in entry["item_keys"]
        )
        strategies = Counter(
            strategy_name(identity, classification)
            for identity, classification in zip(classified_identity, classified_category)
        )
        raw_representations: Dict[str, Set[str]] = {}
        for entry in identified_diag + classified_identity + unclassified_diag:
            raw_representations.setdefault(entry["signature"], set()).add(entry["identity"].casefold())
        collisions = sum(len(values) > 1 for signature, values in raw_representations.items() if signature)
        generic_signatures = {
            _clave_texto(value) for value in (
                "datos personales", "información sensible", "datos identificativos", "datos sensibles",
            )
        }
        
        generic_returned = identified_signatures & generic_signatures
        canonical_generic = canonical_signatures & generic_signatures
        invalid_generic_returned = generic_returned - canonical_signatures
        
        diagnostics.append({
            "contract_stage": "llm_raw", "issue_iid": iid,
            "canonical_data_count": len(canonical_signatures),
            "llm_identified_data_count": len(identified_signatures),
            "canonical_data_classified": len(classified_signatures & canonical_signatures),
            "canonical_data_unclassified": len(unclassified_signatures & canonical_signatures),
            "missing_canonical_data_count": len(canonical_signatures - identified_signatures),
            "generic_group_count": len(invalid_generic_returned),
            "canonical_generic_data_count": len(canonical_generic),
            "identified_items": {
                "count": len(identified), "types": type_counts(identified),
                "identity_extraction_success": sum(entry["data_identity_extracted"] for entry in identified_diag),
                "identity_extraction_failed": sum(not entry["data_identity_extracted"] for entry in identified_diag),
            },
            "classified_items": {
                "count": len(classified), "types": type_counts(classified),
                "object_keys": dict(sorted(raw_keys.items())),
                "strategies": dict(sorted(strategies.items())),
                "identity_extraction_success": sum(entry["data_identity_extracted"] for entry in classified_identity),
                "classification_extraction_success": sum(entry["classification_extracted"] for entry in classified_category),
                "identity_matches": sum(entry["signature"] in identified_signatures for entry in classified_identity),
                "source_classification_matches": source_matches,
            },
            "unclassified_items": {
                "count": len(unclassified), "types": type_counts(unclassified),
                "identity_extraction_success": sum(entry["data_identity_extracted"] for entry in unclassified_diag),
            },
            "external_data_count": len((classified_signatures | unclassified_signatures) - identified_signatures),
            "invented_data_count": len(identified_signatures - canonical_signatures),
            "normalization_collision_count": collisions,
            "contradictions": len(classified_signatures & unclassified_signatures),
        })
    return diagnostics


def resumir_seguridad_post_python(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Resume resultados calculados sin mezclar estrategias propias de llm_raw."""
    summaries: List[Dict[str, Any]] = []
    for item in response.get("resultados", []):
        if not isinstance(item, dict):
            continue
        metrics = item.get("metricas", {}) if isinstance(item.get("metricas"), dict) else {}
        ms01 = metrics.get("cobertura_seguridad", {}) if isinstance(metrics.get("cobertura_seguridad"), dict) else {}
        ms02 = metrics.get("clasificacion_datos", {}) if isinstance(metrics.get("clasificacion_datos"), dict) else {}
        indicator = item.get("indicador", {}) if isinstance(item.get("indicador"), dict) else {}
        summaries.append({
            "contract_stage": "post_python", "issue_iid": normalizar_iid(item.get("issue_iid")),
            "applicable_aspects": len(ms01.get("aspectos_aplicables", [])),
            "documented_aspects": len(ms01.get("aspectos_documentados", [])),
            "identified_data": len(ms02.get("datos_identificados", [])),
            "explicitly_classified_data": len(ms02.get("datos_clasificados", [])),
            "unclassified_data": len(ms02.get("datos_sin_clasificacion", [])),
            "ms01": ms01.get("valor"), "ms02": ms02.get("valor"),
            "security_index": indicator.get("valor"), "lot": item.get("lot_recomendado"),
            "target": indicator.get("meta"), "status": indicator.get("estado"),
        })
    return summaries


def validar_semantica_seguridad_llm(
    response: Dict[str, Any], prepared_input: Dict[str, Any],
) -> Dict[str, Any]:
    """Valida particiones y evidencia de Seguridad con diagnÃ³stico sanitizado."""
    sources = {
        normalizar_iid(item.get("issue_iid")): item
        for item in prepared_input.get("resultados", []) if isinstance(item, dict)
    }
    results = response.get("resultados", []) if isinstance(response, dict) else []
    received = [normalizar_iid(item.get("issue_iid")) for item in results if isinstance(item, dict)]
    diagnostics: List[Dict[str, Any]] = []
    failed_iid = None
    failed_rule = None

    def failure(
        iid: int, rule: str, section: str, field: str, signature: str = "",
        *, source_found: bool = False, explicit_found: bool = False,
        inferred_found: bool = False, duplicates: int = 0, outside: int = 0,
        collisions: int = 0, structure: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "issue_iid": iid, "failed_semantic_rule": rule,
            "semantic_subcategory": rule, "affected_section": section,
            "affected_field": field,
            "element_hash": _hash_seguridad(signature) if signature else None,
            "source_evidence_found": source_found,
            "explicit_classification_found": explicit_found,
            "inferred_classification_found": inferred_found,
            "duplicate_count": duplicates, "out_of_universe_count": outside,
            "normalization_collision_count": collisions,
            **(structure or {}),
        }

    for item in results:
        iid = normalizar_iid(item.get("issue_iid"))
        source = sources.get(iid, {})
        metrics = item.get("metricas", {}) if isinstance(item, dict) else {}
        ms01 = metrics.get("cobertura_seguridad", {}) if isinstance(metrics, dict) else {}
        ms02 = metrics.get("clasificacion_datos", {}) if isinstance(metrics, dict) else {}
        evidence = source.get("evidencia_seguridad", {}) if isinstance(source, dict) else {}
        canonical_data = obtener_universo_datos_seguridad(source, evidence)
        canonical = {_firma_seguridad(value) for value in canonical_data}
        generic_groups = {
            _clave_texto(value) for value in (
                "datos personales", "información sensible", "datos identificativos", "datos sensibles",
            )
        }
        issue_failure = None

        aspect_fields = ("aspectos_aplicables", "aspectos_documentados", "aspectos_parciales", "aspectos_faltantes")
        aspects = {field: normalizar_lista_textos(ms01.get(field)) for field in aspect_fields}
        aspect_signatures = {field: [_firma_seguridad(value) for value in values] for field, values in aspects.items()}
        for field in aspect_fields:
            counts = Counter(aspect_signatures[field])
            raw_by_sig: Dict[str, Set[str]] = {}
            for raw, sig in zip(aspects[field], aspect_signatures[field]):
                raw_by_sig.setdefault(sig, set()).add(raw.strip().casefold())
            collision = next((sig for sig, raw in raw_by_sig.items() if sig and len(raw) > 1), None)
            if collision:
                issue_failure = failure(iid, "SECURITY_INVALID_NORMALIZATION_COLLISION", "aspectos", field, collision, collisions=1)
                break
            duplicate = next((sig for sig, count in counts.items() if sig and count > 1), None)
            if duplicate:
                issue_failure = failure(iid, "SECURITY_ASPECT_DUPLICATED", "aspectos", field, duplicate, duplicates=counts[duplicate]-1)
                break
        applicable = set(aspect_signatures["aspectos_aplicables"])
        classified_groups = [set(aspect_signatures[field]) for field in aspect_fields[1:]]
        if not issue_failure:
            overlap = (classified_groups[0] & classified_groups[1]) | (classified_groups[0] & classified_groups[2]) | (classified_groups[1] & classified_groups[2])
            if overlap:
                sig = next(iter(overlap))
                issue_failure = failure(iid, "SECURITY_ASPECT_IN_MULTIPLE_GROUPS", "aspectos", "aspectos_documentados|aspectos_parciales|aspectos_faltantes", sig)
        if not issue_failure:
            union = set().union(*classified_groups)
            outside = union - applicable
            if outside:
                sig = next(iter(outside))
                field = next(name for name in aspect_fields[1:] if sig in aspect_signatures[name])
                issue_failure = failure(iid, "SECURITY_ASPECT_OUT_OF_APPLICABLE_UNIVERSE", "aspectos", field, sig, outside=len(outside))
            elif applicable - union:
                sig = next(iter(applicable-union))
                issue_failure = failure(iid, "SECURITY_ASPECT_UNCLASSIFIED", "aspectos", "aspectos_aplicables", sig)

        data_fields = ("datos_identificados", "datos_clasificados", "datos_sin_clasificacion")
        data = {
            field: list(ms02.get(field)) if isinstance(ms02.get(field), list) else []
            for field in data_fields
        }
        identity_diagnostics = {
            field: [extraer_identidad_dato(value) for value in values]
            for field, values in data.items()
        }
        classification_diagnostics = [
            extraer_clasificacion_dato(value) for value in data["datos_clasificados"]
        ]
        signatures = {
            field: [diagnostic["signature"] for diagnostic in diagnostics]
            for field, diagnostics in identity_diagnostics.items()
        }
        if not issue_failure:
            for field in data_fields:
                failed_index = next((
                    index for index, diagnostic in enumerate(identity_diagnostics[field])
                    if not diagnostic["data_identity_extracted"]
                ), None)
                if failed_index is not None:
                    diagnostic = identity_diagnostics[field][failed_index]
                    issue_failure = failure(
                        iid, "SECURITY_DATA_IDENTITY_EXTRACTION_FAILED", "datos", field,
                        structure={
                            "identified_item_type": diagnostic["item_type"] if field == "datos_identificados" else None,
                            "classified_item_type": diagnostic["item_type"] if field == "datos_clasificados" else None,
                            "classified_item_keys": diagnostic["item_keys"] if field == "datos_clasificados" else [],
                            "extraction_strategy": diagnostic["extraction_strategy"],
                            "data_identity_extracted": False,
                            "classification_extracted": False,
                            "identity_match_found": False,
                        },
                    )
                    break
        if not issue_failure:
            failed_index = next((
                index for index, diagnostic in enumerate(classification_diagnostics)
                if not diagnostic["classification_extracted"]
            ), None)
            if failed_index is not None:
                identity = identity_diagnostics["datos_clasificados"][failed_index]
                issue_failure = failure(
                    iid, "SECURITY_CLASSIFICATION_EXTRACTION_FAILED", "datos", "datos_clasificados",
                    identity["signature"],
                    structure={
                        "identified_item_type": None,
                        "classified_item_type": identity["item_type"],
                        "classified_item_keys": identity["item_keys"],
                        "extraction_strategy": classification_diagnostics[failed_index]["extraction_strategy"],
                        "data_identity_extracted": True,
                        "classification_extracted": False,
                        "identity_match_found": identity["signature"] in set(signatures["datos_identificados"]),
                    },
                )
        if not issue_failure:
            for field in data_fields:
                counts = Counter(signatures[field])
                raw_by_sig: Dict[str, Set[str]] = {}
                for diagnostic, sig in zip(identity_diagnostics[field], signatures[field]):
                    raw_by_sig.setdefault(sig, set()).add(diagnostic["identity"].casefold())
                collision = next((sig for sig, raw in raw_by_sig.items() if sig and len(raw) > 1), None)
                if collision:
                    issue_failure = failure(iid, "SECURITY_INVALID_NORMALIZATION_COLLISION", "datos", field, collision, collisions=1)
                    break
                duplicate = next((sig for sig, count in counts.items() if sig and count > 1), None)
                if duplicate:
                    issue_failure = failure(iid, "SECURITY_DATA_DUPLICATED", "datos", field, duplicate, duplicates=counts[duplicate]-1)
                    break
        identified, explicit, unclassified = map(set, (signatures[field] for field in data_fields))
        if not issue_failure and explicit & unclassified:
            sig = next(iter(explicit & unclassified))
            issue_failure = failure(iid, "SECURITY_DATA_IN_MULTIPLE_GROUPS", "datos", "datos_clasificados|datos_sin_clasificacion", sig)
        if not issue_failure and (explicit | unclassified) - identified:
            sig = next(iter((explicit | unclassified) - identified))
            field = "datos_clasificados" if sig in explicit else "datos_sin_clasificacion"
            diagnostic = identity_diagnostics[field][signatures[field].index(sig)]
            classification = (
                classification_diagnostics[signatures[field].index(sig)]
                if field == "datos_clasificados" else {}
            )
            issue_failure = failure(
                iid, "SECURITY_DATA_OUT_OF_IDENTIFIED_UNIVERSE", "datos", field, sig, outside=1,
                structure={
                    "identified_item_type": identity_diagnostics["datos_identificados"][0]["item_type"] if identity_diagnostics["datos_identificados"] else None,
                    "classified_item_type": diagnostic["item_type"] if field == "datos_clasificados" else None,
                    "classified_item_keys": diagnostic["item_keys"] if field == "datos_clasificados" else [],
                    "extraction_strategy": diagnostic["extraction_strategy"],
                    "data_identity_extracted": diagnostic["data_identity_extracted"],
                    "classification_extracted": classification.get("classification_extracted", False),
                    "identity_match_found": False,
                },
            )
        if not issue_failure and identified - (explicit | unclassified):
            sig = next(iter(identified - (explicit | unclassified)))
            issue_failure = failure(iid, "SECURITY_DATA_UNCLASSIFIED", "datos", "datos_identificados", sig)

        external = identified - canonical
        missing_canonical = canonical - identified
        generic_returned = identified & generic_groups
        canonical_generic = canonical & generic_groups
        invalid_generic_returned = generic_returned - canonical
        other_evidence = {
            other_iid: other.get("evidencia_seguridad", {})
            for other_iid, other in sources.items()
            if other_iid != iid and isinstance(other, dict)
        }
        canonical_structure = {
            "canonical_data_count": len(canonical),
            "llm_identified_data_count": len(identified),
            "canonical_data_classified": len(explicit & canonical),
            "canonical_data_unclassified": len(unclassified & canonical),
            "missing_canonical_data_count": len(missing_canonical),
            "external_data_count": len(external),
            "generic_group_count": len(invalid_generic_returned),
            "canonical_generic_data_count": len(canonical_generic),
        }
        if not issue_failure and invalid_generic_returned and missing_canonical:
            sig = next(iter(invalid_generic_returned))
            issue_failure = failure(
                iid, "SECURITY_GENERIC_DATA_GROUP_RETURNED", "datos", "datos_identificados", sig,
                structure=canonical_structure,
            )
        if not issue_failure and external:
            sig = next(iter(external))
            cross_issue = any(
                sig in {_firma_seguridad(value) for value in obtener_universo_datos_seguridad(other, evidence_other)}
                for other_iid, evidence_other in other_evidence.items()
                for other in [sources.get(other_iid, {})]
            )
            issue_failure = failure(
                iid,
                "SECURITY_CROSS_ISSUE_EVIDENCE" if cross_issue else "SECURITY_DATA_NOT_FOUND_IN_ORIGINAL_EVIDENCE",
                "datos", "datos_identificados", sig,
                structure=canonical_structure,
            )
        if not issue_failure and missing_canonical:
            sig = next(iter(missing_canonical))
            issue_failure = failure(
                iid, "SECURITY_CANONICAL_DATA_MISSING", "datos", "datos_identificados", sig,
                structure=canonical_structure,
            )

        suggested_values = ms02.get("clasificaciones_inferidas")
        suggested_values = suggested_values if isinstance(suggested_values, list) else []
        suggested = {extraer_identidad_dato(value)["signature"] for value in suggested_values}
        all_other_evidence = {
            other_iid: other.get("evidencia_seguridad", {}) for other_iid, other in sources.items()
            if other_iid != iid and isinstance(other, dict)
        }
        if not issue_failure:
            for raw, sig in zip(data["datos_identificados"], signatures["datos_identificados"]):
                own = clasificacion_explicita_confirmada(sig, evidence)
                if not own["found_data"]:
                    cross = any(clasificacion_explicita_confirmada(sig, other)["found_data"] for other in all_other_evidence.values())
                    rule = "SECURITY_CROSS_ISSUE_EVIDENCE" if cross else "SECURITY_DATA_NOT_FOUND_IN_ORIGINAL_EVIDENCE"
                    issue_failure = failure(iid, rule, "datos", "datos_identificados", sig, source_found=False)
                    break
        if not issue_failure:
            for raw, sig in zip(data["datos_clasificados"], signatures["datos_clasificados"]):
                category = _categoria_clasificacion(raw)
                confirmed = clasificacion_explicita_confirmada(sig, evidence, category)
                if confirmed["collision_detected"]:
                    issue_failure = failure(iid, "SECURITY_INVALID_NORMALIZATION_COLLISION", "datos", "datos_clasificados", sig, collisions=1)
                elif confirmed["classification_mismatch"]:
                    issue_failure = failure(iid, "SECURITY_CLASSIFICATION_MISMATCH", "datos", "datos_clasificados", sig, source_found=True)
                elif not confirmed["found_explicit_category"]:
                    inferred = sig in suggested
                    rule = "SECURITY_INFERRED_CLASSIFICATION_COUNTED_AS_EXPLICIT" if inferred else "SECURITY_EXPLICIT_CLASSIFICATION_WITHOUT_SOURCE"
                    issue_failure = failure(iid, rule, "datos", "datos_clasificados", sig, source_found=confirmed["found_data"], inferred_found=inferred)
                if issue_failure:
                    break

        counts = {
            "issue_iid": iid, "applicable_aspects": len(aspects["aspectos_aplicables"]),
            "documented_aspects": len(aspects["aspectos_documentados"]),
            "partial_aspects": len(aspects["aspectos_parciales"]),
            "missing_aspects": len(aspects["aspectos_faltantes"]),
            "unclassified_aspects": len(applicable - set().union(*classified_groups)),
            "identified_data": len(data["datos_identificados"]),
            "explicitly_classified_data": len(data["datos_clasificados"]),
            "unclassified_data": len(data["datos_sin_clasificacion"]),
            "inferred_classifications": len(normalizar_lista_textos(ms02.get("clasificaciones_inferidas"))),
            "invented_data_count": int(bool(issue_failure and issue_failure["semantic_subcategory"] in {"SECURITY_DATA_NOT_FOUND_IN_ORIGINAL_EVIDENCE", "SECURITY_CROSS_ISSUE_EVIDENCE"})),
            "contradictions": int(issue_failure is not None),
            "explanations_required": int(bool(aspects["aspectos_faltantes"])) + int(bool(data["datos_sin_clasificacion"])),
            "explanations_present": sum(bool(str(ms.get("justificacion", "")).strip()) for ms in (ms01, ms02)),
            **canonical_structure,
        }
        if issue_failure:
            diagnostics.append({**counts, **issue_failure})
            failed_iid, failed_rule = iid, issue_failure["semantic_subcategory"]
            break
        diagnostics.append(counts)

    pending = [iid for iid in received if failed_iid is not None and iid not in [d["issue_iid"] for d in diagnostics]]
    incomplete = failed_rule in {
        "SECURITY_ASPECT_UNCLASSIFIED", "SECURITY_DATA_UNCLASSIFIED",
        "SECURITY_CANONICAL_DATA_MISSING", "SECURITY_GENERIC_DATA_GROUP_RETURNED",
    }
    category = "REMOTE_SEMANTIC_INCOMPLETE" if incomplete else "REMOTE_SEMANTIC_CONTRADICTION" if failed_rule else None
    return {
        "valid": failed_rule is None, "validation": "success" if failed_rule is None else "failed",
        "error_category": category, "semantic_subcategory": failed_rule,
        "failed_semantic_rule": failed_rule, "failed_issue_iid": failed_iid,
        "received_issue_ids": received, "pending_semantic_validation": pending,
        "stage_reached": "semantic_validation_complete" if not failed_rule else "semantic_validation_failed",
        "by_issue": diagnostics,
    }


def validar_respuesta_lote(
    response: Dict[str, Any], expected_issue_ids: Set[int], agent_name: str,
    contract_stage: str = "post_python",
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
        if agent_name in {"Calidad", "Seguridad"} and contract_stage != "llm_raw":
            indice = item.get("indice")
            no_evaluable = indice is None and item.get("estado_medicion") in {
                "no_evaluable", "no_aplicable", "evidencia_insuficiente",
            }
            if not no_evaluable and (not isinstance(indice, (int, float)) or isinstance(indice, bool) or not 0 <= indice <= 1):
                errors.append(f"{agent_name}: índice inválido para Issue #{iid}.")
    if agent_name == "Calidad" and contract_stage == "llm_raw":
        diagnostic = diagnosticar_contrato_calidad_llm(response)
        if not diagnostic["valid"]:
            errors.append("Calidad: contrato LLM previo a cálculos Python inválido.")
    if agent_name == "Seguridad" and contract_stage == "llm_raw":
        diagnostic = diagnosticar_contrato_seguridad_llm(response)
        if not diagnostic["valid"]:
            errors.append("Seguridad: contrato LLM previo a cÃ¡lculos Python invÃ¡lido.")
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


def _evidencia_requerimiento(requirement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: requirement.get(key) for key in (
            "id", "temp_id", "nombre", "descripcion_formal", "origen", "procedencia",
        ) if requirement.get(key) not in (None, "")
    }


def _es_regla_contextual_formal(requirement: Dict[str, Any]) -> bool:
    text = _clave_texto(" ".join(str(requirement.get(field) or "") for field in (
        "nombre", "descripcion_formal", "descripcion", "origen",
    )))
    return any(marker in text for marker in (
        "cuando", "siempre que", "menos de", "no permitir", "impedir", "restringir", "bloquear",
    ))


def consolidar_requerimientos_formales_equivalentes(
    requirements: Any,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Fusiona equivalencias formales tras reunir fuentes y antes de asignar códigos."""
    source = [deepcopy(item) for item in requirements if isinstance(item, dict)] if isinstance(requirements, list) else []
    before_rf = sum(normalizar_tipo_requerimiento(item) == "RF" for item in source)
    before_rnf = sum(normalizar_tipo_requerimiento(item) == "RNF" for item in source)
    consolidated: List[Dict[str, Any]] = []
    merged_rf = merged_rnf = 0

    for candidate in source:
        kind = normalizar_tipo_requerimiento(candidate)
        candidate["tipo"] = kind
        presentation_key = _clave_texto(" ".join(str(candidate.get(field) or "") for field in (
            "nombre", "descripcion_formal", "origen",
        )))
        if kind == "RF" and "agenda" in presentation_key and "actualiz" in presentation_key and "tiempo real" not in presentation_key:
            candidate["descripcion_formal"] = (
                "El sistema deberá actualizar la agenda cuando cambie la información de las citas."
            )
            candidate["descripcion"] = candidate["descripcion_formal"]
        if kind == "RNF" and "tiempo real" in presentation_key and "actualiz" in presentation_key:
            candidate["descripcion_formal"] = "El sistema deberá reflejar la información actualizada en tiempo real."
            candidate["descripcion"] = candidate["descripcion_formal"]
        candidate_evidence = [_evidencia_requerimiento(candidate)]
        candidate_evidence.extend(
            entry for entry in candidate.get("evidencias_equivalentes", []) if isinstance(entry, dict)
        )
        match = None
        for canonical in consolidated:
            if canonical.get("tipo") != kind:
                continue
            if kind == "RF":
                if _es_regla_contextual_formal(candidate) != _es_regla_contextual_formal(canonical):
                    continue
                left = candidate.get("nombre") or candidate.get("descripcion_formal") or candidate.get("descripcion")
                right = canonical.get("nombre") or canonical.get("descripcion_formal") or canonical.get("descripcion")
                equivalent = funciones_equivalentes(left, right)
            else:
                left = _clave_texto(candidate.get("descripcion_formal") or candidate.get("descripcion") or candidate.get("nombre"))
                right = _clave_texto(canonical.get("descripcion_formal") or canonical.get("descripcion") or canonical.get("nombre"))
                equivalent = bool(left and left == right)
            if equivalent:
                match = canonical
                break
        if match is None:
            candidate["evidencias_equivalentes"] = []
            for evidence in candidate_evidence:
                if evidence and evidence not in candidate["evidencias_equivalentes"]:
                    candidate["evidencias_equivalentes"].append(evidence)
            consolidated.append(candidate)
            continue
        merged_rf += int(kind == "RF")
        merged_rnf += int(kind == "RNF")
        evidences = match.setdefault("evidencias_equivalentes", [])
        for evidence in candidate_evidence:
            if evidence and evidence not in evidences:
                evidences.append(evidence)
        match["ids_requerimientos_originales"] = list(dict.fromkeys(
            str(evidence.get("id") or evidence.get("temp_id"))
            for evidence in evidences if evidence.get("id") or evidence.get("temp_id")
        ))
        match["fuentes_explicitas"] = list(dict.fromkeys(
            str(evidence.get("procedencia")) for evidence in evidences if evidence.get("procedencia")
        ))

    after_rf = sum(item.get("tipo") == "RF" for item in consolidated)
    after_rnf = sum(item.get("tipo") == "RNF" for item in consolidated)
    return consolidated, {
        "requirements_before_document_dedup": len(source),
        "requirements_after_document_dedup": len(consolidated),
        "rf_before": before_rf, "rf_after": after_rf,
        "rnf_before": before_rnf, "rnf_after": after_rnf,
        "equivalent_rf_merged": merged_rf,
        "equivalent_rnf_merged": merged_rnf,
    }


def validar_consolidacion_documental_final(results: Iterable[Dict[str, Any]]) -> List[str]:
    errors: List[str] = []
    seen_issues: Set[int] = set()
    for result in results:
        iid = normalizar_iid(result.get("issue_iid")) if isinstance(result, dict) else None
        if iid is None:
            errors.append("Resultado documental sin issue_iid asociable.")
            continue
        if iid in seen_issues:
            errors.append(f"Issue #{iid}: resultado duplicado.")
        seen_issues.add(iid)
        central = result.get("central") if isinstance(result.get("central"), dict) else result
        requirements = central.get("requerimientos", []) if isinstance(central, dict) else []
        codes: Set[str] = set()
        for index, requirement in enumerate(requirements, 1):
            if not isinstance(requirement, dict):
                errors.append(f"Issue #{iid}: requerimiento {index} no estructurado.")
                continue
            code = str(requirement.get("id") or "")
            if code in codes:
                errors.append(f"Issue #{iid}: código duplicado {code}.")
            codes.add(code)
            if requirement.get("tipo") not in {"RF", "RNF"}:
                errors.append(f"Issue #{iid}: tipo inválido en {code or index}.")
            if not str(requirement.get("descripcion_formal") or requirement.get("descripcion") or "").strip():
                errors.append(f"Issue #{iid}: descripción vacía en {code or index}.")
        deduped, diagnostic = consolidar_requerimientos_formales_equivalentes(requirements)
        if diagnostic["requirements_after_document_dedup"] != len(requirements):
            errors.append(f"Issue #{iid}: conserva requerimientos formales equivalentes.")
        for recommendation in result.get("recommendations", []):
            if not isinstance(recommendation, str) or recommendation.lstrip().startswith("{"):
                errors.append(f"Issue #{iid}: recomendación visible no textual.")
    return errors


def normalizar_tipo_requerimiento(requirement: Any) -> str | None:
    """Reduce tipos actuales y heredados a RF/RNF usando el contenido."""
    if not isinstance(requirement, dict):
        kind = _clave_texto(requirement)
        if kind in {"rf", "funcional"}:
            return "RF"
        if kind in {"rnf", "no funcional", "nofuncional"}:
            return "RNF"
        return None
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
    """Fija el veredicto final desde los indicadores calculados en Python."""
    original = evaluation.get("veredicto")
    reasons: List[str] = []
    input_validation = input_validation or {"estado": "entrada_valida", "campos_faltantes": []}
    if input_validation.get("estado") == "informacion_insuficiente":
        reasons.append("La información de entrada es insuficiente.")
    not_evaluated = False
    not_compliant = False
    for label, report in (("calidad", quality), ("seguridad", security)):
        if report.get("indice") is None or report.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}:
            not_evaluated = True
            reasons.append(f"La métrica esencial de {label} no es evaluable.")
        if any(
            isinstance(metric, dict) and metric.get("estado_medicion") in {"no_evaluable", "evidencia_insuficiente"}
            for metric in report.get("metricas", {}).values()
        ):
            not_evaluated = True
            reasons.append(f"Existe evidencia insuficiente en una métrica esencial de {label}.")
        indicator = report.get("indicador") if isinstance(report.get("indicador"), dict) else {}
        indicator_state = indicator.get("estado")
        if indicator_state is None and isinstance(report.get("indice"), (int, float)):
            default_meta = 0.95 if label == "calidad" else {
                "LoT-2": 0.90, "LoT-3": 0.95,
            }.get(report.get("lot_recomendado"), 0.90)
            indicator_state = "Cumple" if report["indice"] >= default_meta else "No cumple"
        if indicator_state == "No cumple":
            not_compliant = True
            reasons.append(f"El índice de {label} no alcanza su meta.")

    if reasons and (not_evaluated or input_validation.get("estado") == "informacion_insuficiente"):
        adjusted = "REVISIÓN REQUERIDA"
    elif not_compliant:
        adjusted = "CORREGIR"
    else:
        adjusted = "APROBADO"

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
        central_item["requerimientos"], documentary_audit = consolidar_requerimientos_formales_equivalentes(
            central_item.get("requerimientos"),
        )
        central_item["auditoria_consolidacion_documental"] = documentary_audit
        try:
            from core.performance_audit import registrar_consolidacion_documental
            registrar_consolidacion_documental(iid, documentary_audit)
        except ImportError:
            pass
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
        if all(isinstance(item, dict) for item in (central_item, quality_item, security_item, evaluation_item)):
            ajustar_veredicto_determinista(
                central_item, quality_item, security_item, evaluation_item, input_validation,
            )
        estado_evaluacion = evaluation_item.get("veredicto", "NO_EVALUADO") if evaluation_item else "NO_EVALUADO"
        central_status = str((central_item or {}).get("status", "ok")).strip().casefold()
        traceable_individual_error = central_status == "error"
        insufficient = central_status == "informacion_insuficiente" or input_validation.get("estado") == "informacion_insuficiente"
        consolidated_item = {
            "issue_iid": iid,
            "status": "error" if errors or traceable_individual_error else (
                "informacion_insuficiente" if insufficient else "ok"
            ),
            "estado_procesamiento": "error" if errors or traceable_individual_error else (
                "informacion_insuficiente" if insufficient else "completo"
            ),
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
        }
        consolidated_item["recommendations"] = recopilar_recomendaciones(consolidated_item)
        consolidated.append(consolidated_item)
    traceable = [x for x in consolidated if isinstance(x.get("central"), dict)]
    quality_values = [x["quality"]["indice"] for x in traceable if isinstance(x.get("quality"), dict) and isinstance(x["quality"].get("indice"), (int, float))]
    security_values = [x["security"]["indice"] for x in traceable if isinstance(x.get("security"), dict) and isinstance(x["security"].get("indice"), (int, float))]
    verdicts = Counter(x["evaluation"].get("veredicto") for x in traceable if isinstance(x.get("evaluation"), dict))
    requirements = [r for x in traceable for r in x["central"].get("requerimientos", []) if isinstance(r, dict)]
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
            "historias_procesadas": len(traceable),
            "historias_evaluables_calidad": len(quality_values),
            "historias_evaluables_seguridad": len(security_values),
            "historias_no_evaluables_calidad": len(traceable) - len(quality_values),
            "historias_no_evaluables_seguridad": len(traceable) - len(security_values),
            "historias_con_error": sum(x["status"] == "error" for x in consolidated),
            "total_por_veredicto": dict(verdicts),
            "calidad_promedio": sum(quality_values) / len(quality_values) if quality_values else None,
            "seguridad_promedio": sum(security_values) / len(security_values) if security_values else None,
            "requerimientos_sugeridos": len(requirements),
        },
    }
