import json
import os
import tempfile
from typing import Dict, Any
from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_mapper import map_issue_to_json
from core.graph import build_graph
from core.utils import generate_evaluation_report_pdf, generate_formal_docx
import logging

logger = logging.getLogger(__name__)

def process_issue_workflow(issue_iid: int, project_name: str) -> Dict[str, Any]:
    """
    Orquesta el flujo entre GitLab y el sistema multiagente.
    """
    adapter = GitLabAdapter()
    
    logger.info(f"Obteniendo issue {issue_iid} desde GitLab...")
    issue = adapter.get_issue(issue_iid)
    
    logger.info(f"Mapeando issue a JSON...")
    issue_data = map_issue_to_json(issue)
    
    logger.info(f"Iniciando ejecución del grafo multiagente para el issue {issue_iid}...")
    graph = build_graph()
    initial_state = {
        "project_name": project_name,
        "issue_data": issue_data,
        "central_init": None,
        "quality_report": None,
        "security_report": None,
        "evaluation": None,
        "final_report": None
    }
    
    # Ejecutar grafo
    final_state = {}
    for output in graph.stream(initial_state):
        for key, value in output.items():
            final_state.update(value)
            
    # Extraer resultados
    try:
        quality_json = json.loads(final_state.get("quality_report", "{}"))
    except json.JSONDecodeError:
        quality_json = {}
        
    try:
        security_json = json.loads(final_state.get("security_report", "{}"))
    except json.JSONDecodeError:
        security_json = {}
        
    try:
        eval_json = json.loads(final_state.get("evaluation", "{}"))
    except json.JSONDecodeError:
        eval_json = {}
        
    try:
        cf_json = json.loads(final_state.get("final_report", "{}"))
    except json.JSONDecodeError:
        cf_json = {"documento_formal_md": final_state.get("final_report", "")}
        
    logger.info("Generando documentos PDF y DOCX...")
    pdf_io = generate_evaluation_report_pdf(project_name, quality_json, security_json, eval_json)
    docx_io = generate_formal_docx(project_name, issue_iid, security_json, cf_json)
    
    # Guardar en temporales para subir
    pdf_path = ""
    docx_path = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_io.getvalue())
        pdf_path = tmp_pdf.name
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
        tmp_docx.write(docx_io.getvalue())
        docx_path = tmp_docx.name
        
    logger.info("Subiendo documentos a GitLab...")
    try:
        pdf_attachment = adapter.upload_attachment(pdf_path)
        docx_attachment = adapter.upload_attachment(docx_path)
        
        # Crear comentario
        veredicto = eval_json.get("veredicto", "Desconocido")
        ind_cal = quality_json.get("indice", 0.0)
        ind_seg = security_json.get("indice", 0.0)
        
        comment_body = f"""### Análisis Multiagente Completado 🤖
        
**Resultado Calidad (ISO 25023):** {ind_cal}
**Resultado Seguridad (ISO 27034):** {ind_seg}
**Estado (Veredicto):** {veredicto}

Documentación generada adjunta:
- [Reporte de Evaluación PDF]({pdf_attachment['url']})
- [Documento Formal DOCX]({docx_attachment['url']})
"""
        adapter.add_comment(issue_iid, comment_body)
        
        # Actualizar etiquetas
        new_labels = list(set(issue.labels + ["Analizado", f"Calidad:{ind_cal}", f"Seguridad:{ind_seg}", f"Veredicto:{veredicto}"]))
        adapter.update_labels(issue_iid, new_labels)
        
        logger.info(f"Flujo completado para issue {issue_iid}.")
    finally:
        # Limpiar temporales
        if os.path.exists(pdf_path): os.remove(pdf_path)
        if os.path.exists(docx_path): os.remove(docx_path)
        
    return {
        "issue_data": issue_data,
        "quality_json": quality_json,
        "security_json": security_json,
        "eval_json": eval_json,
        "final_json": cf_json
    }
