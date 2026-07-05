from langgraph.graph import StateGraph, END
from core.state import AgentState
from agents.central_agent import process_ticket, synthesize_final_report
from agents.quality_agent import analyze_quality
from agents.security_agent import analyze_security
from agents.evaluator_agent import evaluate_reports
from database.db_manager import log_agent_result, update_execution_final

# 1. Definición de Nodos

def node_central_init(state: AgentState):
    """Nodo inicial: El orquestador arranca el flujo."""
    project_name = state["project_name"]
    req_text = state["requirements_text"]
    response = process_ticket(project_name, req_text)
    
    if state["execution_id"]:
        log_agent_result(state["execution_id"], "Agente Central (Init)", response)
        
    return {"central_init": response}

def node_quality(state: AgentState):
    """Nodo paralelo: Calidad."""
    req_text = state["requirements_text"]
    report = analyze_quality(req_text)
    
    if state["execution_id"]:
        log_agent_result(state["execution_id"], "Agente de Calidad", report)
        
    return {"quality_report": report}

def node_security(state: AgentState):
    """Nodo paralelo: Seguridad."""
    req_text = state["requirements_text"]
    report = analyze_security(req_text)
    
    if state["execution_id"]:
        log_agent_result(state["execution_id"], "Agente de Seguridad", report)
        
    return {"security_report": report}

def node_evaluator(state: AgentState):
    """Nodo evaluador: Revisa calidad y seguridad."""
    eval_result = evaluate_reports(state["quality_report"], state["security_report"])
    
    if state["execution_id"]:
        log_agent_result(state["execution_id"], "Agente Evaluador", eval_result)
        
    return {"evaluation": eval_result}

def node_central_final(state: AgentState):
    """Nodo final: Consolida todo."""
    final_report = synthesize_final_report(state["evaluation"], state["project_name"])
    
    if state["execution_id"]:
        log_agent_result(state["execution_id"], "Agente Central (Final)", final_report)
        update_execution_final(
            state["execution_id"], 
            status="COMPLETED", 
            final_decision="Ver reporte", 
            final_report=final_report
        )
        
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
    
    workflow.add_edge("Central_Init", "Quality")
    workflow.add_edge("Central_Init", "Security")
    
    workflow.add_edge("Quality", "Evaluator")
    workflow.add_edge("Security", "Evaluator")
    
    workflow.add_edge("Evaluator", "Central_Final")
    workflow.add_edge("Central_Final", END)
    
    app = workflow.compile()
    return app
