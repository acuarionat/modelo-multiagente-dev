import time
import logging
import os
from copy import deepcopy
from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.central_agent import procesar_central_en_sublotes
from agents.quality_agent import analizar_calidad
from agents.security_agent import analizar_seguridad
from agents.evaluator_agent import evaluar_reportes
import json
from datetime import datetime
from core.config import LOGS_DIR
from core.performance_audit import (
    registrar_evento_grafo, registrar_evento_sublote_remoto, registrar_motivo_reparacion,
)
from core.batch_contract import (
    calcular_metricas_agente, consolidar_lote, indexar_resultados,
    analizar_respuesta_lote, conciliar_ids_issues, validar_contenido_agente,
    validar_respuesta_lote, completar_requerimientos_explicitos_faltantes,
    normalizar_tipo_requerimiento, diagnosticar_contrato_calidad_llm,
    diagnosticar_contrato_seguridad_llm, es_funcion_principal_evaluable,
    diagnosticar_estructura_seguridad_llm, resumir_seguridad_post_python,
    validar_semantica_calidad_llm, validar_semantica_seguridad_llm,
    obtener_universo_funcional_calidad, normalizar_iid,
    descartar_grupos_genericos_sin_datos_canonicos,
)

# Configuración del logger
log_file = os.path.join(LOGS_DIR, "execution.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CentralIncompleteBatchError(RuntimeError):
    category = "CENTRAL_INCOMPLETE_BATCH"
    agent = "Central_Init"
    stage_reached = "central_validation"

    def __init__(self, *, expected_issue_ids, received_issue_ids, audit):
        self.expected_issue_ids = list(expected_issue_ids)
        self.received_issue_ids = list(received_issue_ids)
        self.missing_issue_ids = [
            iid for iid in self.expected_issue_ids if iid not in set(self.received_issue_ids)
        ]
        self.incomplete_issue_ids = list(self.missing_issue_ids)
        self.failed_sub_batches = [
            record.get("sub_batch") for record in audit.get("records", [])
            if record.get("status") != "success"
        ]
        self.selective_repairs_attempted = sum(
            bool(record.get("selective_repair")) for record in audit.get("records", [])
        )
        missing_hu = ", ".join(f"HU-{iid:03d}" for iid in self.missing_issue_ids)
        super().__init__(
            f"Central no recuperó todas las historias del lote. Faltantes: {missing_hu}. "
            "Las etapas de Calidad, Seguridad y Evaluación no fueron ejecutadas."
        )


def _persistir_fallo_central(error, audit):
    """Persiste únicamente identidad y auditoría técnica antes de propagar el fallo."""
    from core.execution_summary import persist_sanitized_execution_summary
    from core.performance_audit import obtener_contadores
    counters = obtener_contadores()
    partial = counters.get("resumen_parcial_central", {})
    execution_id = datetime.now().strftime("central-incomplete-%Y%m%d-%H%M%S-%f")
    payload = {
        "execution_id": execution_id,
        "estado_tecnico": "incompleto",
        "etapa_alcanzada": "central_validation",
        "stage_reached": "central_validation",
        "error_category": error.category,
        "expected_issue_ids": error.expected_issue_ids,
        "received_issue_ids": error.received_issue_ids,
        "missing_issue_ids": error.missing_issue_ids,
        "incomplete_issue_ids": error.incomplete_issue_ids,
        "failed_sub_batches": error.failed_sub_batches,
        "selective_repairs_attempted": error.selective_repairs_attempted,
        "selective_repairs_completed": partial.get("selective_repairs_completed", 0),
        "repair_reasons": counters.get("motivos_reparacion", {}),
        "central_sub_batches": audit.get("records", []),
        "call_durations": [record.get("elapsed_seconds") for record in audit.get("records", [])],
        "central_status": "failed",
        "downstream_agents_executed": False,
        "documents_generated": False,
        "artefactos": {},
        "gitlab_usado": False,
    }
    path = persist_sanitized_execution_summary(payload, os.getenv("TEMP") or None)
    error.summary_path = str(path)
    return path


def preparar_entrada_calidad(central_init, issues_data):
    """
    Construye el payload de Calidad exclusivamente desde las
    Historias de Usuario originales.

    La salida del Central se utiliza únicamente para determinar
    cuáles historias continúan siendo procesables, pero ningún
    contenido formalizado por Central se incorpora como evidencia
    para MC-01 o MC-02.
    """
    from core.batch_contract import (
        obtener_universo_funcional_original,
        normalizar_iid,
    )

    central_parsed = analizar_respuesta_lote(
        central_init,
        "Central",
    )

    central_by_iid = indexar_resultados(
        central_parsed
    )

    resultados_calidad = []
    central_errors = []
    by_issue_audit = []

    for issue in issues_data:
        if not isinstance(issue, dict):
            continue

        iid = normalizar_iid(
            issue.get("issue_iid")
            or issue.get("id")
        )

        if iid is None:
            logger.warning(
                "Historia original sin issue_iid válido; "
                "no se incorpora al payload de Calidad."
            )
            continue

        central_item = central_by_iid.get(iid)

        # Conserva la política existente:
        # una falla individual del Central no continúa hacia Calidad.
        if (
            isinstance(central_item, dict)
            and str(
                central_item.get("status", "")
            ).strip().casefold() == "error"
        ):
            central_errors.append(
                deepcopy(central_item)
            )
            continue

        universe = obtener_universo_funcional_original(
            issue
        )

        resultado = {
            "issue_iid": iid,
            "historia_id": str(
                issue.get("historia_id") or ""
            ),
            "titulo": str(
                issue.get("titulo") or ""
            ),
            "actor": str(
                issue.get("actor") or ""
            ),
            "funcionalidad": str(
                issue.get("funcionalidad") or ""
            ),
            "objetivo": str(
                issue.get("objetivo") or ""
            ),
            "criterios_aceptacion": deepcopy(
                issue.get(
                    "criterios_aceptacion",
                    [],
                )
            ),
            "restricciones": deepcopy(
                issue.get(
                    "restricciones",
                    [],
                )
            ),
            "observaciones": deepcopy(
                issue.get(
                    "observaciones",
                    ""
                )
            ),
            "funciones_principales_evaluables": deepcopy(
                universe[
                    "funciones_principales_evaluables"
                ]
            ),
            "reglas_funcionales_contextuales": deepcopy(
                universe[
                    "reglas_funcionales_contextuales"
                ]
            ),
        }

        resultados_calidad.append(resultado)

        by_issue_audit.append({
            "issue_iid": iid,
            "main_function_count": len(
                universe[
                    "funciones_principales_evaluables"
                ]
            ),
            "contextual_rule_count": len(
                universe[
                    "reglas_funcionales_contextuales"
                ]
            ),
            "source": "historia_usuario_original",
        })

    payload = {
        "agente": "entrada_calidad",
        "resultados": resultados_calidad,
    }

    registrar_evento_grafo(
        "quality_input_prepared",
        "Quality",
        expected_stories=len(issues_data),
        found_stories=len(resultados_calidad),
        processed_issue_iids=[
            item["issue_iid"]
            for item in resultados_calidad
        ],
        mc01_functional_universe=sum(
            item["main_function_count"]
            for item in by_issue_audit
        ),
        mc02_evaluable_universe=sum(
            item["main_function_count"]
            for item in by_issue_audit
        ),
        by_issue=by_issue_audit,
        source="historia_usuario_original",
        central_formalization_included=False,
    )

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        central_errors,
    )


