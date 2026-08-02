import time
import logging
import os
from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.central_agent import procesar_ticket
from agents.quality_agent import analizar_calidad
from agents.security_agent import analizar_seguridad
from agents.evaluator_agent import evaluar_reportes
import json
from core.config import LOGS_DIR
from core.performance_audit import registrar_evento_grafo
from core.batch_contract import (
    calcular_metricas_agente, consolidar_lote, indexar_resultados,
    analizar_respuesta_lote, conciliar_ids_issues, validar_contenido_agente,
    validar_respuesta_lote,
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

# 1. Definición de Nodos

def nodo_central_inicial(state: AgentState):
    """Nodo inicial: El orquestador arranca el flujo para el lote."""
    logger.info("▶ Iniciando Agente Central (Init) para el lote...")
    registrar_evento_grafo("node_start", "Central_Init")
    start_time = time.time()
    
    project_name = state["project_name"]
    sprint_context = state["sprint_context"]
    issues_data = state["issues_data"]
    
    issues_json_str = json.dumps(issues_data, ensure_ascii=False)
    response = procesar_ticket(project_name, issues_json_str, sprint_context)
    parsed, response = _analizar_con_un_reintento(
        response, "Central",
        lambda: procesar_ticket(project_name, issues_json_str, sprint_context, num_predict_override=2800),
    )
    expected_ids = [int(x["id"]) for x in issues_data]
    titles = {x["titulo"]: int(x["id"]) for x in issues_data}
    def reparar(repair_ids):
        subset = [item for item in issues_data if int(item["id"]) in repair_ids]
        return procesar_ticket(project_name, json.dumps(subset, ensure_ascii=False), sprint_context)
    errors, content_errors = _validar_y_reparar(parsed, expected_ids, "Central", reparar, titles)
    response = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Init) completado en {elapsed:.2f} segundos.")
    registrar_evento_grafo("node_end", "Central_Init", elapsed_seconds=round(elapsed, 4))
        
    return {
        "central_init": response,
        "validation_errors": errors,
        "content_validation_errors": _combinar_errores_contenido({}, "Central", content_errors),
    }

def nodo_calidad(state: AgentState):
    """Nodo de Calidad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Calidad (Lote)...")
    registrar_evento_grafo("node_start", "Quality")
    start_time = time.time()
    
    req_text = state["central_init"]
    report_str = analizar_calidad(req_text)
    parsed, report_str = _analizar_con_un_reintento(
        report_str, "Calidad",
        lambda: analizar_calidad(req_text, num_predict_override=2400),
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    context_by_iid = {int(x["id"]): x for x in state["issues_data"]}
    central = analizar_respuesta_lote(req_text, "Central")
    def reparar(repair_ids):
        subset = [item for item in central["resultados"] if item.get("issue_iid") in repair_ids]
        return analizar_calidad(json.dumps({"agente": "central", "resultados": subset}, ensure_ascii=False))
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
    
    req_text = state["central_init"]
    report_str = analizar_seguridad(req_text)
    parsed, report_str = _analizar_con_un_reintento(
        report_str, "Seguridad",
        lambda: analizar_seguridad(req_text, num_predict_override=2800),
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    context_by_iid = {int(x["id"]): x for x in state["issues_data"]}
    central = analizar_respuesta_lote(req_text, "Central")
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
    
    # Ejecución secuencial optimizada para no saturar el hardware
    workflow.add_edge("Central_Init", "Quality")
    workflow.add_edge("Quality", "Security")
    workflow.add_edge("Security", "Evaluator")
    
    workflow.add_edge("Evaluator", "Central_Final")
    workflow.add_edge("Central_Final", END)
    
    app = workflow.compile()
    return app
