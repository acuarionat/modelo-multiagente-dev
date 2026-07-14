import time
import logging
import os
from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.central_agent import process_ticket
from agents.quality_agent import analyze_quality
from agents.security_agent import analyze_security
from agents.evaluator_agent import evaluate_reports
import json
from core.config import LOGS_DIR
from core.performance_audit import log_graph_event
from core.batch_contract import (
    consolidate_batch, parse_batch_response, reconcile_issue_ids,
    validate_batch_response,
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

# 1. Definición de Nodos

def node_central_init(state: AgentState):
    """Nodo inicial: El orquestador arranca el flujo para el lote."""
    logger.info("▶ Iniciando Agente Central (Init) para el lote...")
    log_graph_event("node_start", "Central_Init")
    start_time = time.time()
    
    project_name = state["project_name"]
    sprint_context = state["sprint_context"]
    issues_data = state["issues_data"]
    
    issues_json_str = json.dumps(issues_data, ensure_ascii=False)
    response = process_ticket(project_name, issues_json_str, sprint_context)
    parsed = parse_batch_response(response, "Central")
    expected_ids = [int(x["id"]) for x in issues_data]
    reconciliation = reconcile_issue_ids(
        parsed, expected_ids, "Central", {x["titulo"]: int(x["id"]) for x in issues_data}
    )
    for note in reconciliation:
        logger.warning(note)
    errors = validate_batch_response(parsed, set(expected_ids), "Central")
    response = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Init) completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Central_Init", elapsed_seconds=round(elapsed, 4))
        
    return {"central_init": response, "validation_errors": errors}

def node_quality(state: AgentState):
    """Nodo de Calidad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Calidad (Lote)...")
    log_graph_event("node_start", "Quality")
    start_time = time.time()
    
    req_text = state["central_init"]
    report_str = analyze_quality(req_text)
    
    parsed = parse_batch_response(report_str, "Calidad")
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    for note in reconcile_issue_ids(parsed, expected_ids, "Calidad"):
        logger.warning(note)
    errors = validate_batch_response(parsed, set(expected_ids), "Calidad")
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Quality", elapsed_seconds=round(elapsed, 4))
        
    return {"quality_report": final_report, "validation_errors": state.get("validation_errors", []) + errors}

def node_security(state: AgentState):
    """Nodo de Seguridad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Seguridad (Lote)...")
    log_graph_event("node_start", "Security")
    start_time = time.time()
    
    req_text = state["central_init"]
    report_str = analyze_security(req_text)
    
    parsed = parse_batch_response(report_str, "Seguridad")
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    for note in reconcile_issue_ids(parsed, expected_ids, "Seguridad"):
        logger.warning(note)
    errors = validate_batch_response(parsed, set(expected_ids), "Seguridad")
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Security", elapsed_seconds=round(elapsed, 4))
        
    return {"security_report": final_report, "validation_errors": state.get("validation_errors", []) + errors}

def node_evaluator(state: AgentState):
    """Nodo evaluador: Revisa calidad y seguridad para el lote."""
    logger.info("▶ Iniciando Agente Evaluador (Lote)...")
    log_graph_event("node_start", "Evaluator")
    start_time = time.time()
    
    eval_result = evaluate_reports(state["quality_report"], state["security_report"])
    parsed = parse_batch_response(eval_result, "Evaluador")
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    for note in reconcile_issue_ids(parsed, expected_ids, "Evaluador"):
        logger.warning(note)
    errors = validate_batch_response(parsed, set(expected_ids), "Evaluador")
    eval_result = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Evaluator", elapsed_seconds=round(elapsed, 4))
        
    return {"evaluation": eval_result, "validation_errors": state.get("validation_errors", []) + errors}

def node_central_final(state: AgentState):
    """Nodo final (Determinístico): Consolida el lote con Python sin llamar al LLM."""
    logger.info("▶ Iniciando Nodo de Consolidación Central (Final, solo Python)...")
    log_graph_event("node_start", "Central_Final")
    start_time = time.time()
    
    expected = {int(x["id"]) for x in state["issues_data"]}
    final = consolidate_batch(
        expected,
        parse_batch_response(state["central_init"], "Central"),
        parse_batch_response(state["quality_report"], "Calidad"),
        parse_batch_response(state["security_report"], "Seguridad"),
        parse_batch_response(state["evaluation"], "Evaluador"),
        state.get("validation_errors", []),
    )
    final_report = json.dumps(final, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Consolidación Central completada en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Central_Final", elapsed_seconds=round(elapsed, 4))
        
    return {"final_report": final_report}

# 2. Construcción del Grafo

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("Central_Init", node_central_init)
    workflow.add_node("Quality", node_quality)
    workflow.add_node("Security", node_security)
    workflow.add_node("Evaluator", node_evaluator)
    workflow.add_node("Central_Final", node_central_final)
    
    workflow.set_entry_point("Central_Init")
    
    # Ejecución secuencial optimizada para no saturar el hardware
    workflow.add_edge("Central_Init", "Quality")
    workflow.add_edge("Quality", "Security")
    workflow.add_edge("Security", "Evaluator")
    
    workflow.add_edge("Evaluator", "Central_Final")
    workflow.add_edge("Central_Final", END)
    
    app = workflow.compile()
    return app
