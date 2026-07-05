import docx
from docx import Document
import io

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
    
    # Guardar en memoria (BytesIO)
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
