"""Diagnóstico manual aislado. No realiza llamadas sin --execute."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def _load_local_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_local_env()

from core.batch_contract import (
    analizar_respuesta_lote, validar_contenido_agente, validar_respuesta_lote,
)


FAKE_CENTRAL_INPUT = {
    "agente": "central",
    "resultados": [{
        "issue_iid": 10,
        "historia_id": "HU-010",
        "titulo": "Cancelar cita médica",
        "actor": "Paciente",
        "objetivo": "Liberar el horario reservado",
        "prioridad": "Alta",
        "requerimientos": [{
            "temp_id": "RF-TEMP-01",
            "nombre": "Cancelar cita",
            "descripcion_formal": "El sistema deberá permitir cancelar una cita médica.",
            "tipo": "RF",
            "origen": "Cancelar una cita",
            "justificacion": "Acción explícita de la historia ficticia.",
            "prioridad": "Alta",
            "procedencia": "explícita — funcionalidad",
        }],
        "restricciones": [],
        "ambiguedades": [],
        "informacion_faltante": [],
        "observaciones": [],
        "evidencia_seguridad": {
            "descripcion": "Datos personales de una cita ficticia.",
            "maneja_datos_sensibles": "Sí: nombre y documento ficticios.",
            "tipos_datos_sensibles": ["Nombre ficticio", "Documento ficticio"],
            "autenticacion": "Usuario y contraseña ficticios.",
            "autorizacion_roles": "Rol Paciente.",
            "auditoria": "Registro de cancelación ficticio.",
        },
    }],
}


EXPECTED_OBJECTIVE = "Liberar el horario reservado"


def _texts(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for child in value.values() for text in _texts(child)]
    if isinstance(value, list):
        return [text for child in value for text in _texts(child)]
    return []


QUALITY_ALIASES = {
    "metricas_calidad": "metricas",
    "mc01": "metricas.cobertura_funcional",
    "mc02": "metricas.adecuacion_funcional",
    "funciones_alineadas_detalle": "metricas.adecuacion_funcional.funciones_alineadas",
    "recomendaciones": "recomendacion",
}


def _field_status(container, name, expected_type, *, empty_valid=True):
    present = isinstance(container, dict) and name in container
    value = container.get(name) if present else None
    valid_type = present and isinstance(value, expected_type) and not (
        expected_type is int and isinstance(value, bool)
    )
    status = {
        "presente": present,
        "tipo_esperado": expected_type.__name__,
        "tipo_recibido": type(value).__name__ if present else None,
        "tipo_valido": valid_type,
    }
    if valid_type and expected_type is list:
        status.update({
            "cantidad": len(value),
            "lista_vacia": not value,
            "vacio_valido": empty_valid if not value else None,
        })
    if valid_type and expected_type is str:
        status.update({
            "vacio": not value.strip(),
            "vacio_valido": empty_valid if not value.strip() else None,
        })
        if not empty_valid and not value.strip():
            valid_type = False
    status["valido"] = valid_type and (
        empty_valid or not hasattr(value, "__len__") or len(value) > 0
    )
    return status


def diagnosticar_contrato_calidad(parsed, expected_iid=10):
    """Describe el contrato sin exponer contenido textual de la respuesta."""
    missing = []
    invalid_types = []
    aliases = []

    def inspect(container, name, expected_type, path, *, empty_valid=True):
        status = _field_status(container, name, expected_type, empty_valid=empty_valid)
        if not status["presente"]:
            missing.append(path)
        elif not status["tipo_valido"]:
            invalid_types.append({
                "ruta": path,
                "tipo_esperado": status["tipo_esperado"],
                "tipo_recibido": status["tipo_recibido"],
            })
        return status

    root = parsed if isinstance(parsed, dict) else {}
    top = {
        "agente": inspect(root, "agente", str, "agente", empty_valid=False),
        "resultados": inspect(root, "resultados", list, "resultados", empty_valid=False),
    }
    results = root.get("resultados") if isinstance(root.get("resultados"), list) else []
    item = results[0] if results and isinstance(results[0], dict) else {}
    if results and not isinstance(results[0], dict):
        invalid_types.append({"ruta": "resultados[0]", "tipo_esperado": "dict", "tipo_recibido": type(results[0]).__name__})

    for alias in QUALITY_ALIASES:
        if alias in item:
            aliases.append({"ruta": alias, "equivalente_actual": QUALITY_ALIASES[alias]})

    result_status = {
        "issue_iid": inspect(item, "issue_iid", int, "resultados[0].issue_iid"),
        "historia_id": inspect(item, "historia_id", str, "resultados[0].historia_id", empty_valid=False),
        "metricas": inspect(item, "metricas", dict, "resultados[0].metricas"),
    }
    metrics = item.get("metricas") if isinstance(item.get("metricas"), dict) else {}
    for alias in ("mc01", "mc02"):
        if alias in metrics:
            aliases.append({"ruta": f"resultados[0].metricas.{alias}", "equivalente_actual": QUALITY_ALIASES[alias]})

    def metric_status(name, list_fields, extra_fields=()):
        path = f"resultados[0].metricas.{name}"
        present = inspect(metrics, name, dict, path)
        metric = metrics.get(name) if isinstance(metrics.get(name), dict) else {}
        fields = {field: inspect(metric, field, list, f"{path}.{field}") for field in list_fields}
        for field, expected_type, empty_valid in extra_fields:
            fields[field] = inspect(metric, field, expected_type, f"{path}.{field}", empty_valid=empty_valid)
        for alias in ("funciones_alineadas_detalle", "recomendaciones"):
            if alias in metric:
                aliases.append({"ruta": f"{path}.{alias}", "equivalente_actual": QUALITY_ALIASES[alias]})
        return {"presente": present, **fields}

    mc01 = metric_status("cobertura_funcional", (
        "funciones_especificadas", "funciones_incluidas", "funciones_faltantes",
    ), (("justificacion", str, False), ("recomendacion", str, True)))
    mc02 = metric_status("adecuacion_funcional", (
        "funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas",
    ), (("objetivo_evaluado", str, False), ("justificacion", str, False), ("recomendacion", str, True)))

    current_structure = not aliases and isinstance(item.get("metricas"), dict)
    schema_complete = not missing and not invalid_types and all(
        status.get("valido", True)
        for section in (top, result_status, mc01, mc02)
        for status in section.values() if isinstance(status, dict)
    )
    production_errors = []
    if isinstance(parsed, dict) and isinstance(parsed.get("resultados"), list):
        try:
            production_errors.extend(validar_respuesta_lote(parsed, {expected_iid}, "Calidad"))
            content = validar_contenido_agente(parsed, "Calidad")
            production_errors.extend(error for errors in content.values() for error in errors)
        except (KeyError, TypeError):
            production_errors.append("respuesta no procesable por validadores productivos")
    return {
        "completo": schema_complete,
        "estructura": "actual" if current_structure else "antigua_o_alias" if aliases else "invalida",
        "top_level": top,
        "resultado": result_status,
        "mc01": mc01,
        "mc02": mc02,
        "campos_faltantes": missing,
        "tipos_invalidos": invalid_types,
        "aliases_detectados": aliases,
        "validacion_productiva": {
            "aprobada": not production_errors,
            "reglas_fallidas": [
                "indice requerido antes del calculo Python" if "ndice inv" in error else "contenido o estructura invalida"
                for error in production_errors
            ],
            "cantidad_errores": len(production_errors),
        },
    }


def diagnosticar_contrato_seguridad(parsed, expected_iid=10):
    """Valida la salida propia de Seguridad antes de los cálculos Python."""
    missing = []
    invalid_types = []

    def inspect(container, name, expected_type, path, *, empty_valid=True):
        status = _field_status(container, name, expected_type, empty_valid=empty_valid)
        if not status["presente"]:
            missing.append(path)
        elif not status["tipo_valido"]:
            invalid_types.append({
                "ruta": path,
                "tipo_esperado": status["tipo_esperado"],
                "tipo_recibido": status["tipo_recibido"],
            })
        return status

    root = parsed if isinstance(parsed, dict) else {}
    top = {
        "agente": inspect(root, "agente", str, "agente", empty_valid=False),
        "resultados": inspect(root, "resultados", list, "resultados", empty_valid=False),
    }
    results = root.get("resultados") if isinstance(root.get("resultados"), list) else []
    item = results[0] if results and isinstance(results[0], dict) else {}
    result_status = {
        "issue_iid": inspect(item, "issue_iid", int, "resultados[0].issue_iid"),
        "historia_id": inspect(item, "historia_id", str, "resultados[0].historia_id", empty_valid=False),
        "metricas": inspect(item, "metricas", dict, "resultados[0].metricas"),
    }
    metrics = item.get("metricas") if isinstance(item.get("metricas"), dict) else {}

    def metric_status(name, list_fields):
        path = f"resultados[0].metricas.{name}"
        present = inspect(metrics, name, dict, path)
        metric = metrics.get(name) if isinstance(metrics.get(name), dict) else {}
        fields = {field: inspect(metric, field, list, f"{path}.{field}") for field in list_fields}
        fields["justificacion"] = inspect(metric, "justificacion", str, f"{path}.justificacion", empty_valid=False)
        fields["recomendacion"] = inspect(metric, "recomendacion", str, f"{path}.recomendacion")
        return {"presente": present, **fields}

    ms01 = metric_status("cobertura_seguridad", (
        "aspectos_aplicables", "aspectos_documentados", "aspectos_parciales",
        "aspectos_faltantes", "aspectos_inferidos",
    ))
    ms02 = metric_status("clasificacion_datos", (
        "datos_identificados", "datos_clasificados", "datos_sin_clasificacion",
        "clasificaciones_inferidas",
    ))
    complete = not missing and not invalid_types and all(
        status.get("valido", True)
        for section in (top, result_status, ms01, ms02)
        for status in section.values() if isinstance(status, dict)
    )
    production_errors = []
    if isinstance(parsed, dict) and isinstance(parsed.get("resultados"), list):
        production_errors.extend(validar_respuesta_lote(parsed, {expected_iid}, "Seguridad"))
        content = validar_contenido_agente(parsed, "Seguridad")
        production_errors.extend(error for errors in content.values() for error in errors)
    return {
        "completo": complete,
        "top_level": top,
        "resultado": result_status,
        "ms01": ms01,
        "ms02": ms02,
        "campos_faltantes": missing,
        "tipos_invalidos": invalid_types,
        "validacion_posterior": {
            "aprobada": not production_errors,
            "cantidad_errores": len(production_errors),
        },
        "campos_calculados_en_python": ["indice", "estado_medicion", "meta_cumplida", "lot_recomendado"],
    }


def summarize_quality(raw, elapsed, input_chars):
    initially_valid = True
    recovered = False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        initially_valid = False
        try:
            parsed = analizar_respuesta_lote(raw, "Calidad")
            recovered = True
        except ValueError:
            print(json.dumps({
                "agent": "Quality", "error": "REMOTE_INVALID_RESPONSE",
                "json_inicial_valido": False, "recuperacion_aplicada": False,
                "input_chars": input_chars, "output_chars": len(raw),
                "elapsed_seconds": round(elapsed, 3), "fallback": False,
            }, ensure_ascii=False))
            return

    results = parsed.get("resultados", []) if isinstance(parsed, dict) else []
    item = results[0] if results and isinstance(results[0], dict) else {}
    metrics = item.get("metricas", {}) if isinstance(item.get("metricas"), dict) else {}
    coverage = metrics.get("cobertura_funcional", {})
    adequacy = metrics.get("adecuacion_funcional", {})
    coverage = coverage if isinstance(coverage, dict) else {}
    adequacy = adequacy if isinstance(adequacy, dict) else {}
    iid = item.get("issue_iid")
    story_id = item.get("historia_id")
    diagnostic_text = " ".join(_texts({
        "justificaciones": [coverage.get("justificacion"), adequacy.get("justificacion")],
        "recomendaciones": [coverage.get("recomendacion"), adequacy.get("recomendacion")],
        "observaciones": item.get("observaciones"),
    })).casefold()
    implementation_markers = ("implementad", "desarrollad", "código", "prueba", "despliegue")
    other_story_markers = ("registrar paciente", "agenda médica", "generar reporte", "consultar horario")
    contract_diagnostic = diagnosticar_contrato_calidad(parsed)
    from agents.llm_invocation import obtener_ultimos_metadatos
    metadata = obtener_ultimos_metadatos("Quality")
    print(json.dumps({
        "agent": "Quality",
        "provider": metadata.get("provider", "groq"),
        "model": metadata.get("model"),
        "max_completion_tokens": int(os.getenv("REMOTE_QUALITY_MAX_COMPLETION_TOKENS", "2048")),
        "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
        "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden"),
        "elapsed_seconds": round(elapsed, 3),
        "input_chars": input_chars,
        "output_chars": len(raw),
        "finish_reason": metadata.get("finish_reason"),
        "json_inicial_valido": initially_valid,
        "recuperacion_aplicada": recovered,
        "claves_principales": sorted(parsed) if isinstance(parsed, dict) else [],
        "issue_iid": iid,
        "historia_id": story_id,
        "identificadores_conservados": iid == 10 and story_id == "HU-010",
        "funciones_especificadas": len(coverage.get("funciones_especificadas", [])),
        "funciones_incluidas": len(coverage.get("funciones_incluidas", [])),
        "funciones_faltantes": len(coverage.get("funciones_faltantes", [])),
        "funciones_evaluables": len(adequacy.get("funciones_evaluables", [])),
        "funciones_alineadas": len(adequacy.get("funciones_alineadas", [])),
        "objetivo_correcto": str(adequacy.get("objetivo_evaluado", "")).strip().casefold() == EXPECTED_OBJECTIVE.casefold(),
        "referencias_implementacion": any(marker in diagnostic_text for marker in implementation_markers),
        "mezcla_otra_historia": any(marker in diagnostic_text for marker in other_story_markers),
        "contrato": contract_diagnostic,
        "fallback": metadata.get("fallback", False),
    }, ensure_ascii=False))


def selected_agents(execute, agent):
    if not execute:
        return []
    if agent not in {"quality", "security"}:
        raise ValueError("Debe seleccionar explícitamente quality o security.")
    return [agent]


def summarize_error(label, exc, elapsed, input_chars):
    from agents.llm_invocation import clasificar_error_remoto
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    category = clasificar_error_remoto(exc)
    if status in {400, 413, 422}:
        category = "REMOTE_REQUEST_PREPARATION_ERROR"
    print(json.dumps({
        "agent": label,
        "error": category or "REMOTE_SERVICE_ERROR",
        "http_status": status,
        "elapsed_seconds": round(elapsed, 3),
        "input_chars": input_chars,
        "max_completion_tokens": int(os.getenv(
            f"REMOTE_{label.upper()}_MAX_COMPLETION_TOKENS", "2048",
        )),
        "finish_reason": None,
        "fallback": False,
    }, ensure_ascii=False))


def summarize(label, raw, elapsed):
    try:
        parsed = json.loads(raw)
        valid = True
        keys = sorted(parsed) if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        valid, keys = False, []
    print(json.dumps({
        "agent": label, "elapsed_seconds": round(elapsed, 3),
        "json_valid": valid, "keys": keys,
    }, ensure_ascii=False))


def summarize_security(raw, elapsed, input_chars):
    initially_valid = True
    recovered = False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        initially_valid = False
        try:
            parsed = analizar_respuesta_lote(raw, "Seguridad")
            recovered = True
        except ValueError:
            summarize_error("Security", ValueError("REMOTE_INVALID_RESPONSE"), elapsed, input_chars)
            return

    results = parsed.get("resultados", []) if isinstance(parsed, dict) else []
    item = results[0] if results and isinstance(results[0], dict) else {}
    metrics = item.get("metricas", {}) if isinstance(item.get("metricas"), dict) else {}
    ms01 = metrics.get("cobertura_seguridad", {})
    ms02 = metrics.get("clasificacion_datos", {})
    ms01 = ms01 if isinstance(ms01, dict) else {}
    ms02 = ms02 if isinstance(ms02, dict) else {}

    applicable = ms01.get("aspectos_aplicables", []) if isinstance(ms01.get("aspectos_aplicables"), list) else []
    documented = ms01.get("aspectos_documentados", []) if isinstance(ms01.get("aspectos_documentados"), list) else []
    partial = ms01.get("aspectos_parciales", []) if isinstance(ms01.get("aspectos_parciales"), list) else []
    missing = ms01.get("aspectos_faltantes", []) if isinstance(ms01.get("aspectos_faltantes"), list) else []
    identified = ms02.get("datos_identificados", []) if isinstance(ms02.get("datos_identificados"), list) else []
    classified = ms02.get("datos_clasificados", []) if isinstance(ms02.get("datos_clasificados"), list) else []
    unclassified = ms02.get("datos_sin_clasificacion", []) if isinstance(ms02.get("datos_sin_clasificacion"), list) else []
    aspect_text = " ".join(_texts({"aplicables": applicable, "documentados": documented})).casefold()
    missing_text = " ".join(_texts(missing)).casefold()
    data_text = " ".join(_texts(identified)).casefold()
    input_evidence = FAKE_CENTRAL_INPUT["resultados"][0]["evidencia_seguridad"]
    evidence_text = " ".join(_texts(input_evidence)).casefold()
    forbidden_data = tuple(marker for marker in (
        "historial médico", "prioridad", "dirección", "teléfono", "correo electrónico",
    ) if marker not in evidence_text)
    other_story_markers = ("registrar paciente", "agenda médica", "generar reporte", "consultar horario")
    auth_recognized = "autentic" in aspect_text and "autentic" not in missing_text
    authorization_recognized = any(x in aspect_text for x in ("autoriz", "rol")) and not any(x in missing_text for x in ("autoriz", "rol"))
    audit_recognized = "auditor" in aspect_text and "auditor" not in missing_text
    metadata = __import__("agents.llm_invocation", fromlist=["obtener_ultimos_metadatos"]).obtener_ultimos_metadatos("Security")
    print(json.dumps({
        "agent": "Security",
        "provider": metadata.get("provider", "groq"),
        "model": metadata.get("model"),
        "max_completion_tokens": int(os.getenv("REMOTE_SECURITY_MAX_COMPLETION_TOKENS", "2048")),
        "reasoning_effort": os.getenv("REMOTE_REASONING_EFFORT", "low"),
        "reasoning_format": os.getenv("REMOTE_REASONING_FORMAT", "hidden"),
        "elapsed_seconds": round(elapsed, 3),
        "input_chars": input_chars,
        "output_chars": len(raw),
        "finish_reason": metadata.get("finish_reason"),
        "json_inicial_valido": initially_valid,
        "recuperacion_aplicada": recovered,
        "claves_principales": sorted(parsed) if isinstance(parsed, dict) else [],
        "issue_iid": item.get("issue_iid"),
        "historia_id": item.get("historia_id"),
        "identificadores_conservados": item.get("issue_iid") == 10 and item.get("historia_id") == "HU-010",
        "cantidad_aspectos_aplicables": len(applicable),
        "cantidad_aspectos_documentados": len(documented),
        "cantidad_aspectos_parciales": len(partial),
        "cantidad_aspectos_faltantes": len(missing),
        "cantidad_datos_identificados": len(identified),
        "cantidad_datos_clasificados": len(classified),
        "cantidad_datos_sin_clasificacion": len(unclassified),
        "autenticacion_reconocida": auth_recognized,
        "autorizacion_reconocida": authorization_recognized,
        "auditoria_reconocida": audit_recognized,
        "datos_sensibles_reconocidos": bool(identified),
        "datos_inventados_detectados": any(marker in data_text for marker in forbidden_data),
        "mezcla_entre_historias": any(marker in " ".join(_texts(parsed)).casefold() for marker in other_story_markers),
        "contrato": diagnosticar_contrato_seguridad(parsed),
        "fallback": metadata.get("fallback", False),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute", action="store_true",
        help="Autoriza llamadas configuradas para Calidad y Seguridad.",
    )
    parser.add_argument("--agent", choices=("quality", "security"))
    args = parser.parse_args()
    if not args.execute:
        evidence = FAKE_CENTRAL_INPUT["resultados"][0].get("evidencia_seguridad", {})
        print(json.dumps({
            "diagnostico_preparado": True,
            "llamada_externa": False,
            "seguridad_recibe_evidencia": bool(evidence),
            "campos_evidencia_seguridad": sorted(evidence),
        }, ensure_ascii=False))
        return
    if not args.agent:
        parser.error("--execute requiere --agent quality o --agent security")
    if os.getenv("ENABLE_REMOTE_LLM", "false").casefold() != "true":
        raise SystemExit("ENABLE_REMOTE_LLM debe estar habilitado explícitamente.")
    os.environ["REMOTE_LLM_MAX_RETRIES"] = "0"

    payload = json.dumps(FAKE_CENTRAL_INPUT, ensure_ascii=False)
    if args.agent == "quality":
        from agents.quality_agent import analizar_calidad
        start = time.perf_counter()
        try:
            raw = analizar_calidad(payload)
        except Exception as exc:
            summarize_error("Quality", exc, time.perf_counter() - start, len(payload))
            return
        summarize_quality(raw, time.perf_counter() - start, len(payload))
    else:
        evidence = FAKE_CENTRAL_INPUT["resultados"][0].get("evidencia_seguridad", {})
        required_evidence = {
            "maneja_datos_sensibles", "autenticacion", "autorizacion_roles", "auditoria",
        }
        if not isinstance(evidence, dict) or not required_evidence.issubset(evidence):
            raise SystemExit("La historia ficticia no contiene la evidencia de Seguridad requerida.")
        print(json.dumps({
            "preflight_seguridad": True,
            "claves_evidencia_seguridad": sorted(evidence),
            "contenido_evidencia_mostrado": False,
        }, ensure_ascii=False))
        from agents.security_agent import analizar_seguridad
        start = time.perf_counter()
        try:
            raw = analizar_seguridad(payload)
        except Exception as exc:
            summarize_error("Security", exc, time.perf_counter() - start, len(payload))
            return
        summarize_security(raw, time.perf_counter() - start, len(payload))


if __name__ == "__main__":
    main()