def _ejecutar_sublotes_remotos(req_text, agent_name, batch_size, invoke):
    from agents.llm_invocation import obtener_ultimos_metadatos
    from core.remote_execution import (
        RemoteBatchError, dividir_payload_en_sublotes, remote_single_attempt,
        validar_sublote_estricto,
    )
    payload = analizar_respuesta_lote(req_text, "Central")
    batches = dividir_payload_en_sublotes(payload, batch_size)
    consolidated = []
    for index, batch in enumerate(batches, 1):
        expected = [int(item["issue_iid"]) for item in batch["resultados"]]
        started_at = time.time()
        max_tokens = int(os.getenv(f"REMOTE_{agent_name.upper()}_MAX_COMPLETION_TOKENS", "2048"))
        common = {
            "sub_batch": index, "issue_ids": expected, "expected": expected,
            "max_completion_tokens": max_tokens, "started_at": started_at,
        }
        registrar_evento_sublote_remoto("remote_sub_batch_start", agent_name, **common, status="started")
        registrar_evento_sublote_remoto("remote_sub_batch_call_start", agent_name, **common, status="started")
        status = "interrupted"
        error = None
        received = []
        metadata = {}
        contract_diagnostic = {}
        llm_raw_diagnostic = []
        raw = ""
        try:
            with remote_single_attempt():
                raw = invoke(json.dumps(batch, ensure_ascii=False), index)
            metadata = obtener_ultimos_metadatos(
                "Quality" if agent_name == "Calidad" else "Security"
            )
            try:
                parsed = analizar_respuesta_lote(raw, agent_name)
            except ValueError as exc:
                raise RemoteBatchError(
                    "REMOTE_INVALID_RESPONSE", agent=agent_name,
                    sub_batch=index, issue_ids=expected,
                ) from exc
            ordered = validar_sublote_estricto(
                parsed, expected, agent=agent_name, sub_batch=index,
            )
            received = [int(item["issue_iid"]) for item in ordered]
            diagnostic = (
                diagnosticar_contrato_calidad_llm(parsed)
                if agent_name == "Calidad" else diagnosticar_contrato_seguridad_llm(parsed)
            )
            contract_diagnostic = diagnostic
            if validar_respuesta_lote(
                parsed, set(expected), agent_name,
                contract_stage="llm_raw",
            ):
                raise RemoteBatchError(
                    "REMOTE_CONTRACT_ERROR", agent=agent_name,
                    sub_batch=index, issue_ids=expected, received=received,
                    contract_diagnostic=diagnostic,
                )
            semantic_diagnostic = {}
            if agent_name in {"Calidad", "Seguridad"}:
                if agent_name == "Seguridad":
                    llm_raw_diagnostic = diagnosticar_estructura_seguridad_llm(parsed, batch)
                    normalized_issues = descartar_grupos_genericos_sin_datos_canonicos(parsed, batch)
                    if normalized_issues:
                        registrar_evento_grafo(
                            "security_generic_groups_discarded", "Seguridad",
                            issue_ids=normalized_issues,
                        )
                semantic_diagnostic = (
                    validar_semantica_calidad_llm(parsed, batch)
                    if agent_name == "Calidad" else validar_semantica_seguridad_llm(parsed, batch)
                )
                if not semantic_diagnostic["valid"]:
                    raise RemoteBatchError(
                        semantic_diagnostic["error_category"], agent=agent_name,
                        sub_batch=index, issue_ids=expected, received=received,
                        semantic_diagnostic=semantic_diagnostic,
                    )
            consolidated.extend(ordered)
            status = "success"
            registrar_evento_sublote_remoto(
                "remote_sub_batch_call_end", agent_name, **common,
                elapsed_seconds=round(time.time() - started_at, 4),
                received=received, missing=[], finish_reason=metadata.get("finish_reason"),
                json_valid=_json_valido(raw), json_recovered=not _json_valido(raw), status=status,
            )
        except Exception as exc:
            error = exc
            status = "failed"
            received = list(getattr(exc, "received", received))
            missing = [iid for iid in expected if iid not in received]
            contract_diagnostic = getattr(exc, "contract_diagnostic", {})
            semantic_diagnostic = getattr(exc, "semantic_diagnostic", {})
            registrar_evento_sublote_remoto(
                "remote_sub_batch_error", agent_name, **common,
                elapsed_seconds=round(time.time() - started_at, 4), received=received,
                missing=missing, finish_reason=getattr(exc, "finish_reason", None) or metadata.get("finish_reason"),
                json_valid=_json_valido(raw), json_recovered=False, status=status,
                error_category=getattr(exc, "category", type(exc).__name__),
                http_status=getattr(exc, "http_status", None),
                retry_after_seconds=getattr(exc, "retry_after_seconds", None),
                expected_issue_ids=expected, received_issue_ids=received,
                identity_validation="success" if received else "failed",
                contract_validation=(
                    "failed" if getattr(exc, "category", None) == "REMOTE_CONTRACT_ERROR" else
                    "success" if semantic_diagnostic else "not_reached"
                ),
                failed_validator=(
                    "validar_respuesta_lote" if getattr(exc, "category", None) == "REMOTE_CONTRACT_ERROR" else
                    f"validar_semantica_{'calidad' if agent_name == 'Calidad' else 'seguridad'}_llm"
                    if semantic_diagnostic.get("validation") == "failed" else None
                ),
                missing_fields=contract_diagnostic.get("missing_fields", []),
                invalid_types=contract_diagnostic.get("invalid_types", []),
                premature_fields=contract_diagnostic.get("premature_fields", []),
                empty_but_valid_fields=contract_diagnostic.get("empty_but_valid_fields", []),
                alias_fields_detected=contract_diagnostic.get("alias_fields_detected", []),
                contract_stage=contract_diagnostic.get("contract_stage"),
                semantic_validation=semantic_diagnostic.get("validation", "not_reached"),
                semantic_error_category=semantic_diagnostic.get("error_category"),
                semantic_by_issue=semantic_diagnostic.get("by_issue", []),
                failed_semantic_rule=semantic_diagnostic.get("failed_semantic_rule"),
                semantic_subcategory=semantic_diagnostic.get("semantic_subcategory"),
                failed_issue_iid=semantic_diagnostic.get("failed_issue_iid"),
                pending_semantic_validation=semantic_diagnostic.get("pending_semantic_validation", []),
                stage_reached=semantic_diagnostic.get("stage_reached"),
                security_llm_raw_diagnostic=llm_raw_diagnostic,
                security_normalized_summary=semantic_diagnostic.get("by_issue", []),
            )
            raise
        finally:
            registrar_evento_sublote_remoto(
                "remote_sub_batch_end", agent_name, **common,
                elapsed_seconds=round(time.time() - started_at, 4), received=received,
                missing=[iid for iid in expected if iid not in received],
                finish_reason=getattr(error, "finish_reason", None) or metadata.get("finish_reason"),
                json_valid=_json_valido(raw), json_recovered=False, status=status,
                error_category=getattr(error, "category", None),
                http_status=getattr(error, "http_status", None),
                retry_after_seconds=getattr(error, "retry_after_seconds", None),
                expected_issue_ids=expected, received_issue_ids=received,
                identity_validation="success" if received == expected else "failed",
                contract_validation=(
                    "success" if status == "success" or semantic_diagnostic else
                    "failed" if getattr(error, "category", None) == "REMOTE_CONTRACT_ERROR" else
                    "not_reached"
                ),
                failed_validator=(
                    "validar_respuesta_lote" if getattr(error, "category", None) == "REMOTE_CONTRACT_ERROR" else
                    f"validar_semantica_{'calidad' if agent_name == 'Calidad' else 'seguridad'}_llm"
                    if semantic_diagnostic.get("validation") == "failed" else None
                ),
                missing_fields=contract_diagnostic.get("missing_fields", []),
                invalid_types=contract_diagnostic.get("invalid_types", []),
                premature_fields=contract_diagnostic.get("premature_fields", []),
                empty_but_valid_fields=contract_diagnostic.get("empty_but_valid_fields", []),
                alias_fields_detected=contract_diagnostic.get("alias_fields_detected", []),
                contract_stage=contract_diagnostic.get("contract_stage"),
                semantic_validation=(
                    "success" if status == "success" and agent_name in {"Calidad", "Seguridad"} else
                    semantic_diagnostic.get("validation", "not_reached")
                ),
                semantic_error_category=semantic_diagnostic.get("error_category"),
                semantic_by_issue=semantic_diagnostic.get("by_issue", []),
                failed_semantic_rule=semantic_diagnostic.get("failed_semantic_rule"),
                semantic_subcategory=semantic_diagnostic.get("semantic_subcategory"),
                failed_issue_iid=semantic_diagnostic.get("failed_issue_iid"),
                pending_semantic_validation=semantic_diagnostic.get("pending_semantic_validation", []),
                stage_reached=semantic_diagnostic.get("stage_reached"),
                security_llm_raw_diagnostic=llm_raw_diagnostic,
                security_normalized_summary=semantic_diagnostic.get("by_issue", []),
            )
    return {"agente": agent_name.casefold(), "resultados": consolidated}


