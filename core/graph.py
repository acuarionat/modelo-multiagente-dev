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
from agents.design_central_agent import procesar_diseno_central
from agents.design_quality_agent import analizar_calidad_diseno
from agents.design_security_agent import analizar_seguridad_diseno
from agents.design_evaluator_agent import analizar_evaluador_diseno
from core.design_contract import (
    normalizar_elementos_responsables,
    validar_salida_central_diseno, validar_salida_calidad_diseno,
    validar_salida_seguridad_diseno, validar_salida_evaluador_diseno,
)
from core.design_metrics import (
    calcular_mc03, calcular_mc04, calcular_ms03, calcular_ms04,
    calcular_indice_calidad_diseno, calcular_indice_seguridad_diseno,
    determinar_estado_diseno,
)
from agents.coding_central_agent import procesar_codificacion_central
from agents.coding_quality_agent import analizar_calidad_codificacion
from agents.coding_security_agent import analizar_seguridad_codificacion
from agents.coding_evaluator_agent import analizar_evaluador_codificacion
from core.coding_contract import (
    validar_salida_central_codificacion, validar_salida_calidad_codificacion,
    validar_salida_seguridad_codificacion, validar_salida_evaluador_codificacion,
)
from core.coding_context import construir_contexto_codificacion
from core.coding_metrics import (
    calcular_mc05, calcular_ms05, calcular_ms06, calcular_ms07,
    calcular_indice_calidad_codigo, calcular_indice_seguridad_codigo,
    determinar_estado_codificacion,
)
from core.code_analysis.orchestrator import ejecutar_analizadores_seleccionados, obtener_evidencia_por_metrica
from core.code_analysis.secrets_analyzer import obtener_archivos_codigo_workspace
from core.testing_validation import validar_entrada_pruebas
from core.testing_metrics import calcular_metricas_pruebas, determinar_estado_pruebas, preparar_evidencia_pruebas
from core.testing_context import construir_contexto_pruebas
from core.testing_contract import (
    validar_salida_central_pruebas, validar_salida_calidad_pruebas,
    validar_salida_seguridad_pruebas, validar_salida_evaluador_pruebas,
)
from agents.testing_central_agent import procesar_pruebas_central
from agents.testing_quality_agent import analizar_calidad_pruebas
from agents.testing_security_agent import analizar_seguridad_pruebas
from agents.testing_evaluator_agent import analizar_evaluador_pruebas
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
    purgar_funciones_fuera_de_universo_calidad,
    purgar_clasificaciones_sin_fuente_seguridad,
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
                    if (
                        agent_name == "Calidad"
                        and semantic_diagnostic.get("error_category") == "REMOTE_SEMANTIC_OUT_OF_UNIVERSE"
                    ):
                        purged = purgar_funciones_fuera_de_universo_calidad(parsed, batch)
                        registrar_evento_grafo(
                            "quality_out_of_universe_purged", agent_name,
                            sub_batch=index, issue_ids=expected,
                            purged_count=purged,
                        )
                        semantic_diagnostic["valid"] = True
                        semantic_diagnostic["validation"] = "success"
                        semantic_diagnostic["error_category"] = None
                    elif (
                        agent_name == "Seguridad"
                        and semantic_diagnostic.get("error_category") == "REMOTE_SEMANTIC_CONTRADICTION"
                        and semantic_diagnostic.get("failed_semantic_rule") in (
                            "SECURITY_EXPLICIT_CLASSIFICATION_WITHOUT_SOURCE",
                            "SECURITY_INFERRED_CLASSIFICATION_COUNTED_AS_EXPLICIT",
                        )
                    ):
                        moved = purgar_clasificaciones_sin_fuente_seguridad(parsed, batch)
                        registrar_evento_grafo(
                            "security_classification_without_source_purged", agent_name,
                            sub_batch=index, issue_ids=expected,
                            moved_count=moved,
                        )
                        semantic_diagnostic["valid"] = True
                        semantic_diagnostic["validation"] = "success"
                        semantic_diagnostic["error_category"] = None
                    else:
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

# 1b. Definición de Nodos de Diseño (independientes de Requerimientos)

def nodo_design_central(state: AgentState):
    """Nodo Central de Diseño: establece la trazabilidad Requisito → Elemento de Diseño."""
    logger.info("▶ Iniciando Agente Central de Diseño...")
    registrar_evento_grafo("node_start", "Design_Central")
    start_time = time.time()

    design_context = state["design_context"]
    contexto = design_context[0]

    valid_requirement_codes = {
        requerimiento["codigo"] for requerimiento in contexto["requerimientos_contextualizados"]
    }
    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    # Si la salida incumple el contrato (p. ej. un requisito clasificado en ambos grupos) se
    # reintenta una sola vez; no se decide en Python a cuál grupo pertenece el requisito.
    for intento in (1, 2):
        respuesta = procesar_diseno_central(
            project_name=state["project_name"],
            issues_json_str=json.dumps(design_context, ensure_ascii=False),
            sprint_context=state["sprint_context"],
        )
        parsed = analizar_respuesta_lote(respuesta, "Design_Central")
        resultado = parsed["resultados"][0]

        for campo in ("trazabilidad_diseno", "requisitos_sin_relacion_evidente"):
            items = resultado.get(campo) or []
            vistos = set()
            deduplicados = []
            for item in items:
                requisito = item.get("requisito")
                if requisito in vistos:
                    logger.warning("Design_Central: requisito duplicado %r en %s — se elimina.", requisito, campo)
                    continue
                vistos.add(requisito)
                deduplicados.append(item)
            if len(deduplicados) != len(items):
                resultado[campo] = deduplicados

        # El LLM puede citar un ED que no existe en el Issue: se descarta esa referencia
        # (nunca se acepta). Si el requisito se queda sin ningún elemento real, pasa a
        # "sin relación evidente" en vez de abortar todo el análisis.
        trazabilidad_saneada = []
        for item in resultado.get("trazabilidad_diseno") or []:
            elementos = item.get("elementos_relacionados") or []
            validos = [e for e in elementos if e in valid_element_ids]
            descartados = [e for e in elementos if e not in valid_element_ids]
            if descartados:
                logger.warning(
                    "Design_Central: ED inexistente(s) %s descartado(s) del requisito %r.",
                    descartados, item.get("requisito"),
                )
            if validos:
                item["elementos_relacionados"] = validos
                trazabilidad_saneada.append(item)
            else:
                resultado.setdefault("requisitos_sin_relacion_evidente", []).append({
                    "requisito": item.get("requisito"),
                    "justificacion": (
                        "El Diseño no contiene un elemento existente que sustente la relación "
                        f"(el modelo refirió elementos inexistentes: {descartados})."
                    ),
                    "confianza": "baja",
                })
        resultado["trazabilidad_diseno"] = trazabilidad_saneada

        validacion = validar_salida_central_diseno(
            resultado, [contexto["issue_iid"]], valid_requirement_codes, valid_element_ids,
        )
        if validacion["valido"]:
            break
        if intento == 1:
            logger.warning(
                "Design_Central: salida inválida %s. Reintentando una sola vez.",
                validacion["errores"],
            )
            registrar_evento_grafo(
                "agent_retry", "Design_Central", reason=str(validacion["errores"]),
            )
    if not validacion["valido"]:
        raise ValueError(f"Design_Central: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central de Diseño completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Design_Central", elapsed_seconds=round(elapsed, 4))

    return {"design_central_result": resultado}


