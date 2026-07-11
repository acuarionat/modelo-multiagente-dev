import streamlit as st
import os
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_service import process_issue_workflow

st.set_page_config(page_title="Recepción de Requerimientos (GitLab)", page_icon="🦊", layout="wide")

st.title("🦊 Etapa 1: Recepción de Requerimientos (Vía GitLab)")
st.markdown("El sistema actuará como herramienta de apoyo leyendo las Historias de Usuario desde GitLab, ejecutando el flujo multiagente y actualizando el Issue directamente.")

# Instanciar el adaptador (verificar que existen variables de entorno)
try:
    adapter = GitLabAdapter()
except ValueError as e:
    st.error(f"Error de configuración: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"No se pudo conectar a GitLab: {str(e)}")
    st.stop()

st.subheader("Selecciona una Historia de Usuario (Issue Abierto)")

if st.button("Actualizar Lista de Issues"):
    st.session_state.issues = adapter.list_open_issues()

if "issues" not in st.session_state:
    with st.spinner("Cargando issues desde GitLab..."):
        st.session_state.issues = adapter.list_open_issues()

if not st.session_state.issues:
    st.info("No hay issues abiertos en el proyecto configurado.")
    st.stop()

# Crear opciones para el selectbox
issue_options = {f"#{issue.iid}: {issue.title}": issue.iid for issue in st.session_state.issues}
selected_issue_str = st.selectbox("Issue a analizar:", list(issue_options.keys()))

project_name = st.text_input("Nombre del Proyecto para Reportes:", placeholder="Ej: Sistema de Gestión de Inventarios", value=adapter.project.name)

if st.button("Ejecutar Análisis Multiagente sobre el Issue"):
    if not project_name:
        st.warning("Debes ingresar el Nombre del Proyecto.")
    else:
        issue_iid = issue_options[selected_issue_str]
        
        st.divider()
        st.info(f"Iniciando flujo multiagente para el Issue #{issue_iid}...")
        
        start_time_total = time.time()
        
        with st.spinner("El sistema multiagente está analizando el Issue, por favor espera..."):
            try:
                results = process_issue_workflow(issue_iid, project_name)
                end_time_total = time.time()
                
                # Guardar en session_state para renderizado
                st.session_state.parsed_q = results["quality_json"]
                st.session_state.parsed_s = results["security_json"]
                st.session_state.parsed_e = results["eval_json"]
                st.session_state.parsed_cf = results["final_json"]
                st.session_state.issue_data = results["issue_data"]
                st.session_state.total_time = end_time_total - start_time_total
                
                st.success("¡Flujo completado exitosamente! Los documentos fueron adjuntados en GitLab y se añadió un comentario.")
            except Exception as e:
                st.error(f"Error durante la ejecución del grafo: {str(e)}")

# --- Renderizado de Resultados ---
if 'parsed_q' in st.session_state:
    st.divider()
    
    st.markdown("### Resumen del Análisis")
    
    col_issue = st.expander("Datos del Issue (JSON Base)", expanded=False)
    col_issue.json(st.session_state.issue_data)
    
    cols = st.columns(2)
    with cols[0]:
        col_q = st.expander("Reporte de Calidad (ISO 25023)", expanded=True)
        col_q.json(st.session_state.parsed_q)
    with cols[1]:
        col_s = st.expander("Reporte de Seguridad (ISO 27034)", expanded=True)
        col_s.json(st.session_state.parsed_s)
        
    col_eval = st.expander("Veredicto del Evaluador", expanded=True)
    col_eval.json(st.session_state.parsed_e)
    
    col_final = st.expander("Reporte Final (Agente Central)", expanded=True)
    col_final.success("Análisis Completado. Síntesis:")
    col_final.markdown(st.session_state.parsed_cf.get("resumen_interfaz", "No se generó resumen de interfaz."))
    
    if "total_time" in st.session_state:
        st.info(f"⏱️ **Tiempo total de ejecución del modelo:** {st.session_state.total_time:.2f} segundos. (Los detalles por agente se guardaron en log estructurado JSON).")
    
    st.divider()
    st.subheader("📊 Matriz de Trazabilidad y Documento Formal")
    st.write("Estos documentos ya fueron generados y subidos como archivos adjuntos al Issue de GitLab correspondiente.")
    
    tab_doc, tab_matriz = st.tabs(["Previsualización Documento Formal", "Previsualización Matriz de Trazabilidad"])
    with tab_doc:
        st.markdown(st.session_state.parsed_cf.get("documento_formal_md", "No se generó el documento formal."))
    with tab_matriz:
        st.markdown(st.session_state.parsed_cf.get("matriz_trazabilidad_md", "No se generó la matriz de trazabilidad."))        