def _json_valido(raw):
    try:
        json.loads(raw)
        return True
    except (TypeError, json.JSONDecodeError):
        return False


def _analizar_con_un_reintento(raw_response, agent_name, retry_call):
    try:
        return analizar_respuesta_lote(raw_response, agent_name), raw_response
    except ValueError as first_error:
        logger.warning("%s Reintentando una sola vez con mayor presupuesto.", first_error)
        registrar_evento_grafo("agent_retry", agent_name, reason=str(first_error))
        retry_response = retry_call()
        return analizar_respuesta_lote(retry_response, f"{agent_name} (reintento)"), retry_response


def _combinar_reparacion(base, repair):
    repaired = indexar_resultados(repair)
    base["resultados"] = [
        repaired.get(item.get("issue_iid"), item)
        for item in base.get("resultados", [])
        if isinstance(item, dict)
    ]
    existing = {item.get("issue_iid") for item in base["resultados"]}
    base["resultados"].extend(item for iid, item in repaired.items() if iid not in existing)


def diagnosticar_reparacion_central(parsed, expected_stories):
    """Describe fallos estructurales sin incluir la respuesta completa."""
    indexed = indexar_resultados(parsed)
    diagnostics = []
    for iid, story_id in expected_stories.items():
        if iid in indexed:
            continue
        diagnostics.append({
            "issue_iid": iid,
            "historia_id": story_id,
            "campos_fallidos": [{
                "campo": f"resultados[issue_iid={iid}]",
                "tipo_esperado": "objeto",
                "tipo_recibido": "ausente",
                "valor": "ausente",
            }],
            "categoria_error": "HISTORIA_AUSENTE_EN_RESULTADOS",
            "reparable_en_python": False,
            "reparacion_llm_necesaria": True,
        })
    return diagnostics