def nodo_design_quality(state: AgentState):
    """Nodo de Calidad de Diseño: evalúa MC-03 y MC-04 a partir de la salida del Central."""
    logger.info("▶ Iniciando Agente de Calidad de Diseño...")
    registrar_evento_grafo("node_start", "Design_Quality")
    start_time = time.time()

    design_context = state["design_context"]
    contexto = design_context[0]
    central_envelope = {
        "agente": "central_diseno",
        "etapa": "Diseño",
        "resultados": [state["design_central_result"]],
    }

    respuesta = analizar_calidad_diseno(
        resultado_central_json_str=json.dumps(central_envelope, ensure_ascii=False),
        contexto_json_str=json.dumps(design_context, ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Design_Quality")
    resultado = parsed["resultados"][0]

    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    mc04_section = (resultado.get("metricas") or {}).get("acoplamiento_componentes") or {}
    for comp in mc04_section.get("componentes_evaluados") or []:
        deps = comp.get("dependencias_consideradas") or []
        invalid_deps = [d for d in deps if d not in valid_element_ids]
        if invalid_deps:
            logger.warning(
                "Design_Quality: %s tiene dependencias_consideradas inexistentes %s — se eliminan.",
                comp.get("elemento_id"), invalid_deps,
            )
            comp["dependencias_consideradas"] = [d for d in deps if d in valid_element_ids]

    validacion = validar_salida_calidad_diseno(resultado.get("metricas", {}), valid_element_ids)
    if not validacion["valido"]:
        raise ValueError(f"Design_Quality: salida inválida: {validacion['errores']}")

    metricas = resultado.get("metricas", {})
    mc03_raw = metricas.get("completitud_descripcion", {})
    mc04_raw = metricas.get("acoplamiento_componentes", {})

    mc03_calculado = calcular_mc03(
        mc03_raw.get("elementos_documentados", []),
        mc03_raw.get("elementos_necesarios_faltantes", []),
    )
    mc04_calculado = calcular_mc04(mc04_raw.get("componentes_evaluados", []))

    design_quality_result = {
        "raw": resultado,
        "mc03": {
            "valor": mc03_calculado.get("valor"),
            "numerador": mc03_calculado.get("documentados"),
            "denominador": mc03_calculado.get("esperados"),
            "estado": "calculada" if mc03_calculado.get("valor") is not None else "no_evaluable",
        },
        "mc04": {
            "valor": mc04_calculado.get("valor"),
            "numerador": mc04_calculado.get("aceptables"),
            "denominador": mc04_calculado.get("evaluables"),
            "estado": "calculada" if mc04_calculado.get("valor") is not None else "no_evaluable",
        },
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad de Diseño completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Design_Quality", elapsed_seconds=round(elapsed, 4))

    return {"design_quality_result": design_quality_result}


def nodo_design_security(state: AgentState):
    """Nodo de Seguridad de Diseño: evalúa MS-03 y MS-04."""
    logger.info("▶ Iniciando Agente de Seguridad de Diseño...")
    registrar_evento_grafo("node_start", "Design_Security")
    start_time = time.time()

    design_context = state["design_context"]
    contexto = design_context[0]

    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }

    # Si la salida incumple el contrato (p. ej. un control aplicable sin clasificar como
    # definido o faltante) se reintenta una sola vez; no se completa ni se adivina la
    # clasificación porque alteraría MS-04.
    for intento in (1, 2):
        respuesta = analizar_seguridad_diseno(
            issues_json_str=json.dumps(design_context, ensure_ascii=False),
        )
        parsed = analizar_respuesta_lote(respuesta, "Design_Security")
        resultado = parsed["resultados"][0]

        for control in (resultado.get("cobertura_controles") or {}).get("controles_definidos", []):
            control["elementos_responsables"] = normalizar_elementos_responsables(control)
            control.pop("elemento_responsable", None)

        # Referencias a ED inexistentes (el LLM las inventa a pesar del prompt): se descartan
        # de las listas de IDs. Son datos de presentación; MS-03/MS-04 no dependen de ellas.
        cobertura_amenazas = resultado.get("cobertura_amenazas") or {}
        cobertura_controles = resultado.get("cobertura_controles") or {}
        grupos_ed = (
            [(i, "elementos_afectados", "amenaza") for i in cobertura_amenazas.get("amenazas_identificadas") or []]
            + [(i, "elementos_responsables", "control") for i in cobertura_controles.get("controles_definidos") or []]
        )
        for item, campo, etiqueta in grupos_ed:
            ids = item.get(campo)
            if not isinstance(ids, list):
                continue
            validos = [e for e in ids if e in valid_element_ids]
            if len(validos) != len(ids):
                logger.warning(
                    "Design_Security: ED inexistente(s) %s descartado(s) de %s en %s.",
                    [e for e in ids if e not in valid_element_ids], campo, etiqueta,
                )
                item[campo] = validos

        validacion = validar_salida_seguridad_diseno(
            resultado, contexto["issue_iid"], contexto["diseno_id"], valid_element_ids,
        )
        if validacion["valido"]:
            break
        if intento == 1:
            logger.warning(
                "Design_Security: salida inválida %s. Reintentando una sola vez.",
                validacion["errores"],
            )
            registrar_evento_grafo(
                "agent_retry", "Design_Security", reason=str(validacion["errores"]),
            )
    if not validacion["valido"]:
        raise ValueError(f"Design_Security: salida inválida: {validacion['errores']}")

    ms03_raw = resultado.get("cobertura_amenazas", {})
    ms04_raw = resultado.get("cobertura_controles", {})
    ms03_calculado = calcular_ms03(ms03_raw)
    ms04_calculado = calcular_ms04(ms04_raw)

    design_security_result = {
        "raw": resultado,
        "ms03": {
            "valor": ms03_calculado.get("valor"),
            "numerador": ms03_calculado.get("numerador"),
            "denominador": ms03_calculado.get("denominador"),
            "estado": ms03_calculado.get("estado_calculo"),
        },
        "ms04": {
            "valor": ms04_calculado.get("valor"),
            "numerador": ms04_calculado.get("numerador"),
            "denominador": ms04_calculado.get("denominador"),
            "estado": ms04_calculado.get("estado_calculo"),
        },
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad de Diseño completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Design_Security", elapsed_seconds=round(elapsed, 4))

    return {"design_security_result": design_security_result}


def nodo_design_evaluator(state: AgentState):
    """Nodo Evaluador de Diseño: consolida hallazgos a partir de métricas ya calculadas (solo lectura)."""
    logger.info("▶ Iniciando Agente Evaluador de Diseño...")
    registrar_evento_grafo("node_start", "Design_Evaluator")
    start_time = time.time()

    contexto = state["design_context"][0]
    quality_result = state["design_quality_result"]
    security_result = state["design_security_result"]

    entrada_evaluador = {
        "issue_iid": contexto["issue_iid"],
        "diseno_id": contexto["diseno_id"],
        "calidad": {
            "mc03": quality_result["mc03"],
            "mc04": quality_result["mc04"],
        },
        "seguridad": {
            "ms03": security_result["ms03"],
            "ms04": security_result["ms04"],
        },
        "evidencia_calidad": quality_result["raw"],
        "evidencia_seguridad": security_result["raw"],
    }

    valid_element_ids = {
        elemento["elemento_id"] for elemento in contexto["elementos_diseno"]
    }
    valid_requirement_codes = {
        requerimiento["codigo"] for requerimiento in contexto["requerimientos_contextualizados"]
    }

    # Si la salida incumple el contrato (p. ej. el LLM omite las listas de hallazgos) se
    # reintenta una sola vez. No se rellenan campos faltantes con [] porque un hallazgo
    # omitido falsearía el estado orientativo calculado por Python.
    for intento in (1, 2):
        respuesta = analizar_evaluador_diseno(
            issues_json_str=json.dumps([entrada_evaluador], ensure_ascii=False),
        )
        parsed = analizar_respuesta_lote(respuesta, "Design_Evaluator")
        resultado = parsed["resultados"][0]
        validacion = validar_salida_evaluador_diseno(
            resultado, contexto["issue_iid"], contexto["diseno_id"],
            valid_element_ids, valid_requirement_codes,
        )
        if validacion["valido"]:
            break
        if intento == 1:
            logger.warning(
                "Design_Evaluator: salida inválida %s. Reintentando una sola vez.",
                validacion["errores"],
            )
            registrar_evento_grafo(
                "agent_retry", "Design_Evaluator", reason=str(validacion["errores"]),
            )
    if not validacion["valido"]:
        raise ValueError(f"Design_Evaluator: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador de Diseño completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Design_Evaluator", elapsed_seconds=round(elapsed, 4))

    return {"design_evaluator_result": resultado}


def nodo_design_central_final(state: AgentState):
    """Nodo final de Diseño (determinístico, solo Python): índices, correcciones y estado orientativo."""
    logger.info("▶ Iniciando Nodo de Consolidación de Diseño (Final, solo Python)...")
    registrar_evento_grafo("node_start", "Design_Central_Final")
    start_time = time.time()

    contexto = state["design_context"][0]
    mc03 = state["design_quality_result"]["mc03"]
    mc04 = state["design_quality_result"]["mc04"]
    ms03 = state["design_security_result"]["ms03"]
    ms04 = state["design_security_result"]["ms04"]
    evaluador = state["design_evaluator_result"]

    indice_calidad = calcular_indice_calidad_diseno(mc03["valor"], mc04["valor"])
    indice_seguridad = calcular_indice_seguridad_diseno(ms03["valor"], ms04["valor"])

    estado = determinar_estado_diseno(
        indice_calidad=indice_calidad,
        indice_seguridad=indice_seguridad,
        correcciones_necesarias=evaluador["correcciones_necesarias"],
        precisiones_necesarias=evaluador["precisiones_necesarias"],
        oportunidades_mejora=evaluador["oportunidades_mejora"],
    )

    design_summary = {
        "issue_iid": contexto["issue_iid"],
        "diseno_id": contexto["diseno_id"],
        "metricas": {
            "MC-03": mc03,
            "MC-04": mc04,
            "MS-03": ms03,
            "MS-04": ms04,
        },
        "indice_calidad_diseno": indice_calidad,
        "indice_seguridad_diseno": indice_seguridad,
        "estado_orientativo": estado,
        "correcciones_necesarias": evaluador["correcciones_necesarias"],
        "precisiones_necesarias": evaluador["precisiones_necesarias"],
        "oportunidades_mejora": evaluador["oportunidades_mejora"],
        "matriz_metadata": {
            "matriz_version": state.get("matriz_version"),
            "matriz_fuente": state.get("matriz_fuente"),
            "matriz_estado": state.get("matriz_estado"),
            "requisitos_vigentes": state.get("requisitos_vigentes"),
        },
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Consolidación de Diseño completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Design_Central_Final", elapsed_seconds=round(elapsed, 4))

    return {"design_summary": design_summary}


def construir_grafo_diseno():
    """Grafo independiente para el flujo de Diseño. No reutiliza los nodos de Requerimientos."""
    workflow = StateGraph(AgentState)

    workflow.add_node("Design_Central", nodo_design_central)
    workflow.add_node("Design_Quality", nodo_design_quality)
    workflow.add_node("Design_Security", nodo_design_security)
    workflow.add_node("Design_Evaluator", nodo_design_evaluator)
    workflow.add_node("Design_Central_Final", nodo_design_central_final)

    workflow.set_entry_point("Design_Central")

    # Quality y Security son independientes entre sí (ninguno usa la salida del
    # otro), pero ambos llaman a Groq: se encadenan en secuencia para que
    # REMOTE_PACER siga espaciando las llamadas remotas y no se agoten los
    # tokens por minuto al ejecutarlos de forma concurrente.
    workflow.add_edge("Design_Central", "Design_Quality")
    workflow.add_edge("Design_Quality", "Design_Security")

    workflow.add_edge("Design_Security", "Design_Evaluator")
    workflow.add_edge("Design_Evaluator", "Design_Central_Final")
    workflow.add_edge("Design_Central_Final", END)

    app = workflow.compile()
    return app


# 1c. Definición de Nodos de Codificación (independientes de Requerimientos y de Diseño)

def nodo_coding_prepare(state: AgentState):
    """
    Nodo de preparación de Codificación: ejecuta ÚNICAMENTE las
    herramientas ya seleccionadas por
    core/code_analysis/tool_selector.py (coding_selected_tools) sobre el
    código ya localizado (integrations/code_repository_service.py,
    ejecutado antes del grafo), vía
    core/code_analysis/orchestrator.py::ejecutar_analizadores_seleccionados,
    y ensambla el contexto completo del COD.
    No es un agente LLM: solo herramientas locales y ensamblado determinístico.
    """
    logger.info("▶ Iniciando preparación de Codificación (herramientas de análisis)...")
    registrar_evento_grafo("node_start", "Coding_Prepare")
    start_time = time.time()

    issue_codificacion = state["coding_issues"][0]
    matriz_entrada = state["coding_matrix_input"]
    codigo_localizado = state["coding_codigo_localizado"]
    workspace = codigo_localizado["workspace"]
    herramientas_seleccionadas = state.get("coding_selected_tools") or {}
    repository_profile = state.get("coding_repository_profile") or {}

    try:
        evidencia_herramientas = ejecutar_analizadores_seleccionados(
            workspace, herramientas_seleccionadas, repository_profile,
            manifiesto_dependencias=codigo_localizado.get("manifiesto_dependencias"),
        )
        # Universo de archivos de código para MS-07 (calcular_ms07): debe
        # obtenerse aquí, mientras el workspace todavía existe, porque
        # nodo_coding_security (que calcula MS-07) corre después de que
        # este workspace temporal ya fue borrado.
        archivos_codigo_workspace = obtener_archivos_codigo_workspace(workspace)
    finally:
        import shutil
        shutil.rmtree(workspace, ignore_errors=True)

    registrar_evento_grafo(
        "coding_tools_summary",
        "Coding_Prepare",
        herramientas_ejecutadas={
            adaptador: resultado.get("estado")
            for adaptador, resultado in evidencia_herramientas.items()
        },
    )

    contexto = construir_contexto_codificacion(
        issue_codificacion, matriz_entrada, codigo_localizado, evidencia_herramientas,
    )

    elapsed = time.time() - start_time
    logger.info(f"✔ Preparación de Codificación completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Prepare", elapsed_seconds=round(elapsed, 4))

    return {
        "coding_context": [contexto],
        "coding_tool_results": evidencia_herramientas,
        "coding_archivos_codigo_workspace": archivos_codigo_workspace,
    }


def nodo_coding_central(state: AgentState):
    """Nodo Central de Codificación: valida coherencia declarado-vs-evidencia y relaciona COD con ED."""
    logger.info("▶ Iniciando Agente Central de Codificación...")
    registrar_evento_grafo("node_start", "Coding_Central")
    start_time = time.time()

    coding_context = state["coding_context"]
    contexto = coding_context[0]

    def medir(valor):
        texto = json.dumps(valor, ensure_ascii=False, default=str)
        return {
            "chars": len(texto),
            "bytes": len(texto.encode("utf-8")),
        }

    print("\n=== CODING_CONTEXT_SIZE ===")
    for campo, valor in contexto.items():
        medicion = medir(valor)
        print(f"{campo:35s} {medicion['chars']} chars / {medicion['bytes']} bytes")
    medicion_total = medir(coding_context)
    print(f"{'TOTAL coding_context':35s} {medicion_total['chars']} chars / {medicion_total['bytes']} bytes")

    archivos_localizados = contexto.get("archivos_localizados", [])
    rutas = [archivo["ruta"] for archivo in archivos_localizados]
    print("\n=== DIAGNOSTICO DE DUPLICACION ===")
    print("ARCHIVOS_LOCALIZADOS:", len(archivos_localizados))
    print("RUTAS_TOTALES:", len(rutas))
    print("RUTAS_UNICAS:", len(set(rutas)))

    respuesta = procesar_codificacion_central(
        project_name=state["project_name"],
        coding_context_json_str=json.dumps(coding_context, ensure_ascii=False),
        sprint_context=state["sprint_context"],
    )
    parsed = analizar_respuesta_lote(respuesta, "Coding_Central")
    resultado = parsed["resultados"][0]

    valid_element_ids = {
        item["elemento_id"] for item in contexto["elementos_diseno_contextualizados"]
    }
    valid_archivos = {
        archivo["ruta"] for archivo in contexto["archivos_localizados"] if archivo.get("estado") == "OK"
    }
    validacion = validar_salida_central_codificacion(
        resultado, [contexto["issue_iid"]], valid_element_ids, valid_archivos,
    )
    if not validacion["valido"]:
        raise ValueError(f"Coding_Central: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central de Codificación completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Central", elapsed_seconds=round(elapsed, 4))

    return {"coding_central_result": resultado}


def nodo_coding_quality(state: AgentState):
    """Nodo de Calidad de Codificación: MC-05 ya calculado por Python (Radon o ESLint, según lenguaje); el agente solo interpreta."""
    logger.info("▶ Iniciando Agente de Calidad de Codificación...")
    registrar_evento_grafo("node_start", "Coding_Quality")
    start_time = time.time()

    contexto = state["coding_context"][0]
    evidencia_mc05 = obtener_evidencia_por_metrica(state["coding_tool_results"])["MC-05"]
    mc05_calculado = calcular_mc05(evidencia_mc05)

    entrada = {
        "issue_iid": contexto["issue_iid"],
        "codificacion_id": contexto["codificacion_id"],
        "mc05": mc05_calculado,
        "evidencia_mc05": evidencia_mc05,
    }

    respuesta = analizar_calidad_codificacion(
        entrada_json_str=json.dumps([entrada], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Coding_Quality")
    resultado = parsed["resultados"][0]

    validacion = validar_salida_calidad_codificacion(resultado)
    if not validacion["valido"]:
        raise ValueError(f"Coding_Quality: salida inválida: {validacion['errores']}")

    coding_quality_result = {"raw": resultado, "mc05": mc05_calculado}

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad de Codificación completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Quality", elapsed_seconds=round(elapsed, 4))

    return {"coding_quality_result": coding_quality_result}


def compactar_ms05_para_agente(evidencia: dict) -> dict:
    """
    Compacta la evidencia de Semgrep (MS-05) para el contexto del agente
    de Seguridad: el cálculo determinístico (calcular_ms05, en
    coding_tool_results) ya usó la evidencia completa; aquí solo se
    reduce lo que se ENVÍA al LLM a un resumen + una muestra acotada de
    hallazgos, para no exceder el límite de tokens del proveedor.
    """
    evidencia = evidencia or {}
    datos = evidencia.get("datos") or {}
    hallazgos = datos.get("hallazgos") or []
    criticas = sum(1 for hallazgo in hallazgos if hallazgo.get("critico"))

    resumen = {
        "herramienta": evidencia.get("herramienta", "semgrep"),
        "estado": evidencia.get("estado"),
        "vulnerabilidades_criticas": criticas,
        "total_hallazgos": len(hallazgos),
        "hallazgos_relevantes": [],
        "motivo_error": evidencia.get("detalle_error"),
    }

    for item in hallazgos[:8]:
        resumen["hallazgos_relevantes"].append({
            "archivo": item.get("archivo"),
            "regla": item.get("regla"),
            "severidad": item.get("severidad"),
            "descripcion": item.get("mensaje"),
        })

    return resumen


def compactar_ms06_para_agente(evidencia: dict) -> dict:
    """Compacta la evidencia de dependencias (MS-06, pip-audit o npm audit) para el contexto del agente de Seguridad."""
    evidencia = evidencia or {}
    datos = evidencia.get("datos") or {}
    dependencias = datos.get("dependencias") or []
    vulnerables = [dependencia for dependencia in dependencias if dependencia.get("segura") is False]

    severidades = {
        "critical": 0, "high": 0, "moderate": 0, "medium": 0, "low": 0, "unknown": 0,
    }
    for dependencia in vulnerables:
        severidad = str(dependencia.get("severidad") or "unknown").lower()
        if severidad not in severidades:
            severidad = "unknown"
        severidades[severidad] += 1

    def _advisory(dependencia: dict):
        primera_vulnerabilidad = (dependencia.get("vulnerabilidades") or [{}])[0]
        return primera_vulnerabilidad.get("id")

    return {
        "herramienta": evidencia.get("herramienta", "npm-audit"),
        "estado": evidencia.get("estado"),
        "dependencias_analizadas": len(dependencias),
        "dependencias_seguras": len(dependencias) - len(vulnerables),
        "dependencias_vulnerables": len(vulnerables),
        "resumen_por_severidad": severidades,
        "muestras_relevantes": [
            {
                "nombre": dependencia.get("nombre"),
                "severidad": dependencia.get("severidad"),
                "advisory": _advisory(dependencia),
            }
            for dependencia in vulnerables[:8]
        ],
        "motivo_error": evidencia.get("detalle_error"),
    }


def compactar_ms07_para_agente(evidencia: dict) -> dict:
    """Compacta la evidencia de Gitleaks (MS-07) para el contexto del agente de Seguridad. NUNCA envía el secreto real."""
    evidencia = evidencia or {}
    hallazgos = evidencia.get("hallazgos") or []

    return {
        "herramienta": evidencia.get("herramienta", "gitleaks"),
        "estado": evidencia.get("estado"),
        "archivos_con_secretos": evidencia.get("total_archivos_con_secretos", 0),
        "secretos_detectados": evidencia.get("secretos_detectados", len(hallazgos)),
        "hallazgos_relevantes": [
            {
                "archivo": item.get("archivo"),
                "tipo": item.get("regla"),
                "linea": item.get("linea"),
                "valor": "[REDACTED]",
            }
            for item in hallazgos[:8]
        ],
        "motivo_error": evidencia.get("motivo"),
    }


def nodo_coding_security(state: AgentState):
    """Nodo de Seguridad de Codificación: MS-05/MS-06/MS-07 ya calculados por Python; el agente solo interpreta."""
    logger.info("▶ Iniciando Agente de Seguridad de Codificación...")
    registrar_evento_grafo("node_start", "Coding_Security")
    start_time = time.time()

    contexto = state["coding_context"][0]
    evidencia_por_metrica = obtener_evidencia_por_metrica(state["coding_tool_results"])
    evidencia_semgrep = evidencia_por_metrica["MS-05"]
    evidencia_ms06 = evidencia_por_metrica["MS-06"]
    evidencia_gitleaks = evidencia_por_metrica["MS-07"]
    ms05_calculado = calcular_ms05(evidencia_semgrep)
    ms06_calculado = calcular_ms06(evidencia_ms06)

    # Universo de archivos de código para MS-07: preferir el perfil del
    # repositorio si ya trae la lista; si no, usar el escaneo del
    # workspace ya hecho en Coding_Prepare (el workspace en sí ya no
    # existe para este nodo, por eso no se puede volver a recorrer aquí).
    repository_profile = state.get("coding_repository_profile") or {}
    archivos_codigo = (
        repository_profile.get("archivos_codigo")
        or state.get("coding_archivos_codigo_workspace")
        or []
    )
    ms07_calculado = calcular_ms07(evidencia_gitleaks, archivos_codigo)

    entrada = {
        "issue_iid": contexto["issue_iid"],
        "codificacion_id": contexto["codificacion_id"],
        "ms05": ms05_calculado,
        "ms06": ms06_calculado,
        "ms07": ms07_calculado,
        "evidencia_ms05": compactar_ms05_para_agente(evidencia_semgrep),
        "evidencia_ms06": compactar_ms06_para_agente(evidencia_ms06),
        "evidencia_ms07": compactar_ms07_para_agente(evidencia_gitleaks),
    }

    respuesta = analizar_seguridad_codificacion(
        entrada_json_str=json.dumps([entrada], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Coding_Security")
    resultado = parsed["resultados"][0]

    validacion = validar_salida_seguridad_codificacion(resultado)
    if not validacion["valido"]:
        raise ValueError(f"Coding_Security: salida inválida: {validacion['errores']}")

    coding_security_result = {
        "raw": resultado, "ms05": ms05_calculado, "ms06": ms06_calculado, "ms07": ms07_calculado,
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad de Codificación completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Security", elapsed_seconds=round(elapsed, 4))

    return {"coding_security_result": coding_security_result}


def nodo_coding_evaluator(state: AgentState):
    """Nodo Evaluador de Codificación: consolida hallazgos a partir de métricas ya calculadas (solo lectura)."""
    logger.info("▶ Iniciando Agente Evaluador de Codificación...")
    registrar_evento_grafo("node_start", "Coding_Evaluator")
    start_time = time.time()

    contexto = state["coding_context"][0]
    quality_result = state["coding_quality_result"]
    security_result = state["coding_security_result"]

    entrada_evaluador = {
        "issue_iid": contexto["issue_iid"],
        "codificacion_id": contexto["codificacion_id"],
        "calidad": {"mc05": quality_result["mc05"]},
        "seguridad": {
            "ms05": security_result["ms05"],
            "ms06": security_result["ms06"],
            "ms07": security_result["ms07"],
        },
        "interpretacion_calidad": quality_result["raw"],
        "interpretacion_seguridad": security_result["raw"],
    }

    respuesta = analizar_evaluador_codificacion(
        issues_json_str=json.dumps([entrada_evaluador], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Coding_Evaluator")
    resultado = parsed["resultados"][0]

    valid_element_ids = {
        item["elemento_id"] for item in contexto["elementos_diseno_contextualizados"]
    }
    validacion = validar_salida_evaluador_codificacion(
        resultado, contexto["issue_iid"], contexto["codificacion_id"], valid_element_ids,
    )
    if not validacion["valido"]:
        raise ValueError(f"Coding_Evaluator: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador de Codificación completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Evaluator", elapsed_seconds=round(elapsed, 4))

    return {"coding_evaluator_result": resultado}


def nodo_coding_central_final(state: AgentState):
    """Nodo final de Codificación (determinístico, solo Python): índices, correcciones y estado orientativo."""
    logger.info("▶ Iniciando Nodo de Consolidación de Codificación (Final, solo Python)...")
    registrar_evento_grafo("node_start", "Coding_Central_Final")
    start_time = time.time()

    contexto = state["coding_context"][0]
    mc05 = state["coding_quality_result"]["mc05"]
    ms05 = state["coding_security_result"]["ms05"]
    ms06 = state["coding_security_result"]["ms06"]
    ms07 = state["coding_security_result"]["ms07"]
    evaluador = state["coding_evaluator_result"]

    indice_calidad = calcular_indice_calidad_codigo(mc05["valor"])
    indice_seguridad = calcular_indice_seguridad_codigo(ms05["valor"], ms06["valor"], ms07["valor"])

    estado = determinar_estado_codificacion(
        indice_calidad=indice_calidad,
        indice_seguridad=indice_seguridad,
        correcciones_necesarias=evaluador["correcciones_necesarias"],
        precisiones_necesarias=evaluador["precisiones_necesarias"],
        oportunidades_mejora=evaluador["oportunidades_mejora"],
    )

    coding_summary = {
        "issue_iid": contexto["issue_iid"],
        "codificacion_id": contexto["codificacion_id"],
        "metricas": {
            "MC-05": mc05,
            "MS-05": ms05,
            "MS-06": ms06,
            "MS-07": ms07,
        },
        "indice_calidad_codigo": indice_calidad,
        "indice_seguridad_codigo": indice_seguridad,
        "estado_orientativo": estado,
        "correcciones_necesarias": evaluador["correcciones_necesarias"],
        "precisiones_necesarias": evaluador["precisiones_necesarias"],
        "oportunidades_mejora": evaluador["oportunidades_mejora"],
        "matriz_metadata": {
            "coding_matrix_version": state.get("coding_matrix_version"),
            "coding_matrix_source": state.get("coding_matrix_source"),
            "coding_matrix_status": state.get("coding_matrix_status"),
        },
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Consolidación de Codificación completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Coding_Central_Final", elapsed_seconds=round(elapsed, 4))

    return {"coding_summary": coding_summary}


def construir_grafo_codificacion():
    """Grafo independiente para el flujo de Codificación. No reutiliza los nodos de Requerimientos ni de Diseño."""
    workflow = StateGraph(AgentState)

    workflow.add_node("Coding_Prepare", nodo_coding_prepare)
    workflow.add_node("Coding_Central", nodo_coding_central)
    workflow.add_node("Coding_Quality", nodo_coding_quality)
    workflow.add_node("Coding_Security", nodo_coding_security)
    workflow.add_node("Coding_Evaluator", nodo_coding_evaluator)
    workflow.add_node("Coding_Central_Final", nodo_coding_central_final)

    workflow.set_entry_point("Coding_Prepare")

    workflow.add_edge("Coding_Prepare", "Coding_Central")
    # Quality y Security son independientes entre sí (ninguno usa la salida
    # del otro), pero se encadenan en secuencia por el mismo motivo que
    # Diseño: REMOTE_PACER espacia las llamadas remotas (Groq) para no
    # agotar los tokens por minuto al ejecutarlas de forma concurrente.
    workflow.add_edge("Coding_Central", "Coding_Quality")
    workflow.add_edge("Coding_Quality", "Coding_Security")

    workflow.add_edge("Coding_Security", "Coding_Evaluator")
    workflow.add_edge("Coding_Evaluator", "Coding_Central_Final")
    workflow.add_edge("Coding_Central_Final", END)

    app = workflow.compile()
    return app


# 1d. Definición de Nodos de Pruebas (independientes de Requerimientos,
# Diseño y Codificación)

def nodo_testing_prepare(state: AgentState):
    """
    Nodo de preparación de Pruebas: valida el PRU-xxx, valida los COD
    declarados contra testing_input_matrix (Matriz de Trazabilidad —
    Etapa Codificación, entrada formal del state, no session_state),
    resuelve la trazabilidad heredada (PRU -> COD -> ED -> RF/RNF -> HU),
    prepara la evidencia y calcula MC-07/MC-08/MS-08/MS-09. No es un
    agente LLM: solo cálculo determinístico en Python.
    """
    logger.info("▶ Iniciando preparación de Pruebas (validación + métricas)...")
    registrar_evento_grafo("node_start", "Testing_Prepare")
    start_time = time.time()

    issue_pruebas = state["testing_issues"][0]
    matriz_entrada = state["testing_input_matrix"]

    validacion = validar_entrada_pruebas(issue_pruebas, matriz_entrada)
    evidencia = preparar_evidencia_pruebas(issue_pruebas)
    metricas = calcular_metricas_pruebas(evidencia)
    contexto = construir_contexto_pruebas(
        issue_pruebas, evidencia, metricas, validacion["trazabilidad_heredada"],
    )
    contexto["validacion_entrada"] = validacion

    elapsed = time.time() - start_time
    logger.info(f"✔ Preparación de Pruebas completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Prepare", elapsed_seconds=round(elapsed, 4))

    return {
        "testing_evidence": evidencia,
        "testing_metrics": metricas,
        "testing_context": [contexto],
    }


def nodo_testing_central(state: AgentState):
    """Nodo Central de Pruebas: contextualiza el PRU y confirma la trazabilidad heredada."""
    logger.info("▶ Iniciando Agente Central de Pruebas...")
    registrar_evento_grafo("node_start", "Testing_Central")
    start_time = time.time()

    testing_context = state["testing_context"]
    contexto = testing_context[0]

    respuesta = procesar_pruebas_central(
        project_name=state["project_name"],
        testing_context_json_str=json.dumps(testing_context, ensure_ascii=False),
        sprint_context=state["sprint_context"],
    )
    parsed = analizar_respuesta_lote(respuesta, "Testing_Central")
    resultado = parsed["resultados"][0]

    valid_codificaciones = set(contexto["trazabilidad"])
    validacion = validar_salida_central_pruebas(
        resultado, [contexto["issue_iid"]], valid_codificaciones,
    )
    if not validacion["valido"]:
        raise ValueError(f"Testing_Central: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central de Pruebas completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Central", elapsed_seconds=round(elapsed, 4))

    return {"testing_central_result": resultado}


def nodo_testing_quality(state: AgentState):
    """Nodo de Calidad de Pruebas: MC-07/MC-08 ya calculados por Python; el agente solo interpreta."""
    logger.info("▶ Iniciando Agente de Calidad de Pruebas...")
    registrar_evento_grafo("node_start", "Testing_Quality")
    start_time = time.time()

    contexto = state["testing_context"][0]
    metricas = contexto["metricas"]
    evidencia = contexto["evidencia"]

    entrada = {
        "issue_iid": contexto["issue_iid"],
        "prueba_id": contexto["prueba_id"],
        "mc07": metricas["MC-07"],
        "mc08": metricas["MC-08"],
        "evidencia_mc07": evidencia.get("pruebas_funcionales", []),
        "evidencia_mc08": evidencia.get("fallos", []),
    }

    respuesta = analizar_calidad_pruebas(
        entrada_json_str=json.dumps([entrada], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Testing_Quality")
    resultado = parsed["resultados"][0]

    validacion = validar_salida_calidad_pruebas(resultado)
    if not validacion["valido"]:
        raise ValueError(f"Testing_Quality: salida inválida: {validacion['errores']}")

    testing_quality_result = {"raw": resultado, "mc07": metricas["MC-07"], "mc08": metricas["MC-08"]}

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad de Pruebas completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Quality", elapsed_seconds=round(elapsed, 4))

    return {"testing_quality_result": testing_quality_result}


def nodo_testing_security(state: AgentState):
    """Nodo de Seguridad de Pruebas: MS-08/MS-09 ya calculados por Python; el agente solo interpreta."""
    logger.info("▶ Iniciando Agente de Seguridad de Pruebas...")
    registrar_evento_grafo("node_start", "Testing_Security")
    start_time = time.time()

    contexto = state["testing_context"][0]
    metricas = contexto["metricas"]
    evidencia = contexto["evidencia"]

    entrada = {
        "issue_iid": contexto["issue_iid"],
        "prueba_id": contexto["prueba_id"],
        "ms08": metricas["MS-08"],
        "ms09": metricas["MS-09"],
        "evidencia_ms08": evidencia.get("controles_seguridad", []),
        "evidencia_ms09": evidencia.get("pruebas_seguridad", []),
    }

    respuesta = analizar_seguridad_pruebas(
        entrada_json_str=json.dumps([entrada], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Testing_Security")
    resultado = parsed["resultados"][0]

    validacion = validar_salida_seguridad_pruebas(resultado)
    if not validacion["valido"]:
        raise ValueError(f"Testing_Security: salida inválida: {validacion['errores']}")

    testing_security_result = {"raw": resultado, "ms08": metricas["MS-08"], "ms09": metricas["MS-09"]}

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad de Pruebas completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Security", elapsed_seconds=round(elapsed, 4))

    return {"testing_security_result": testing_security_result}


def nodo_testing_evaluator(state: AgentState):
    """Nodo Evaluador de Pruebas: consolida hallazgos a partir de métricas ya calculadas (solo lectura)."""
    logger.info("▶ Iniciando Agente Evaluador de Pruebas...")
    registrar_evento_grafo("node_start", "Testing_Evaluator")
    start_time = time.time()

    contexto = state["testing_context"][0]
    quality_result = state["testing_quality_result"]
    security_result = state["testing_security_result"]

    entrada_evaluador = {
        "issue_iid": contexto["issue_iid"],
        "prueba_id": contexto["prueba_id"],
        "calidad": {"mc07": quality_result["mc07"], "mc08": quality_result["mc08"]},
        "seguridad": {"ms08": security_result["ms08"], "ms09": security_result["ms09"]},
        "interpretacion_calidad": quality_result["raw"],
        "interpretacion_seguridad": security_result["raw"],
    }

    respuesta = analizar_evaluador_pruebas(
        issues_json_str=json.dumps([entrada_evaluador], ensure_ascii=False),
    )
    parsed = analizar_respuesta_lote(respuesta, "Testing_Evaluator")
    resultado = parsed["resultados"][0]

    valid_codificaciones = set(contexto["trazabilidad"])
    validacion = validar_salida_evaluador_pruebas(
        resultado, contexto["issue_iid"], contexto["prueba_id"], valid_codificaciones,
    )
    if not validacion["valido"]:
        raise ValueError(f"Testing_Evaluator: salida inválida: {validacion['errores']}")

    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador de Pruebas completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Evaluator", elapsed_seconds=round(elapsed, 4))

    return {"testing_evaluator_result": resultado}


def nodo_testing_central_final(state: AgentState):
    """Nodo final de Pruebas (determinístico, solo Python): estado orientativo y consolidación."""
    logger.info("▶ Iniciando Nodo de Consolidación de Pruebas (Final, solo Python)...")
    registrar_evento_grafo("node_start", "Testing_Central_Final")
    start_time = time.time()

    contexto = state["testing_context"][0]
    metricas = contexto["metricas"]
    evaluador = state["testing_evaluator_result"]
    quality_result = state["testing_quality_result"]
    security_result = state["testing_security_result"]

    estado = determinar_estado_pruebas(metricas)

    testing_summary = {
        "prueba_id": contexto["prueba_id"],
        "issue_iid": contexto["issue_iid"],
        "codificaciones_relacionadas": contexto["codificaciones_relacionadas"],
        "estado_orientativo": estado,
        "metricas": metricas,
        "calidad": {
            "mc07": metricas["MC-07"],
            "mc08": metricas["MC-08"],
            "interpretacion": quality_result["raw"],
            "conclusion": evaluador.get("conclusion_calidad", ""),
        },
        "seguridad": {
            "ms08": metricas["MS-08"],
            "ms09": metricas["MS-09"],
            "interpretacion": security_result["raw"],
            "conclusion": evaluador.get("conclusion_seguridad", ""),
        },
        "correcciones_necesarias": evaluador["correcciones_necesarias"],
        "precisiones": evaluador["precisiones_necesarias"],
        "oportunidades_mejora": evaluador["oportunidades_mejora"],
        "trazabilidad": contexto["trazabilidad"],
        "conclusion": evaluador.get("recomendacion_revision", ""),
    }

    elapsed = time.time() - start_time
    logger.info(f"✔ Consolidación de Pruebas completada en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Testing_Central_Final", elapsed_seconds=round(elapsed, 4))

    return {"testing_summary": testing_summary}


def construir_grafo_pruebas():
    """Grafo independiente para el flujo de Pruebas. No reutiliza los nodos de Requerimientos, Diseño ni Codificación."""
    workflow = StateGraph(AgentState)

    workflow.add_node("Testing_Prepare", nodo_testing_prepare)
    workflow.add_node("Testing_Central", nodo_testing_central)
    workflow.add_node("Testing_Quality", nodo_testing_quality)
    workflow.add_node("Testing_Security", nodo_testing_security)
    workflow.add_node("Testing_Evaluator", nodo_testing_evaluator)
    workflow.add_node("Testing_Central_Final", nodo_testing_central_final)

    workflow.set_entry_point("Testing_Prepare")

    workflow.add_edge("Testing_Prepare", "Testing_Central")
    # Quality y Security son independientes entre sí, pero se encadenan en
    # secuencia por el mismo motivo que Diseño y Codificación: REMOTE_PACER
    # espacia las llamadas remotas (Groq) para no agotar los tokens por
    # minuto al ejecutarlas de forma concurrente.
    workflow.add_edge("Testing_Central", "Testing_Quality")
    workflow.add_edge("Testing_Quality", "Testing_Security")

    workflow.add_edge("Testing_Security", "Testing_Evaluator")
    workflow.add_edge("Testing_Evaluator", "Testing_Central_Final")
    workflow.add_edge("Testing_Central_Final", END)

    app = workflow.compile()
    return app


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
