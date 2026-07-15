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
    calculate_agent_metrics, consolidate_batch, index_results,
    parse_batch_response, reconcile_issue_ids, validate_agent_content,
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


def _parse_with_single_retry(raw_response, agent_name, retry_call):
    try:
        return parse_batch_response(raw_response, agent_name), raw_response
    except ValueError as first_error:
        logger.warning("%s Reintentando una sola vez con mayor presupuesto.", first_error)
        retry_response = retry_call()
        return parse_batch_response(retry_response, f"{agent_name} (reintento)"), retry_response


def _merge_repair(base, repair):
    repaired = index_results(repair)
    base["resultados"] = [
        repaired.get(item.get("issue_iid"), item)
        for item in base.get("resultados", [])
        if isinstance(item, dict)
    ]
    existing = {item.get("issue_iid") for item in base["resultados"]}
    base["resultados"].extend(item for iid, item in repaired.items() if iid not in existing)


def _validate_and_repair(parsed, expected_ids, agent_name, repair_call, expected_titles=None):
    for note in reconcile_issue_ids(parsed, expected_ids, agent_name, expected_titles):
        logger.warning(note)
    calculate_agent_metrics(parsed, agent_name)
    content_errors = validate_agent_content(parsed, agent_name)
    missing = set(expected_ids) - set(index_results(parsed))
    repair_ids = sorted(set(content_errors) | missing)
    if repair_ids:
        logger.warning("%s: reparación selectiva para Issues %s.", agent_name, repair_ids)
        repair = parse_batch_response(repair_call(repair_ids), f"{agent_name} (reparación)")
        repair_titles = None
        if expected_titles:
            repair_titles = {title: iid for title, iid in expected_titles.items() if iid in repair_ids}
        for note in reconcile_issue_ids(repair, repair_ids, f"{agent_name} (reparación)", repair_titles):
            logger.warning(note)
        calculate_agent_metrics(repair, agent_name)
        _merge_repair(parsed, repair)
        calculate_agent_metrics(parsed, agent_name)
        content_errors = validate_agent_content(parsed, agent_name)
    structural_errors = validate_batch_response(parsed, set(expected_ids), agent_name)
    return structural_errors, content_errors


def _merge_content_errors(previous, agent_name, current):
    merged = {int(iid): list(messages) for iid, messages in (previous or {}).items()}
    for iid, messages in current.items():
        merged.setdefault(iid, []).extend(f"{agent_name}: {message}" for message in messages)
    return merged

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
    parsed, response = _parse_with_single_retry(
        response, "Central",
        lambda: process_ticket(project_name, issues_json_str, sprint_context, num_predict_override=2800),
    )
    expected_ids = [int(x["id"]) for x in issues_data]
    titles = {x["titulo"]: int(x["id"]) for x in issues_data}
    def repair_call(repair_ids):
        subset = [item for item in issues_data if int(item["id"]) in repair_ids]
        return process_ticket(project_name, json.dumps(subset, ensure_ascii=False), sprint_context)
    errors, content_errors = _validate_and_repair(parsed, expected_ids, "Central", repair_call, titles)
    response = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Central (Init) completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Central_Init", elapsed_seconds=round(elapsed, 4))
        
    return {
        "central_init": response,
        "validation_errors": errors,
        "content_validation_errors": _merge_content_errors({}, "Central", content_errors),
    }

def node_quality(state: AgentState):
    """Nodo de Calidad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Calidad (Lote)...")
    log_graph_event("node_start", "Quality")
    start_time = time.time()
    
    req_text = state["central_init"]
    report_str = analyze_quality(req_text)
    parsed, report_str = _parse_with_single_retry(
        report_str, "Calidad",
        lambda: analyze_quality(req_text, num_predict_override=2400),
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    central = parse_batch_response(req_text, "Central")
    def repair_call(repair_ids):
        subset = [item for item in central["resultados"] if item.get("issue_iid") in repair_ids]
        return analyze_quality(json.dumps({"agente": "central", "resultados": subset}, ensure_ascii=False))
    errors, content_errors = _validate_and_repair(parsed, expected_ids, "Calidad", repair_call)
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Calidad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Quality", elapsed_seconds=round(elapsed, 4))
        
    return {
        "quality_report": final_report,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _merge_content_errors(state.get("content_validation_errors"), "Calidad", content_errors),
    }

def node_security(state: AgentState):
    """Nodo de Seguridad: Procesa el lote estructurado."""
    logger.info("▶ Iniciando Agente de Seguridad (Lote)...")
    log_graph_event("node_start", "Security")
    start_time = time.time()
    
    req_text = state["central_init"]
    report_str = analyze_security(req_text)
    parsed, report_str = _parse_with_single_retry(
        report_str, "Seguridad",
        lambda: analyze_security(req_text, num_predict_override=2800),
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    central = parse_batch_response(req_text, "Central")
    def repair_call(repair_ids):
        subset = [item for item in central["resultados"] if item.get("issue_iid") in repair_ids]
        return analyze_security(json.dumps({"agente": "central", "resultados": subset}, ensure_ascii=False))
    errors, content_errors = _validate_and_repair(parsed, expected_ids, "Seguridad", repair_call)
    final_report = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente de Seguridad completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Security", elapsed_seconds=round(elapsed, 4))
        
    return {
        "security_report": final_report,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _merge_content_errors(state.get("content_validation_errors"), "Seguridad", content_errors),
    }

def node_evaluator(state: AgentState):
    """Nodo evaluador: Revisa calidad y seguridad para el lote."""
    logger.info("▶ Iniciando Agente Evaluador (Lote)...")
    log_graph_event("node_start", "Evaluator")
    start_time = time.time()
    
    eval_result = evaluate_reports(state["quality_report"], state["security_report"])
    parsed, eval_result = _parse_with_single_retry(
        eval_result, "Evaluador",
        lambda: evaluate_reports(state["quality_report"], state["security_report"], num_predict_override=1400),
    )
    expected_ids = [int(x["id"]) for x in state["issues_data"]]
    quality = parse_batch_response(state["quality_report"], "Calidad")
    security = parse_batch_response(state["security_report"], "Seguridad")
    def repair_call(repair_ids):
        q_subset = [item for item in quality["resultados"] if item.get("issue_iid") in repair_ids]
        s_subset = [item for item in security["resultados"] if item.get("issue_iid") in repair_ids]
        return evaluate_reports(
            json.dumps({"agente": "calidad", "resultados": q_subset}, ensure_ascii=False),
            json.dumps({"agente": "seguridad", "resultados": s_subset}, ensure_ascii=False),
        )
    errors, content_errors = _validate_and_repair(parsed, expected_ids, "Evaluador", repair_call)
    eval_result = json.dumps(parsed, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✔ Agente Evaluador completado en {elapsed:.2f} segundos.")
    log_graph_event("node_end", "Evaluator", elapsed_seconds=round(elapsed, 4))
        
    return {
        "evaluation": eval_result,
        "validation_errors": state.get("validation_errors", []) + errors,
        "content_validation_errors": _merge_content_errors(state.get("content_validation_errors"), "Evaluador", content_errors),
    }

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
        state.get("content_validation_errors", {}),
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