def _validar_y_reparar(
    parsed, expected_ids, agent_name, funcion_reparacion, expected_titles=None,
    context_by_iid=None,
):
    for note in conciliar_ids_issues(parsed, expected_ids, agent_name, expected_titles):
        logger.warning(note)
    calcular_metricas_agente(parsed, agent_name, context_by_iid)
    content_errors = validar_contenido_agente(parsed, agent_name)
    missing = set(expected_ids) - set(indexar_resultados(parsed))
    # Los campos textuales secundarios generan advertencias, no nuevas llamadas.
    # Sólo una historia completamente ausente justifica una reparación selectiva.
    repair_ids = sorted(missing)
    if repair_ids:
        registrar_motivo_reparacion(
            f"{agent_name}_Batch", repair_ids, "HISTORIA_AUSENTE_EN_RESULTADOS",
        )
        logger.warning("%s: reparación selectiva para Issues %s.", agent_name, repair_ids)
        repair = analizar_respuesta_lote(funcion_reparacion(repair_ids), f"{agent_name} (reparación)")
        repair_titles = None
        if expected_titles:
            repair_titles = {title: iid for title, iid in expected_titles.items() if iid in repair_ids}
        for note in conciliar_ids_issues(repair, repair_ids, f"{agent_name} (reparación)", repair_titles):
            logger.warning(note)
        calcular_metricas_agente(repair, agent_name, context_by_iid)
        _combinar_reparacion(parsed, repair)
        calcular_metricas_agente(parsed, agent_name, context_by_iid)
        content_errors = validar_contenido_agente(parsed, agent_name)
    structural_errors = validar_respuesta_lote(parsed, set(expected_ids), agent_name)
    return structural_errors, content_errors


