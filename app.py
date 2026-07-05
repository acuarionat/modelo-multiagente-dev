import streamlit as st
import os
import sys
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import init_db, log_execution
from core.graph import build_graph
from core.utils import generate_word_template, extract_text_from_docx

st.set_page_config(page_title="Recepción de Requerimientos", page_icon="📝", layout="wide")

st.title("📝 Etapa 1: Recepción de Requerimientos")
st.markdown("Evalúa la viabilidad de los requerimientos de un proyecto (Calidad ISO 25023 y Seguridad ISO 27034).")

if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

project_name = st.text_input("Nombre del Proyecto:", placeholder="Ej: Sistema de Gestión de Inventarios")

tab1, tab2 = st.tabs(["✍️ Llenar en Interfaz (Recomendado)", "📄 Subir Plantilla Word"])

req_text_to_analyze = None

with tab1:
    st.subheader("Formulario de Requerimientos")
    
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha:", datetime.now())
    with col2:
        solicitante = st.text_input("Solicitante:")
        
    desc = st.text_area("1. Descripción General")
    obj = st.text_area("2. Objetivos Principales (Uno por línea)")
    func = st.text_area("3. Funcionalidades Requeridas (Especifique Prioridad)")
    
    st.markdown("**4. Datos Sensibles**")
    maneja_datos = st.selectbox("¿Maneja datos sensibles?", ["No", "Sí"])
    tipos_datos = st.text_input("Tipos de datos:", placeholder="ej. datos personales, financieros, etc.")
    nivel_sensibilidad = st.selectbox("Nivel de sensibilidad:", ["Bajo", "Medio", "Alto"])
    
    st.markdown("**5. Requisitos de Seguridad Específicos**")
    auth = st.text_input("Autenticación:", placeholder="Sí/No + tipo: usuario/contraseña, 2FA, etc.")
    autorizacion = st.text_input("Autorización (roles y permisos):")
    auditoria = st.text_input("Auditoría:", placeholder="¿Se necesita registro de acciones?")
    proteccion = st.text_input("Protección de datos:", placeholder="Cifrado, anonimato, etc.")
    otros_seg = st.text_area("Otros requisitos de seguridad:")
    
    st.markdown("**6. Usuarios y Accesos**")
    roles = st.text_area("Roles de usuarios y sus permisos:")
    
    obs = st.text_area("7. Observaciones Adicionales o Restricciones")
    
    if st.button("Enviar para Análisis (Formulario)"):
        if not project_name:
            st.warning("Debes ingresar el Nombre del Proyecto.")
        elif not desc or not obj or not func:
            st.warning("Por favor, llena al menos la descripción, objetivos y funcionalidades.")
        else:
            req_text_to_analyze = f"""Nombre del Proyecto: {project_name}
Fecha: {fecha}
Solicitante: {solicitante}

1. Descripción General
{desc}

2. Objetivos Principales
{obj}

3. Funcionalidades Requeridas
{func}

4. Datos Sensibles
¿Maneja datos sensibles?: {maneja_datos}
Tipos de datos: {tipos_datos}
Nivel de sensibilidad: {nivel_sensibilidad}

5. Requisitos de Seguridad Específicos
Autenticación: {auth}
Autorización: {autorizacion}
Auditoría: {auditoria}
Protección de datos: {proteccion}
Otros requisitos: {otros_seg}

6. Usuarios y Accesos
{roles}

7. Observaciones Adicionales
{obs}
"""

with tab2:
    st.subheader("Análisis mediante Plantilla DOCX")
    st.download_button(
        label="📥 Descargar Plantilla Word",
        data=generate_word_template(),
        file_name="plantilla_requerimientos.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    
    uploaded_file = st.file_uploader("Sube el Word llenado", type=["docx"])
    
    if st.button("Analizar Documento (Word)"):
        if not project_name:
            st.warning("Debes ingresar el Nombre del Proyecto.")
        elif uploaded_file is not None:
            req_text_to_analyze = extract_text_from_docx(uploaded_file)
        else:
            st.warning("Por favor, sube un archivo Word válido.")

# --- Ejecución del Grafo ---
if req_text_to_analyze:
    st.divider()
    st.info("Iniciando flujo multiagente...")
    
    execution_id = log_execution(project_name)
    st.write(f"**ID de Ejecución BD:** `{execution_id}`")
    
    graph = build_graph()
    
    initial_state = {
        "project_name": project_name,
        "requirements_text": req_text_to_analyze,
        "execution_id": execution_id,
        "central_init": None,
        "quality_report": None,
        "security_report": None,
        "evaluation": None,
        "final_report": None
    }
    
    status_text = st.empty()
    cols = st.columns(2)
    with cols[0]:
        col_q = st.expander("Reporte de Calidad (ISO 25023)", expanded=True)
    with cols[1]:
        col_s = st.expander("Reporte de Seguridad (ISO 27034)", expanded=True)
        
    col_eval = st.expander("Veredicto del Evaluador", expanded=True)
    col_final = st.expander("Reporte Final (Agente Central)", expanded=True)
    
    try:
        for output in graph.stream(initial_state):
            for key, value in output.items():
                status_text.text(f"Nodo completado: {key}")
                
                if key == "Central_Init":
                    st.success(f"**Agente Central (Recepción):**\n{value.get('central_init')}")
                elif key == "Quality":
                    try:
                        parsed_q = json.loads(value.get("quality_report", "{}"))
                        col_q.json(parsed_q)
                    except json.JSONDecodeError:
                        col_q.text(value.get("quality_report"))
                elif key == "Security":
                    try:
                        parsed_s = json.loads(value.get("security_report", "{}"))
                        col_s.json(parsed_s)
                    except json.JSONDecodeError:
                        col_s.text(value.get("security_report"))
                elif key == "Evaluator":
                    try:
                        parsed_e = json.loads(value.get("evaluation", "{}"))
                        col_eval.json(parsed_e)
                    except json.JSONDecodeError:
                        col_eval.text(value.get("evaluation"))
                elif key == "Central_Final":
                    col_final.success("Análisis Completado. Síntesis:")
                    col_final.markdown(value.get("final_report"))
                    status_text.success("¡Flujo completado exitosamente!")
                    
    except Exception as e:
        st.error(f"Error durante la ejecución del grafo: {str(e)}")
        st.exception(e)
