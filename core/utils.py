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
    # Normaliza y elimina caracteres unicode extraños que puedan romper FPDF
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    # También podemos reemplazar saltos de línea extraños
    return text.replace('\r', '')

def generate_word_template() -> io.BytesIO:
    """
    Genera un documento Word con la plantilla mejorada de requerimientos.
    """
    doc = Document()
    doc.add_heading('Plantilla de Requerimientos de Proyecto', 0)
    
    doc.add_paragraph('Nombre del Proyecto: [Nombre]')
    doc.add_paragraph('Fecha: [Fecha]')
    doc.add_paragraph('Solicitante: [Nombre]')
    
    doc.add_heading('1. Descripción General', level=1)
    doc.add_paragraph('[Descripción clara y breve del proyecto]')
    
    doc.add_heading('2. Objetivos Principales', level=1)
    doc.add_paragraph('[Objetivo 1]\n[Objetivo 2]\n[Objetivo 3]')
    
    doc.add_heading('3. Funcionalidades Requeridas', level=1)
    doc.add_paragraph('[Funcionalidad 1] - Prioridad: Alta / Media / Baja\n[Funcionalidad 2] - Prioridad: ...\n[Funcionalidad 3] - Prioridad: ...')
    
    doc.add_heading('4. Datos Sensibles', level=1)
    doc.add_paragraph('¿Maneja datos sensibles? (Sí/No)\nTipos de datos: [ej. datos personales, calificaciones, financiera, etc.]\nNivel de sensibilidad: Bajo / Medio / Alto')
    
    doc.add_heading('5. Requisitos de Seguridad Específicos', level=1)
    doc.add_paragraph('Autenticación: [Sí/No + tipo: usuario/contraseña, 2FA, etc.]\nAutorización (roles): [Lista de roles y permisos]\nAuditoría: [¿Se necesita registro de acciones? Sí/No]\nProtección de datos: [Cifrado, anonimato, etc.]\nOtros requisitos de seguridad: [detallar]')
    
    doc.add_heading('6. Usuarios y Accesos', level=1)
    doc.add_paragraph('Roles de usuarios: [Administrador, Profesor, Estudiante, etc.]\nPermisos por rol: [breve descripción]')
    
    doc.add_heading('7. Observaciones Adicionales o Restricciones', level=1)
    doc.add_paragraph('[Espacio libre para cualquier detalle importante]')
    
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return doc_io

def extract_text_from_docx(file_bytes) -> str:
    """
    Extrae todo el texto de un archivo Word.
    """
    doc = Document(file_bytes)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text)
    return '\n'.join(full_text)