def _combinar_errores_contenido(previous, agent_name, current):
    merged = {int(iid): list(messages) for iid, messages in (previous or {}).items()}
    for iid, messages in current.items():
        merged.setdefault(iid, []).extend(f"{agent_name}: {message}" for message in messages)
    return merged


def _adjuntar_evidencia_seguridad(parsed, issues_data):
    """Agrega evidencia original por issue_iid sin alterar la salida del Central."""
    evidence_by_iid = {}
    for issue in issues_data:
        try:
            iid = int(issue.get("id"))
        except (TypeError, ValueError):
            continue
        security = issue.get("seguridad")
        evidence_by_iid[iid] = deepcopy(security) if isinstance(security, dict) else {}

    for result in parsed.get("resultados", []):
        if not isinstance(result, dict):
            continue
        try:
            iid = int(result.get("issue_iid"))
        except (TypeError, ValueError):
            result["evidencia_seguridad"] = {}
            continue
        result["evidencia_seguridad"] = deepcopy(evidence_by_iid.get(iid, {}))


def _separar_errores_centrales(response_text):
    """Aparta sólo errores individuales explícitos; conserva las historias insuficientes."""
    parsed = analizar_respuesta_lote(response_text, "Central")
    errors, active = [], []
    for item in parsed.get("resultados", []):
        target = errors if str(item.get("status", "")).strip().casefold() == "error" else active
        target.append(item)
    parsed["resultados"] = active
    return json.dumps(parsed, ensure_ascii=False), errors


