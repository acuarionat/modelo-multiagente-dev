import streamlit as st
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_service import process_batch_workflow
from database.repository import clear_tracking_data

st.set_page_config(page_title="Recepción de Requerimientos", page_icon="🦊", layout="wide")

st.title("🦊 Etapa 1: Recepción de Requerimientos (Vía GitLab)")
st.markdown("Plataforma automatizada para análisis de Historias de Usuario.")

# Sidebar options
with st.sidebar:
    st.header("Administración")
    if st.button("Limpiar Base de Seguimiento (Caché e Historial)"):
        clear_tracking_data()
        st.success("Base de datos limpia.")

try:
    adapter = GitLabAdapter()
except ValueError as e:
    st.error(f"Error de configuración: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"No se pudo conectar a GitLab: {str(e)}")
    st.stop()

if "milestones" not in st.session_state:
    with st.spinner("Cargando Sprints desde GitLab..."):
        st.session_state.milestones = adapter.get_milestones()
        st.session_state.all_labels = set()
        # To get all labels, we'd have to fetch project labels, but we can just let user type or we use predefined.
        # Simplification: Let user type labels separated by comma.

project_name = st.text_input("Nombre del Proyecto para Reportes:", placeholder="Ej: Sistema de Gestión", value=adapter.project.name)

st.subheader("Configuración del Lote")
milestone_options = {"Ninguno": None}
for m in st.session_state.milestones:
    milestone_options[m.title] = m.title
selected_milestone = st.selectbox("Seleccionar Sprint (Milestone):", list(milestone_options.keys()))

if st.button("Ejecutar Análisis por Lote", type="primary"):
    if not project_name:
        st.warning("Debes ingresar el Nombre del Proyecto.")
        st.stop()
        
    milestone_val = milestone_options[selected_milestone]
    
    with st.spinner("Obteniendo issues de GitLab..."):
        # Solo traer los que sean Historia de Usuario
        issues = adapter.list_open_issues(milestone_title=milestone_val, labels=["Historia de Usuario"])
        
    if not issues:
        st.info("No se encontraron 'Historias de Usuario' en el Sprint seleccionado.")
        st.stop()
        
    # Filtrar según la lógica estricta de labels
    issues_to_process = []
    for iss in issues:
        labels = iss.labels
        if "Analizada" in labels:
            continue
        if "Pendiente" in labels or "En revisión" in labels:
            issues_to_process.append(iss)
            
    if not issues_to_process:
        st.success(f"Se encontraron {len(issues)} historias, pero todas están Analizadas o no están Pendientes/En revisión. Nada que hacer.")
        st.stop()
        
    st.markdown(f"### Sprint {milestone_val or 'Personalizado'}")
    st.write(f"**{len(issues_to_process)} historias pendientes/en revisión encontradas.**")
    
    # Construir Contexto del Sprint
    sprint_context = f"Proyecto: {project_name}\nSprint: {milestone_val or 'Sin milestone'}\nHistorias a analizar: {len(issues_to_process)}\n"
    sprint_context += "Títulos:\n" + "\n".join([f"- {i.title}" for i in issues_to_process])
    
    status_container = st.container()
    metrics_container = st.container()
    
    start_time_total = time.time()
    
    if "processed_results" not in st.session_state:
        st.session_state.processed_results = {}
    run_results = []
        
    # Agrupar en lotes de MAX_ISSUES_PER_BATCH
    MAX_ISSUES_PER_BATCH = 5
    batches = [issues_to_process[i:i + MAX_ISSUES_PER_BATCH] for i in range(0, len(issues_to_process), MAX_ISSUES_PER_BATCH)]
    
    with status_container:
        st.markdown("### Progreso del Análisis (Por Agente / Lote)")
        st.markdown(f"1. Cargando {len(issues_to_process)} Issues del Sprint ✔")
        st.markdown(f"2. Validando plantillas y filtrando Issues con Python ✔")
        
        global_ph = st.empty()
        completed_batches = 0
        processed_stories = 0
        failed_batches = []
        incomplete_stories = []
        
        for batch_idx, batch in enumerate(batches):
            batch_num = batch_idx + 1
            total_batches = len(batches)
            global_ph.markdown(f"**Procesando lote {batch_num} de {total_batches} ({len(batch)} historias)**... ⏳\n*(Agente Central -> Calidad -> Seguridad -> Evaluador -> Central Final)*")
            
            try:
                from integrations.issue_service import process_batch_workflow
                batch_results = process_batch_workflow(batch, project_name, sprint_context)
                run_results.extend(batch_results)
                
                for res in batch_results:
                    iid = res["issue_iid"]
                    st.session_state.processed_results[iid] = res
                    if res["status"] == "ok":
                        st.markdown(f"**HU-{iid}** ✔ Requerimientos formalizados y evaluados")
                    else:
                        st.error(f"HU-{iid} — {' '.join(res['errors'])} No se publicó comentario ni se actualizó la etiqueta.")
                        incomplete_stories.append(iid)
                valid_in_batch = sum(res["status"] == "ok" for res in batch_results)
                if valid_in_batch == len(batch_results):
                    completed_batches += 1
                processed_stories += valid_in_batch
                    
            except Exception as e:
                st.error(f"❌ Error en lote {batch_num}: {str(e)}")
                failed_batches.append(batch_num)
                
            elapsed_total = time.time() - start_time_total
            avg_time = elapsed_total / processed_stories if processed_stories else 0
            
            with metrics_container:
                m1, m2, m3 = st.columns(3)
                m1.metric("Lotes Completados", f"{completed_batches} / {total_batches}")
                m2.metric("Tiempo Total", f"{elapsed_total:.1f} s")
                m3.metric("Tiempo Promedio/Historia", f"{avg_time:.1f} s" if processed_stories else "N/D")
                
        if failed_batches or incomplete_stories:
            failed_list = ", ".join(map(str, failed_batches))
            details = []
            if failed_list:
                details.append(f"lotes: {failed_list}")
            if incomplete_stories:
                details.append(f"historias: {', '.join(map(str, incomplete_stories))}")
            global_ph.markdown(f"**Análisis incompleto ({'; '.join(details)}).** ❌")
        else:
            global_ph.markdown("**¡Análisis completo! Todos los lotes procesados.** ✔")
        st.session_state.last_batch_results = run_results
        st.session_state.last_project_name = project_name
        st.session_state.last_milestone = milestone_val or "Personalizado"
            
    if failed_batches or incomplete_stories:
        st.error("El análisis del Sprint terminó con errores.")
    else:
        st.success("¡Análisis del Sprint finalizado!")

# Resultados y documentos consolidados del último lote
if st.session_state.get("last_batch_results"):
    st.divider()
    from core.utils import (
        build_traceability_rows, calculate_batch_summary,
        generate_batch_formal_docx, generate_batch_report_pdf,
    )
    results = st.session_state.last_batch_results
    summary = calculate_batch_summary(results)
    st.subheader("Resumen global")
    st.write(f"**Milestone:** {st.session_state.last_milestone}")
    a, b, c, d = st.columns(4)
    a.metric("Historias procesadas", summary["procesadas"])
    b.metric("Con error", summary["errores"])
    c.metric("Calidad promedio", f"{summary['calidad_promedio'] * 100:.0f} %" if summary["calidad_promedio"] is not None else "N/D")
    d.metric("Seguridad promedio", f"{summary['seguridad_promedio'] * 100:.0f} %" if summary["seguridad_promedio"] is not None else "N/D")
    st.write(f"**Veredictos:** {summary['veredictos']} — **Requerimientos sugeridos:** {summary['requerimientos']}")

    st.subheader("Resultados por historia")
    for result in results:
        if result["status"] != "ok":
            st.error(f"HU-{result['issue_iid']:03d} — {' '.join(result['errors'])}")
            continue
        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        title = f"{central['historia_id']} — {central['titulo']}"
        with st.expander(title):
            st.write(f"**Veredicto:** {evaluation['veredicto']} · **Calidad:** {quality['indice'] * 100:.0f} % · **Seguridad:** {security['indice'] * 100:.0f} % · **LoT:** {security.get('lot_recomendado', 'No informado')}")
            st.write(f"**Requerimientos sugeridos:** {len(central['requerimientos'])} · **Correcciones obligatorias:** {len(evaluation.get('correcciones_obligatorias', []))}")
            st.write("**Métricas de calidad:**", quality.get("metricas", {}))
            st.write("**Métricas de seguridad:**", security.get("metricas", {}))
            st.write("**Riesgos:**", evaluation.get("riesgos_criticos", []))
            st.write("**Recomendaciones:**", quality.get("recomendaciones", []) + security.get("recomendaciones", []))
            st.write("**Comentario publicado en GitLab:**", "Sí" if result.get("comment_published") else "No")

    st.subheader("Matriz de trazabilidad completa")
    try:
        rows = build_traceability_rows(results)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        for row in rows:
            with st.expander(f"{row['id']} — {row['tipo']}"):
                st.write("**Historia:**", row["historia"])
                st.write("**Requerimiento:**", row["requerimiento_formal"])
                st.write("**Justificación:**", row["justificacion"])
        import csv
        import io
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
        st.download_button("Descargar matriz CSV", csv_buffer.getvalue().encode("utf-8-sig"), "matriz_trazabilidad.csv", "text/csv")
    except ValueError as exc:
        st.error(str(exc))

    st.subheader("Documentos consolidados")
    col_pdf, col_docx = st.columns(2)
    with col_pdf:
        if st.button("Generar Reporte Ejecutivo del Lote"):
            st.session_state.batch_pdf = generate_batch_report_pdf(st.session_state.last_project_name, st.session_state.last_milestone, results).getvalue()
        if st.session_state.get("batch_pdf"):
            st.download_button("Descargar PDF consolidado", st.session_state.batch_pdf, "Reporte_Ejecutivo_Lote.pdf", "application/pdf")
    with col_docx:
        if st.button("Generar Documento Formal Consolidado"):
            st.session_state.batch_docx = generate_batch_formal_docx(st.session_state.last_project_name, st.session_state.last_milestone, results).getvalue()
        if st.session_state.get("batch_docx"):
            st.download_button("Descargar DOCX consolidado", st.session_state.batch_docx, "Requerimientos_Consolidados.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
