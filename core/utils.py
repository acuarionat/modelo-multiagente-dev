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
    pdf.multi_cell(0, line_h, txt=f"Veredicto: {clean_text_for_pdf(eval_json.get('veredicto', 'N/A'))}", align='C', **mc_kwargs)
    pdf.ln(10)
    
    # Decisión Final y Conclusión
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Decision Final y Conclusion", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, line_h, txt=clean_text_for_pdf(eval_json.get('conclusion', 'N/A')), **mc_kwargs)
    pdf.ln(5)
    
    # Métricas de Calidad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Metricas de Calidad (ISO 25023)", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    ind_cal = quality_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"- Indice de Calidad: {ind_cal}", **mc_kwargs)
    
    just_cal = quality_json.get("justificaciones", {})
    pdf.multi_cell(0, line_h, txt=f"- FCp-1-G (Cobertura Funcional): {clean_text_for_pdf(just_cal.get('FCp-1-G', 'N/A'))}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- FAp-1-G (Adecuacion Funcional): {clean_text_for_pdf(just_cal.get('FAp-1-G', 'N/A'))}", **mc_kwargs)
    
    recom_cal = quality_json.get("recomendaciones", [])
    if recom_cal:
        pdf.multi_cell(0, line_h, txt="  Recomendaciones:", **mc_kwargs)
        for rc in recom_cal:
            pdf.multi_cell(0, line_h, txt=f"   * {clean_text_for_pdf(rc)}", **mc_kwargs)
    pdf.ln(5)
    
    # Métricas de Seguridad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Metricas de Seguridad (ISO 27034)", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    lot = security_json.get("lot_recomendado", "N/A")
    ind_seg = security_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"- Indice de Seguridad: {ind_seg}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- Nivel de Confianza (LoT) Recomendado: {lot}", **mc_kwargs)
    
    just_seg = security_json.get("justificaciones", {})
    pdf.multi_cell(0, line_h, txt=f"- Controles de Seguridad (ASC-REQ-01): {clean_text_for_pdf(just_seg.get('controles_seguridad', 'N/A'))}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=f"- Asignacion de LoT (ASC-REQ-02): {clean_text_for_pdf(just_seg.get('lot_asignado', 'N/A'))}", **mc_kwargs)
    
    recom_seg = security_json.get("recomendaciones", [])
    if recom_seg:
        pdf.multi_cell(0, line_h, txt="  Recomendaciones:", **mc_kwargs)
        for rs in recom_seg:
            pdf.multi_cell(0, line_h, txt=f"   * {clean_text_for_pdf(rs)}", **mc_kwargs)
    pdf.ln(5)
    
    # Riesgos y Correcciones (Evaluador)
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="Riesgos y Correcciones Inmediatas", **mc_kwargs)
    pdf.set_font("Helvetica", size=12)
    riesgos = eval_json.get("riesgos_criticos", [])
    if riesgos:
        pdf.multi_cell(0, line_h, txt="Riesgos Criticos:", **mc_kwargs)
        for r in riesgos:
            pdf.multi_cell(0, line_h, txt=f"  * {clean_text_for_pdf(r)}", **mc_kwargs)
            
    correcciones = eval_json.get("correcciones_inmediatas", [])
    if correcciones:
        pdf.multi_cell(0, line_h, txt="Correcciones Inmediatas:", **mc_kwargs)
        for c in correcciones:
            pdf.multi_cell(0, line_h, txt=f"  * {clean_text_for_pdf(c)}", **mc_kwargs)
            
    pdf_bytes = pdf.output(dest='S')
    return io.BytesIO(pdf_bytes)


def extract_section(text: str, start_marker: str, end_markers: list) -> str:
    """Extrae una sección de texto entre un marcador inicial y uno o varios marcadores finales."""
    start_idx = text.find(start_marker)
    if start_idx == -1: return "No especificado."
    start_idx += len(start_marker)
    
    end_idx = len(text)
    for marker in end_markers:
        idx = text.find(marker, start_idx)
        if idx != -1 and idx < end_idx:
            end_idx = idx
            
    return text[start_idx:end_idx].strip()

def generate_formal_docx(project_name: str, execution_id: int, security_json: dict, parsed_cf: dict) -> io.BytesIO:
    """
    Genera el Documento Formal de Requerimientos en Word usando el markdown generado por el Agente Central.
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
    
    # Contenido lógico generado por el Agente Central Final
    doc_md = parsed_cf.get("documento_formal_md", "Contenido no generado.")
    matriz_md = parsed_cf.get("matriz_trazabilidad_md", "Matriz no generada.")
    
    doc.add_heading('Contenido del Documento Formal', level=1)
    
    # Como python-docx no soporta Markdown nativo, agregamos el texto crudo estructurado.
    # El usuario puede aplicar estilos luego o podemos separarlo por líneas simples.
    for line in doc_md.split('\n'):
        if line.startswith('###'):
            doc.add_heading(line.replace('#', '').strip(), level=3)
        elif line.startswith('##'):
            doc.add_heading(line.replace('#', '').strip(), level=2)
        elif line.startswith('#'):
            doc.add_heading(line.replace('#', '').strip(), level=1)
        elif line.strip():
            doc.add_paragraph(line.strip())
            
    doc.add_page_break()
    doc.add_heading('Matriz de Trazabilidad', level=1)
    for line in matriz_md.split('\n'):
        if line.strip():
            doc.add_paragraph(line.strip())
            
    doc.add_page_break()
    doc.add_heading('Aprobación', level=1)
    doc.add_paragraph('____________________________________________________')
    doc.add_paragraph('Firma / Aprobación del Responsable')
    
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return doc_io