def _resultado_agente_no_evaluable(iid, agent_name):
    base = {
        "issue_iid": iid, "status": "error", "indice": None,
        "estado_medicion": "no_evaluable", "metricas": {},
        "motivo_sanitizado": "CENTRAL_RESULTADO_CON_ERROR_INDIVIDUAL",
    }
    if agent_name == "Evaluador":
        base.update({"veredicto": "ALERTA", "conclusion": "Revisión humana requerida.", "riesgos_criticos": [], "correcciones_obligatorias": []})
    return base

# 1. Definición de Nodos

def nodo_central_inicial(state: AgentState):
    """Nodo inicial: El orquestador arranca el flujo para el lote."""
    logger.info("▶ Iniciando Agente Central (Init) para el lote...")
    registrar_evento_grafo("node_start", "Central_Init")
    start_time = time.time()
    
    project_name = state["project_name"]
    sprint_context = state["sprint_context"]
    issues_data = state["issues_data"]
    
    parsed, _sub_batch_audit = procesar_central_en_sublotes(
        project_name, issues_data, sprint_context,
    )
    sources = {int(item["id"]): item for item in issues_data}
    for item in parsed.get("resultados", []):
        if not isinstance(item, dict):
            continue
        iid = normalizar_iid(item.get("issue_iid"))
        source = sources.get(iid)
        if source is None:
            continue
        validation = source.get("validacion_entrada", {})
        missing_fields = list(validation.get("campos_faltantes", []))
        explicit_error = str(item.get("status", "")).strip().casefold() == "error"
        item["status"] = "error" if explicit_error else (
            "informacion_insuficiente"
            if validation.get("estado") == "informacion_insuficiente" else "ok"
        )
        item.setdefault("motivo_sanitizado", "ESTRUCTURA_CENTRAL_INSUFICIENTE" if explicit_error else "")
        item.setdefault("campos_recuperados", [])
        item.setdefault("campos_ausentes", missing_fields)
        item["evaluacion_posterior_posible"] = not explicit_error
    expected_ids = [int(x["id"]) for x in issues_data]
    received_ids = [iid for iid in expected_ids if iid in set(indexar_resultados(parsed))]
    if received_ids != expected_ids:
        error = CentralIncompleteBatchError(
            expected_issue_ids=expected_ids,
            received_issue_ids=received_ids,
            audit=_sub_batch_audit,
        )
        _persistir_fallo_central(error, _sub_batch_audit)
        registrar_evento_grafo(
            "central_validation_failed", "Central_Init",
            error_category=error.category,
            expected_issue_ids=expected_ids, received_issue_ids=received_ids,
            missing_issue_ids=error.missing_issue_ids,
            stage_reached="central_validation",
        )
        raise error
    content_errors = validar_contenido_agente(parsed, "Central")
    errors = validar_respuesta_lote(parsed, set(expected_ids), "Central")
    _adjuntar_evidencia_seguridad(parsed, issues_data)
    response = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Init) completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Central_Init", elapsed_seconds=round(elapsed, 4))
        
    return {
        "central_init": response,
        "issues_data": issues_data,
        "validation_errors": errors,
        "content_validation_errors": _combinar_errores_contenido({}, "Central", content_errors),
    }

