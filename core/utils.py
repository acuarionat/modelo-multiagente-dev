from docx import Document
import io
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import datetime
import json
import unicodedata

def clean_text_for_pdf(text: str) -> str:
    """Limpia el texto para evitar problemas con la fuente base de FPDF."""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return text.replace('\r', '')

def extract_percentage(val) -> str:
    if isinstance(val, (int, float)):
        return f"{round(val * 100)} %"
    return str(val)


def build_traceability_rows(batch_results: list) -> list:
    rows = []
    for result in batch_results:
        if result.get("status") != "ok":
            continue
        central = result["central"]
        history = f"{central['historia_id']} — {central['titulo']}"
        for requirement in central["requerimientos"]:
            rows.append({
                "id": requirement["id"],
                "historia": history,
                "requerimiento_formal": requirement.get("descripcion", ""),
                "tipo": requirement["tipo"],
                "justificacion": requirement.get("justificacion", ""),
                "prioridad": requirement.get("prioridad", ""),
                "seguimiento": "Sugerido",
            })
    if not rows:
        raise ValueError("No fue posible construir la matriz porque el Agente Central no devolvió requerimientos formalizados.")
    return rows


def calculate_batch_summary(batch_results: list) -> dict:
    valid = [x for x in batch_results if x.get("status") == "ok"]
    quality = [x["quality"]["indice"] for x in valid]
    security = [x["security"]["indice"] for x in valid]
    verdicts = {}
    for item in valid:
        verdict = item["evaluation"]["veredicto"]
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    return {
        "procesadas": len(valid),
        "errores": len(batch_results) - len(valid),
        "veredictos": verdicts,
        "calidad_promedio": sum(quality) / len(quality) if quality else None,
        "seguridad_promedio": sum(security) / len(security) if security else None,
        "requerimientos": sum(len(x["central"]["requerimientos"]) for x in valid),
    }


