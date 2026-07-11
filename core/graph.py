import time
import logging
import os
from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.central_agent import process_ticket, synthesize_final_report
from agents.quality_agent import analyze_quality
from agents.security_agent import analyze_security
from agents.evaluator_agent import evaluate_reports
import json
from core.config import LOGS_DIR
from core.performance_audit import log_graph_event

# Configuración del logger
log_file = os.path.join(LOGS_DIR, "execution.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 1. Definición de Nodos

def node_central_init(state: AgentState):
    """Nodo inicial: El orquestador arranca el flujo."""
    logger.info("▶ Iniciando Agente Central (Init)...")
    log_graph_event("node_start", "Central_Init")
    start_time = time.time()
    
    project_name = state["project_name"]
    issue_data = state["issue_data"]
    
    issue_json_str = json.dumps(issue_data, ensure_ascii=False)
    response = process_ticket(project_name, issue_json_str)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Init) completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Central_Init", elapsed_seconds=round(elapsed, 4))
        
    return {"central_init": response}

def node_quality(state: AgentState):
    """Nodo paralelo: Calidad."""
    logger.info("▶ Iniciando Agente de Calidad (Ejecución en Paralelo)...")
    log_graph_event("node_start", "Quality")
    start_time = time.time()
    
    req_text = state["central_init"]
    report = analyze_quality(req_text)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Quality", elapsed_seconds=round(elapsed, 4))
        
    return {"quality_report": report}

def node_security(state: AgentState):
    """Nodo paralelo: Seguridad."""
    logger.info("▶ Iniciando Agente de Seguridad (Ejecución en Paralelo)...")
    log_graph_event("node_start", "Security")
    start_time = time.time()
    
    req_text = state["central_init"]
    report = analyze_security(req_text)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Security", elapsed_seconds=round(elapsed, 4))
        
    return {"security_report": report}

def node_evaluator(state: AgentState):
    """Nodo evaluador: Revisa calidad y seguridad."""
    logger.info("▶ Iniciando Agente Evaluador...")
    log_graph_event("node_start", "Evaluator")
    start_time = time.time()
    
    eval_result = evaluate_reports(state["quality_report"], state["security_report"])
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Evaluator", elapsed_seconds=round(elapsed, 4))
        
    return {"evaluation": eval_result}

def node_central_final(state: AgentState):
    """Nodo final: Consolida todo."""
    logger.info("▶ Iniciando Agente Central (Final)...")
    log_graph_event("node_start", "Central_Final")
    start_time = time.time()
    
    final_report = synthesize_final_report(
        project_name=state["project_name"],
        central_init=state["central_init"],
        quality_report=state["quality_report"],
        security_report=state["security_report"],
        evaluation=state["evaluation"]
    )
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Final) completado en {elapsed:.2f} segundos.")
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
    
    # Ejecución paralela
    workflow.add_edge("Central_Init", "Quality")
    workflow.add_edge("Central_Init", "Security")
    
    workflow.add_edge("Quality", "Evaluator")
    workflow.add_edge("Security", "Evaluator")
    
    workflow.add_edge("Evaluator", "Central_Final")
    workflow.add_edge("Central_Final", END)
    
    app = workflow.compile()
    return app