def nodo_calidad(state: AgentState):
    """Nodo de Calidad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Calidad (Lote)...")
    registrar_evento_grafo("node_start", "Quality")
    start_time = time.time()
    
    req_text, central_errors = preparar_entrada_calidad(
        state["central_init"],
        state["issues_data"]
    )
    from core.remote_execution import remote_batch_size, remote_enabled_for, reiniciar_pacing_remoto
    remote_mode = remote_enabled_for("quality")
    if remote_mode and json.loads(req_text)["resultados"]:
        reiniciar_pacing_remoto()
        parsed = _ejecutar_sublotes_remotos(
            req_text, "Calidad", remote_batch_size("quality"),
            lambda payload, sub_batch: analizar_calidad(payload, sub_batch=sub_batch),
        )
    elif json.loads(req_text)["resultados"]:
        report_str = analizar_calidad(req_text)
        parsed, report_str = _analizar_con_un_reintento(
            report_str, "Calidad",
            lambda: analizar_calidad(req_text, num_predict_override=2400),
        )
    else:
        parsed = {"agente": "calidad", "resultados": []}
    parsed["resultados"].extend(
        _resultado_agente_no_evaluable(int(item["issue_iid"]), "Calidad") for item in central_errors
    )
    from core.batch_contract import normalizar_iid
    expected_ids = []
    for issue in state["issues_data"]:
        iid = normalizar_iid(
            issue.get("issue_iid")
            or issue.get("id")
        )
        if iid is not None:
            expected_ids.append(iid)

    entrada_calidad = analizar_respuesta_lote(req_text, "Entrada Calidad")
    
    context_by_iid = {}
    
    for issue in state["issues_data"]:
        iid = normalizar_iid(
            issue.get("issue_iid")
            or issue.get("id")
        )
    
        if iid is None:
            continue
    
        context_by_iid[iid] = deepcopy(issue)
    if remote_mode:
        for note in conciliar_ids_issues(parsed, expected_ids, "Calidad"):
            logger.warning(note)
        calcular_metricas_agente(parsed, "Calidad", context_by_iid)
        content_errors = validar_contenido_agente(parsed, "Calidad")
        errors = validar_respuesta_lote(parsed, set(expected_ids), "Calidad")
        if errors:
            from core.remote_execution import RemoteBatchError
            raise RemoteBatchError(
                "REMOTE_CONTRACT_ERROR", agent="Calidad", sub_batch=0,
                issue_ids=expected_ids,
            )
    else:
        def reparar(repair_ids):
            subset = [
                item
                for item in entrada_calidad["resultados"]
                if normalizar_iid(
                    item.get("issue_iid")
                ) in repair_ids
            ]
            return analizar_calidad(
                json.dumps(
                    {
                        "agente": "entrada_calidad",
                        "resultados": subset,
                    },
                    ensure_ascii=False,
                )
            )
        errors, content_errors = _validar_y_reparar(
            parsed, expected_ids, "Calidad", reparar,
            context_by_iid=context_by_iid,
        )
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Quality", elapsed_seconds=round(elapsed, 4))
        
    return {
        "quality_report": final_report,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _combinar_errores_contenido(state.get("content_validation_errors"), "Calidad", content_errors),
    }

def nodo_seguridad(state: AgentState):
    """Nodo de Seguridad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Seguridad (Lote)...")
    registrar_evento_grafo("node_start", "Security")
    start_time = time.time()
    
    central_seguridad = analizar_respuesta_lote(state["central_init"], "Central")
    central_error_items = [
        item for item in central_seguridad.get("resultados", [])
        if str(item.get("status", "")).strip().casefold() == "error"
    ]
    central_seguridad["resultados"] = [
        item for item in central_seguridad.get("resultados", []) if item not in central_error_items
    ]
    from core.batch_contract import obtener_universo_datos_seguridad
    for result in central_seguridad.get("resultados", []):
        if isinstance(result, dict):
            evidence = result.get("evidencia_seguridad", {})
            result["datos_canonicos_identificados"] = obtener_universo_datos_seguridad(
                result, evidence,
            )
    req_text = json.dumps(central_seguridad, ensure_ascii=False)
    from core.remote_execution import remote_batch_size, remote_enabled_for
    remote_mode = remote_enabled_for("security")
    if remote_mode and central_seguridad["resultados"]:
        parsed = _ejecutar_sublotes_remotos(
            req_text, "Seguridad", remote_batch_size("security"),
            lambda payload, sub_batch: analizar_seguridad(payload, sub_batch=sub_batch),
        )
    elif central_seguridad["resultados"]:
        report_str = analizar_seguridad(req_text)
        parsed, report_str = _analizar_con_un_reintento(
            report_str, "Seguridad",
            lambda: analizar_seguridad(req_text, num_predict_override=2800),
        )
    else:
        parsed = {"agente": "seguridad", "resultados": []}
    parsed["resultados"].extend(
        _resultado_agente_no_evaluable(int(item["issue_iid"]), "Seguridad") for item in central_error_items
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    context_by_iid = {int(x["id"]): x for x in state["issues_data"]}
    central = analizar_respuesta_lote(req_text, "Central")
    if remote_mode:
        for note in conciliar_ids_issues(parsed, expected_ids, "Seguridad"):
            logger.warning(note)
        calcular_metricas_agente(parsed, "Seguridad", context_by_iid)
        registrar_evento_grafo(
            "security_post_python_summary", "Seguridad",
            contract_stage="post_python",
            by_issue=resumir_seguridad_post_python(parsed),
        )
        content_errors = validar_contenido_agente(parsed, "Seguridad")
        errors = validar_respuesta_lote(parsed, set(expected_ids), "Seguridad")
        if errors:
            from core.remote_execution import RemoteBatchError
            raise RemoteBatchError(
                "REMOTE_CONTRACT_ERROR", agent="Seguridad", sub_batch=0,
                issue_ids=expected_ids,
            )
    else:
        def reparar(repair_ids):
            subset = [item for item in central["resultados"] if item.get("issue_iid") in repair_ids]
            return analizar_seguridad(json.dumps({"agente": "central", "resultados": subset}, ensure_ascii=False))
        errors, content_errors = _validar_y_reparar(
            parsed, expected_ids, "Seguridad", reparar,
            context_by_iid=context_by_iid,
        )
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Security", elapsed_seconds=round(elapsed, 4))
        
    return {
        "security_report": final_report,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _combinar_errores_contenido(state.get("content_validation_errors"), "Seguridad", content_errors),
    }

def nodo_evaluador(state: AgentState):
    """Nodo evaluador: Revisa calidad y seguridad para el lote."""
    logger.info("▶ Iniciando Agente Evaluador (Lote)...")
    registrar_evento_grafo("node_start", "Evaluator")
    start_time = time.time()
    
    quality = analizar_respuesta_lote(state["quality_report"], "Calidad")
    security = analizar_respuesta_lote(state["security_report"], "Seguridad")
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    if expected_ids:
        eval_result = evaluar_reportes(state["quality_report"], state["security_report"])
        parsed, eval_result = _analizar_con_un_reintento(
            eval_result, "Evaluador",
            lambda: evaluar_reportes(state["quality_report"], state["security_report"], num_predict_override=1400),
        )
    else:
        parsed = {"agente": "evaluador", "resultados": []}
    def reparar(repair_ids):
        q_subset = [item for item in quality["resultados"] if item.get("issue_iid") in repair_ids]
        s_subset = [item for item in security["resultados"] if item.get("issue_iid") in repair_ids]
        return evaluar_reportes(
            json.dumps({"agente": "calidad", "resultados": q_subset}, ensure_ascii=False),
            json.dumps({"agente": "seguridad", "resultados": s_subset}, ensure_ascii=False),
        )
    errors, content_errors = _validar_y_reparar(parsed, expected_ids, "Evaluador", reparar)
    eval_result = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Evaluator", elapsed_seconds=round(elapsed, 4))
        
    return {
        "evaluation": eval_result,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _combinar_errores_contenido(state.get("content_validation_errors"), "Evaluador", content_errors),
    }

def nodo_central_final(state: AgentState):
    """Nodo final (Determinístico): Consolida el lote con Python sin llamar al LLM."""
    logger.info("▶ Iniciando Nodo de Consolidación Central (Final, solo Python)...")
    registrar_evento_grafo("node_start", "Central_Final")
    start_time = time.time()
    
    expected = {int(x["id"]) for x in state["issues_data"]}
    final = consolidar_lote(
        expected,
        analizar_respuesta_lote(state["central_init"], "Central"),
        analizar_respuesta_lote(state["quality_report"], "Calidad"),
        analizar_respuesta_lote(state["security_report"], "Seguridad"),
        analizar_respuesta_lote(state["evaluation"], "Evaluador"),
        state.get("validation_errors", []),
        state.get("content_validation_errors", {}),
        {int(item["id"]): item.get("validacion_entrada", {}) for item in state["issues_data"]},
        {int(item["id"]): item for item in state["issues_data"]},
    )
    final_report = json.dumps(final, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Consolidación Central completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Central_Final", elapsed_seconds=round(elapsed, 4))
        
    return {"final_report": final_report}

# 2. Construcción del Grafo

def construir_grafo():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("Central_Init", nodo_central_inicial)
    workflow.add_node("Quality", nodo_calidad)
    workflow.add_node("Security", nodo_seguridad)
    workflow.add_node("Evaluator", nodo_evaluador)
    workflow.add_node("Central_Final", nodo_central_final)
    
    workflow.set_entry_point("Central_Init")
    
    # Las evaluaciones se ejecutan de forma separada y secuencial.
    workflow.add_edge("Central_Init", "Quality")
    workflow.add_edge("Quality", "Security")
    workflow.add_edge("Security", "Evaluator")
    
    workflow.add_edge("Evaluator", "Central_Final")
    workflow.add_edge("Central_Final", END)
    
    app = workflow.compile()
    return app