def generate_batch_report_pdf(project_name: str, milestone: str, batch_results: list) -> io.BytesIO:
    valid = [x for x in batch_results if x.get("status") == "ok"]
    if not valid:
        raise ValueError("No existen historias completas para generar el PDF.")
    summary = calculate_batch_summary(batch_results)
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    kwargs = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    def heading(text, size=14):
        pdf.set_font("Helvetica", style="B", size=size)
        pdf.multi_cell(0, 7, clean_text_for_pdf(text), **kwargs)
    def line(text):
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, clean_text_for_pdf(text), **kwargs)
    heading("Reporte Ejecutivo Consolidado", 16)
    line(f"Proyecto: {project_name}")
    line(f"Milestone: {milestone}")
    line(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    pdf.ln(4)
    heading("Resumen global", 13)
    line(f"Historias procesadas: {summary['procesadas']} | Con error: {summary['errores']}")
    line(f"Calidad promedio: {extract_percentage(summary['calidad_promedio'])}")
    line(f"Seguridad promedio: {extract_percentage(summary['seguridad_promedio'])}")
    line(f"Requerimientos sugeridos: {summary['requerimientos']}")
    for result in valid:
        c, q, s, e = result["central"], result["quality"], result["security"], result["evaluation"]
        pdf.add_page()
        heading(f"{c['historia_id']} — {c['titulo']}", 13)
        line(f"Veredicto: {e['veredicto']} | Calidad: {extract_percentage(q['indice'])} | Seguridad: {extract_percentage(s['indice'])} | LoT: {s.get('lot_recomendado', 'No informado')}")
        line(f"Actor: {c.get('actor', '')}")
        line(f"Objetivo: {c.get('objetivo', '')}")
        heading("Métricas de calidad", 11)
        for name, metric in q.get("metricas", {}).items():
            line(f"{name}: {extract_percentage(metric.get('valor'))}. {metric.get('justificacion', '')}")
        heading("Métricas de seguridad", 11)
        for name, metric in s.get("metricas", {}).items():
            line(f"{name}: {extract_percentage(metric.get('valor'))}. {metric.get('justificacion', '')}")
        heading("Riesgos y recomendaciones", 11)
        for text_value in e.get("riesgos_criticos", []) + e.get("correcciones_obligatorias", []):
            line(f"- {text_value}")
        heading("Requerimientos sugeridos", 11)
        for requirement in c["requerimientos"]:
            line(f"{requirement['id']} — {requirement.get('nombre', '')}: {requirement.get('descripcion', '')}")
    return io.BytesIO(pdf.output(dest="S"))


def generate_batch_formal_docx(project_name: str, milestone: str, batch_results: list) -> io.BytesIO:
    valid = [x for x in batch_results if x.get("status") == "ok"]
    if not valid:
        raise ValueError("No existen historias completas para generar el DOCX.")
    rows = build_traceability_rows(valid)
    doc = Document()
    doc.add_heading("Documento Formal Consolidado de Requerimientos", 0)
    doc.add_paragraph(f"Proyecto: {project_name}")
    doc.add_paragraph(f"Milestone: {milestone}")
    doc.add_paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    doc.add_paragraph("Versión: 1.0")
    doc.add_paragraph(f"Historias analizadas: {len(valid)}")
    doc.add_page_break()
    doc.add_heading("1. Introducción", 1)
    doc.add_paragraph("Este documento consolida los requerimientos formalizados del lote de Historias de Usuario analizado mediante el sistema multiagente.")
    doc.add_heading("2. Alcance", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective: doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading("3. Actores identificados", 1)
    for actor in dict.fromkeys(x["central"].get("actor", "") for x in valid):
        if actor: doc.add_paragraph(actor, style="List Bullet")
    doc.add_heading("4. Objetivos identificados", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective: doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading("5. Requerimientos formales consolidados", 1)
    for result in valid:
        origin = f"{result['central']['historia_id']} — {result['central']['titulo']}"
        for requirement in result["central"]["requerimientos"]:
            doc.add_heading(f"{requirement['id']} — {requirement.get('nombre', '')}", 3)
            doc.add_paragraph(requirement.get("descripcion", ""))
            doc.add_paragraph(f"Tipo: {requirement['tipo']}")
            doc.add_paragraph(f"Prioridad: {requirement.get('prioridad', '')}")
            doc.add_paragraph(f"Origen: {origin}")
            doc.add_paragraph(f"Justificación: {requirement.get('justificacion', '')}")
    doc.add_heading("6. Restricciones consolidadas", 1)
    restrictions = dict.fromkeys(r for x in valid for r in x["central"].get("restricciones", []))
    for restriction in restrictions: doc.add_paragraph(restriction, style="List Bullet")
    doc.add_heading("7. Recomendaciones generales", 1)
    recommendations = dict.fromkeys(r for x in valid for r in (x["quality"].get("recomendaciones", []) + x["security"].get("recomendaciones", []) + x["evaluation"].get("correcciones_obligatorias", [])))
    for recommendation in recommendations: doc.add_paragraph(recommendation, style="List Bullet")
    doc.add_heading("8. Matriz de trazabilidad", 1)
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    headers = ["ID", "Historia", "Requerimiento", "Tipo", "Justificación", "Prioridad", "Seguimiento"]
    for cell, value in zip(table.rows[0].cells, headers): cell.text = value
    for row in rows:
        for cell, key in zip(table.add_row().cells, ["id", "historia", "requerimiento_formal", "tipo", "justificacion", "prioridad", "seguimiento"]):
            cell.text = str(row[key])
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output

def generate_formal_docx(project_name: str, issue_iid: int, central_init: dict, quality_json: dict, security_json: dict, eval_json: dict, parsed_cf: dict) -> io.BytesIO:
    """Genera el Documento Formal de Requerimientos en Word."""
    doc = Document()
    req_id = f"REQ-{datetime.now().year}-{issue_iid:03d}"
    
    doc.add_heading('Documento Formal de Requerimientos', 0)
    doc.add_paragraph(f'ID del Documento: {req_id}')
    doc.add_paragraph(f'Proyecto: {project_name}')
    doc.add_paragraph(f'Fecha: {datetime.now().strftime("%Y-%m-%d")}')
    doc.add_page_break()
    
    doc.add_heading('1. Introducción', level=1)
    intro = f"El presente documento formaliza los requerimientos extraídos para el proyecto '{project_name}' correspondientes a la Historia de Usuario #{issue_iid}."
    doc.add_paragraph(intro)
    
    doc.add_heading('2. Alcance', level=1)
    actores = central_init.get("actores", [])
    if actores:
        doc.add_paragraph("Actores identificados:")
        for actor in actores:
            doc.add_paragraph(f"- {actor}")
            
    doc.add_heading('3. Objetivos', level=1)
    objetivos = central_init.get("objetivos_identificados", [])
    if objetivos:
        for obj in objetivos:
            doc.add_paragraph(f"- {obj}")
    else:
        doc.add_paragraph("No se identificaron objetivos específicos.")
        
    doc.add_heading('4. Requerimientos Funcionales', level=1)
    for req in central_init.get("requerimientos_funcionales", []):
        doc.add_paragraph(f"ID: {req.get('id', 'N/A')} - {req.get('nombre', 'N/A')}", style='Heading 3')
        doc.add_paragraph(f"Descripción: {req.get('descripcion_formal', 'N/A')}")
        doc.add_paragraph(f"Actor: {req.get('actor_principal', 'N/A')}")
        doc.add_paragraph(f"Prioridad: {req.get('prioridad', 'N/A')}")
        criterios = req.get("criterios_aceptacion", [])
        if criterios:
            doc.add_paragraph("Criterios de Aceptación:")
            for c in criterios:
                doc.add_paragraph(f"- {c}")
                
    doc.add_heading('5. Requerimientos No Funcionales', level=1)
    for req in central_init.get("requerimientos_no_funcionales", []):
        doc.add_paragraph(f"ID: {req.get('id', 'N/A')} - {req.get('nombre', 'N/A')}", style='Heading 3')
        doc.add_paragraph(f"Descripción: {req.get('descripcion_formal', 'N/A')}")
        
    restricciones = central_init.get("restricciones", [])
    if restricciones:
        doc.add_heading('6. Restricciones', level=1)
        for r in restricciones:
            doc.add_paragraph(f"- {r}")
            
    doc.add_heading('7. Conclusiones y Recomendaciones', level=1)
    doc.add_paragraph(parsed_cf.get("conclusiones_finales", ""))
    for rec in parsed_cf.get("recomendaciones_globales", []):
        doc.add_paragraph(f"- {rec}")
            
    doc.add_page_break()
    doc.add_heading('Matriz de Trazabilidad', level=1)
    
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    headers = ['Historia de Usuario', 'Requerimiento Formal', 'Tipo', 'Justificación']
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        
    reqs_func = central_init.get("requerimientos_funcionales", [])
    reqs_no_func = central_init.get("requerimientos_no_funcionales", [])
    requerimientos = reqs_func + reqs_no_func
    
    for r in requerimientos:
        row_cells = table.add_row().cells
        origen = str(r.get("texto_original_asociado", f"HU #{issue_iid}"))
        r_nombre = f"{r.get('id', 'N/A')} - {r.get('nombre', r.get('descripcion_formal', 'N/A'))}"
        r_tipo = "RF" if "RF-" in str(r.get("id", "")) else "RNF"
        r_justif = str(r.get("justificacion", "Generado a partir de la historia."))
        
        row_cells[0].text = origen
        row_cells[1].text = r_nombre
        row_cells[2].text = r_tipo
        row_cells[3].text = r_justif
            
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io

def generate_evaluation_report_pdf(project_name: str, issue_iid: int, quality_json: dict, security_json: dict, eval_json: dict, central_init: dict, parsed_cf: dict) -> io.BytesIO:
    """Genera el Reporte Ejecutivo en PDF estructurado según el plan simplificado."""
    pdf = FPDF()
    pdf.set_margins(left=25, top=25, right=25)
    pdf.add_page()
    mc_kwargs = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    line_h = 6
    
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.multi_cell(0, line_h, txt=f"Reporte Ejecutivo de Requerimientos", align='C', **mc_kwargs)
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt=f"Proyecto: {clean_text_for_pdf(project_name)} | HU #{issue_iid}", align='C', **mc_kwargs)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, line_h, txt=f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", align='C', **mc_kwargs)
    pdf.ln(5)
    
    # Resumen Ejecutivo
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="1. Resumen Ejecutivo", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, line_h, txt=f"Veredicto: {clean_text_for_pdf(eval_json.get('veredicto', 'N/A'))}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=clean_text_for_pdf(parsed_cf.get('resumen_ejecutivo', '')), **mc_kwargs)
    pdf.ln(5)
    
    # Historia Analizada
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="2. Historia Analizada", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    objetivos = central_init.get("objetivos_identificados", [])
    if objetivos:
        for obj in objetivos:
            pdf.multi_cell(0, line_h, txt=f"- {clean_text_for_pdf(obj)}", **mc_kwargs)
    pdf.ln(5)
    
    # Resultados Calidad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="3. Resultados Calidad", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    ind_cal = quality_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"Índice Global: {extract_percentage(ind_cal)}", **mc_kwargs)
    just_cal = quality_json.get("justificaciones", {})
    for k, v in just_cal.items():
        if isinstance(v, dict):
            pdf.multi_cell(0, line_h, txt=f"- {k}: {v.get('resultado', 'N/A')} | {clean_text_for_pdf(v.get('justificacion', ''))}", **mc_kwargs)
            if 'razon_valor' in v:
                pdf.multi_cell(0, line_h, txt=f"  Razón: {clean_text_for_pdf(v['razon_valor'])}", **mc_kwargs)
    pdf.ln(5)
    
    # Resultados Seguridad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="4. Resultados Seguridad", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    ind_seg = security_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"Índice Global: {extract_percentage(ind_seg)}", **mc_kwargs)
    just_seg = security_json.get("justificaciones", {})
    for k, v in just_seg.items():
        if isinstance(v, dict):
            pdf.multi_cell(0, line_h, txt=f"- {k}: {v.get('resultado', 'N/A')} | {clean_text_for_pdf(v.get('justificacion', ''))}", **mc_kwargs)
            if 'razon_valor' in v:
                pdf.multi_cell(0, line_h, txt=f"  Razón: {clean_text_for_pdf(v['razon_valor'])}", **mc_kwargs)
    pdf.ln(5)
    
    # Riesgos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="5. Riesgos Identificados", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    riesgos = eval_json.get("riesgos_criticos", [])
    if riesgos:
        for r in riesgos:
            pdf.multi_cell(0, line_h, txt=f"- {clean_text_for_pdf(r)}", **mc_kwargs)
    else:
        pdf.multi_cell(0, line_h, txt="Ninguno crítico.", **mc_kwargs)
    pdf.ln(5)
    
    # Requerimientos Sugeridos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="6. Requerimientos Sugeridos", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    for req in central_init.get("requerimientos_funcionales", []) + central_init.get("requerimientos_no_funcionales", []):
        pdf.multi_cell(0, line_h, txt=f"- {req.get('id', 'N/A')} : {clean_text_for_pdf(req.get('nombre', ''))}", **mc_kwargs)
    pdf.ln(5)
    
    # Conclusión
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="7. Conclusión", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, line_h, txt=clean_text_for_pdf(parsed_cf.get("conclusiones_finales", eval_json.get('conclusion', ''))), **mc_kwargs)
    pdf.ln(5)
    
    # Próximos pasos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="8. Próximos Pasos", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    correcciones = eval_json.get("correcciones_obligatorias", [])
    if correcciones:
        for c in correcciones:
            pdf.multi_cell(0, line_h, txt=f"- {clean_text_for_pdf(c)}", **mc_kwargs)
    else:
        pdf.multi_cell(0, line_h, txt="- Avanzar a fase de diseño.", **mc_kwargs)
            
    pdf_bytes = pdf.output(dest='S')
    return io.BytesIO(pdf_bytes)

def generate_traceability_matrix_md(central_init_json: dict) -> str:
    """Genera la Matriz de Trazabilidad en Markdown simplificada."""
    md = "### Matriz de Trazabilidad Automática\n\n"
    md += "| ID | Historia de Usuario | Requerimiento Formal | Tipo | Justificación | Prioridad | Seguimiento |\n"
    md += "|----|---------------------|----------------------|------|---------------|-----------|-------------|\n"
    
    reqs_func = central_init_json.get("requerimientos_funcionales", [])
    reqs_no_func = central_init_json.get("requerimientos_no_funcionales", [])
    requerimientos = reqs_func + reqs_no_func
    
    if not requerimientos:
        md += "| N/A | N/A | No se encontraron requerimientos | N/A | N/A | N/A | N/A |\n"
        return md
        
    for req in requerimientos:
        while isinstance(req, list) and len(req) > 0:
            req = req[0]
        if not isinstance(req, dict):
            continue
            
        req_id = req.get("id", "N/A")
        # El origen de la HU ya no viene del LLM para cada req en el nuevo prompt (ya que todo el issue es la fuente)
        # Pondremos el título del proyecto o simplemente referiremos a la HU actual.
        hu = central_init_json.get("proyecto", "HU")
        nombre = req.get("nombre", "N/A").replace("|", "-").replace("\n", " ")
        tipo = "RF" if "RF-" in str(req_id) else "RNF"
        justif = req.get("justificacion", "Derivado de la HU.").replace("|", "-").replace("\n", " ")
        prioridad = req.get("prioridad", "Media")
        
        md += f"| {req_id} | {hu} | {nombre} | {tipo} | {justif} | {prioridad} | Pendiente |\n"
        
    return md

def calculate_quality_metrics(q_json: dict) -> dict:
    """Calcula las métricas de calidad FCp-1-G y FAp-1-G en base a los datos extraídos por el agente."""
    funciones_esperadas = q_json.get("funciones_esperadas", 1)
    if funciones_esperadas <= 0:
        funciones_esperadas = 1
    funciones_ausentes = q_json.get("funciones_ausentes_ambiguas", 0)
    
    fcp_1_g = 1.0 - (funciones_ausentes / funciones_esperadas)
    fcp_1_g = max(0.0, min(1.0, fcp_1_g))
    
    funciones = q_json.get("funciones", [])
    total_funciones = len(funciones)
    contribuyen = 0
    if total_funciones == 0:
        fap_1_g = 1.0
    else:
        contribuyen = sum(1 for f in funciones if f.get("contribuye_objetivo", False))
        fap_1_g = contribuyen / total_funciones
        
    indice = (fcp_1_g + fap_1_g) / 2.0
    
    q_json["indice"] = indice
    q_json["meta_cumplida"] = indice >= 0.95
    q_json["justificaciones"] = {
        "FCp-1-G": {
            "resultado": f"{int(fcp_1_g * 100)} %",
            "justificacion": f"{funciones_ausentes} funciones ausentes/ambiguas de {funciones_esperadas} esperadas."
        },
        "FAp-1-G": {
            "resultado": f"{int(fap_1_g * 100)} %",
            "justificacion": f"{contribuyen} de {total_funciones} funciones evaluadas contribuyen al objetivo."
        }
    }
    return q_json

def calculate_security_metrics(s_json: dict) -> dict:
    """Calcula las métricas de seguridad en base a los datos extraídos por el agente."""
    requerimientos_evaluados = s_json.get("total_requerimientos_evaluados", 1)
    if requerimientos_evaluados <= 0:
        requerimientos_evaluados = 1
        
    con_control = s_json.get("requerimientos_con_control_explicito", 0)
    con_lot = s_json.get("requerimientos_con_lot_asignado", 0)
    
    cobertura_controles = con_control / requerimientos_evaluados
    cobertura_controles = max(0.0, min(1.0, cobertura_controles))
    
    cobertura_lot = con_lot / requerimientos_evaluados
    cobertura_lot = max(0.0, min(1.0, cobertura_lot))
    
    indice = (cobertura_controles + cobertura_lot) / 2.0
    
    s_json["indice"] = indice
    s_json["meta_cumplida"] = indice >= 0.85
    s_json["justificaciones"] = {
        "controles_seguridad": {
            "resultado": f"{int(cobertura_controles * 100)} %",
            "justificacion": f"{con_control} de {requerimientos_evaluados} con controles explícitos."
        },
        "lot_asignado": {
            "resultado": f"{int(cobertura_lot * 100)} %",
            "justificacion": f"{con_lot} de {requerimientos_evaluados} con LoT asignado."
        }
    }
    return s_json