def generate_evaluation_report_pdf(project_name: str, quality_json: dict, security_json: dict, eval_json: dict) -> io.BytesIO:
    """
    Genera el Reporte de Evaluación en formato PDF con formato Arial 12, espaciado 1.15 y márgenes de 2.5 cm.
    """
    pdf = FPDF()
    # Margenes de 2.5 cm = 25 mm
    pdf.set_margins(left=25, top=25, right=25)
    pdf.add_page()
    
    mc_kwargs = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    line_h = 6 # Aproximado para espaciado 1.15 en fuente 12
    
    # Portada / Título
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt=f"Reporte de Evaluacion: {clean_text_for_pdf(project_name)}", align='C', **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, line_h, txt=f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", align='C', **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"Veredicto: {clean_text_for_pdf(eval_json.get('Veredicto', 'N/A'))}", align='C', **mc_kwargs)
    pdf.ln(10)
    
    # Decisión Final y Conclusión
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Decision Final y Conclusion", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, line_h, txt=clean_text_for_pdf(eval_json.get('Conclusion', 'N/A')), **mc_kwargs)
    pdf.ln(5)
    
    # Métricas de Calidad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Metricas de Calidad (ISO 25023)", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    fcp = quality_json.get("FCp-1-G", 0.0)
    fap = quality_json.get("FAp-1-G", 0.0)
    ind_cal = quality_json.get("Indice_Calidad", 0.0)
    pdf.multi_cell(0, line_h, txt=f"- Indice de Calidad: {ind_cal}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- FCp-1-G (Cobertura Funcional) [X = 1 - (A/B)]: {fcp}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"  Justificacion: {clean_text_for_pdf(quality_json.get('Justificacion_FCp', 'N/A'))}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- FAp-1-G (Adecuacion Funcional): {fap}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"  Justificacion: {clean_text_for_pdf(quality_json.get('Justificacion_FAp', 'N/A'))}", **mc_kwargs)
    pdf.ln(5)
    
    # Métricas de Seguridad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Metricas de Seguridad (ISO 27034)", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    lot = security_json.get("LoT_Asignado", "N/A")
    ind_seg = security_json.get("Indice_Seguridad", 0.0)
    pdf.multi_cell(0, line_h, txt=f"- Indice de Seguridad: {ind_seg}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- Nivel de Confianza (LoT) Recomendado: {lot}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- ASC-REQ-01 Cumplido: {security_json.get('ASC-REQ-01_Cumplido', False)}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- ASC-REQ-02 Cumplido: {security_json.get('ASC-REQ-02_Cumplido', False)}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"  Justificacion y Observaciones: {clean_text_for_pdf(security_json.get('Observaciones', 'N/A'))}", **mc_kwargs)
    pdf.ln(5)
    
    # Recomendaciones y Riesgos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Recomendaciones y Riesgos", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    riesgos = eval_json.get("Riesgos_Criticos", [])
    if riesgos:
        pdf.multi_cell(0, line_h, txt="Riesgos Criticos:", **mc_kwargs)
        for r in riesgos:
            pdf.multi_cell(0, line_h, txt=f"  * {clean_text_for_pdf(r)}", **mc_kwargs)
            
    correcciones = eval_json.get("Correcciones_Inmediatas", [])
    if correcciones:
        pdf.multi_cell(0, line_h, txt="Correcciones Inmediatas:", **mc_kwargs)
        for c in correcciones:
            pdf.multi_cell(0, line_h, txt=f"  * {clean_text_for_pdf(c)}", **mc_kwargs)
            
    pdf_bytes = pdf.output(dest='S')
    return io.BytesIO(pdf_bytes)


def generate_formal_docx(project_name: str, execution_id: int, security_json: dict) -> io.BytesIO:
    """
    Genera el Documento Formal de Requerimientos en Word.
    Solo se llama si se aprueban las métricas.
    """
    doc = Document()
    req_id = f"REQ-{datetime.now().year}-{execution_id:03d}-v1"
    
    # Portada
    doc.add_heading('Documento Formal de Requerimientos', 0)
    doc.add_paragraph(f'ID del Documento: {req_id}')
    doc.add_paragraph(f'Proyecto: {project_name}')
    doc.add_paragraph(f'Fecha: {datetime.now().strftime("%Y-%m-%d")}')
    doc.add_paragraph(f'Versión: 1.0')
    doc.add_paragraph('Aprobado por: Agente Central (Sistema Multiagente)')
    doc.add_page_break()
    
    doc.add_heading('1. Introducción', level=1)
    doc.add_paragraph('Este documento consolida los requerimientos aprobados formalmente tras superar los umbrales de Calidad (ISO 25023) y Seguridad (ISO 27034).')
    
    doc.add_heading('2. Objetivos', level=1)
    doc.add_paragraph('[Detallar los objetivos del sistema]')
    
    doc.add_heading('3. Funcionalidades Detalladas', level=1)
    doc.add_paragraph('[Listado de funcionalidades estructuradas con prioridad, derivadas del texto original]')
    
    doc.add_heading('4. Datos Sensibles y LoT asignado', level=1)
    lot = security_json.get("LoT_Asignado", "N/A")
    doc.add_paragraph(f'Nivel de Confianza Asignado (LoT): Nivel {lot}')
    doc.add_paragraph('[Detallar tipos de datos sensibles procesados]')
    
    doc.add_heading('5. Requisitos de Seguridad', level=1)
    doc.add_paragraph('[Detalle de requisitos de seguridad, autenticación, autorización y auditoría]')
    
    doc.add_heading('6. Matriz de Trazabilidad Inicial', level=1)
    # Ejemplo de tabla simple
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'ID Req'
    hdr_cells[1].text = 'Descripción'
    hdr_cells[2].text = 'Estado'
    
    row_cells = doc.add_table(rows=1, cols=3).rows[0].cells
    row_cells[0].text = f'{req_id}-F01'
    row_cells[1].text = 'Funcionalidad base'
    row_cells[2].text = 'Aprobado'
    
    doc.add_page_break()
    doc.add_heading('7. Aprobación', level=1)
    doc.add_paragraph('____________________________________________________')
    doc.add_paragraph('Firma / Aprobación del Responsable')
    
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return doc_io
