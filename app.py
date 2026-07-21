import streamlit as st
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_service import procesar_flujo_lote
from database.repository import limpiar_datos_seguimiento

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMI_LOGO_PATH = os.path.join(BASE_DIR, "assets", "emi_logo.png")

st.set_page_config(page_title="EMI | Recepción de Requerimientos", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
    :root {
        --emi-blue: #07549A;
        --emi-blue-dark: #063A6B;
        --emi-blue-soft: #EAF3FB;
        --emi-yellow: #F2C300;
        --emi-yellow-soft: #FFF8D6;
        --emi-ink: #17324D;
        --emi-line: #D8E4EF;
    }

    .stApp {
        background: #FFFFFF;
        color: var(--emi-ink);
    }

    [data-testid="stHeader"] {
        background: rgba(255, 255, 255, 0.96);
        border-bottom: 1px solid var(--emi-line);
    }

    [data-testid="stAppViewContainer"] > .main .block-container {
        max-width: 1480px;
        padding-top: 1.4rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--emi-blue-dark) 0%, #0A4A83 100%);
        border-right: 5px solid var(--emi-yellow);
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1.2rem;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span:not([data-testid="stIconMaterial"]) {
        color: #FFFFFF !important;
    }

    .emi-header {
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 155px;
        padding: 1.2rem 1.6rem;
        background: linear-gradient(115deg, var(--emi-blue-dark), var(--emi-blue));
        border-left: 9px solid var(--emi-yellow);
        border-radius: 10px;
        box-shadow: 0 8px 24px rgba(6, 58, 107, 0.14);
    }

    .emi-eyebrow {
        color: var(--emi-yellow);
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.13em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }

    .emi-header h1 {
        color: #FFFFFF !important;
        font-size: clamp(1.75rem, 3vw, 2.65rem);
        line-height: 1.12;
        margin: 0;
        padding: 0;
    }

    .emi-header p {
        color: #DDEEFF;
        font-size: 1rem;
        margin: 0.65rem 0 0;
    }

    h1, h2, h3 {
        color: var(--emi-blue-dark) !important;
        letter-spacing: -0.015em;
    }

    h2, h3 {
        border-bottom: 3px solid var(--emi-yellow);
        padding-bottom: 0.38rem;
    }

    div[data-testid="stForm"],
    div[data-testid="stExpander"],
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--emi-line);
        border-radius: 9px;
        box-shadow: 0 4px 14px rgba(7, 84, 154, 0.07);
        overflow: hidden;
    }

    div[data-testid="stExpander"] details summary {
        background: var(--emi-blue-soft);
        color: var(--emi-blue-dark);
        font-weight: 700;
    }

    div[data-testid="stMetric"] {
        min-height: 112px;
        padding: 1rem 1.1rem;
        background: #FFFFFF;
        border: 1px solid var(--emi-line);
        border-top: 5px solid var(--emi-yellow);
        border-radius: 9px;
        box-shadow: 0 5px 16px rgba(7, 84, 154, 0.08);
    }

    [data-testid="stMetricLabel"] {
        color: #58708A;
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        color: var(--emi-blue-dark);
        font-weight: 800;
    }

    .stButton > button,
    .stDownloadButton > button {
        min-height: 2.85rem;
        border-radius: 7px;
        border: 2px solid var(--emi-blue);
        background: #FFFFFF;
        color: var(--emi-blue-dark);
        font-weight: 750;
        transition: all 0.18s ease;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: var(--emi-yellow);
        background: var(--emi-yellow-soft);
        color: var(--emi-blue-dark);
        transform: translateY(-1px);
    }

    .stButton > button[kind="primary"] {
        border-color: var(--emi-blue);
        background: var(--emi-blue);
        color: #FFFFFF;
        box-shadow: 0 5px 14px rgba(7, 84, 154, 0.2);
    }

    .stButton > button[kind="primary"]:hover {
        border-color: var(--emi-yellow);
        background: var(--emi-blue-dark);
        color: var(--emi-yellow);
    }

    [data-testid="stSidebar"] .stButton > button {
        border-color: var(--emi-yellow);
        background: var(--emi-yellow);
        color: var(--emi-blue-dark) !important;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-color: #B8CADB;
        border-radius: 7px;
        color: #111111 !important;
    }

    [data-testid="stTextInput"] input {
        background: #FFFFFF !important;
    }

    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: #F1F7FC !important;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stSelectbox"] div[data-baseweb="select"] span,
    [data-testid="stSelectbox"] div[data-baseweb="select"] input {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #111111 !important;
    }

    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="popover"] ul {
        background: #F7FBFF !important;
    }

    [data-baseweb="popover"] li,
    [data-baseweb="popover"] div {
        color: #111111 !important;
    }

    [data-baseweb="popover"] li:hover,
    [data-baseweb="popover"] li[aria-selected="true"] {
        background: #DCECF8 !important;
        color: var(--emi-blue-dark) !important;
    }

    [data-testid="stTextInput"] input:focus {
        border-color: var(--emi-blue);
        box-shadow: 0 0 0 2px rgba(7, 84, 154, 0.13);
    }

    div[data-testid="stAlert"] {
        border: 1px solid #BCD4E8;
        border-left: 6px solid var(--emi-yellow);
        border-radius: 7px;
        background: #F5F9FD;
        color: var(--emi-ink);
    }

    hr {
        border-color: var(--emi-yellow) !important;
        opacity: 0.7;
    }

    [data-testid="stCaptionContainer"] {
        color: #5B7187;
    }

    @media (max-width: 800px) {
        .emi-header { min-height: auto; padding: 1rem; }
        [data-testid="stAppViewContainer"] > .main .block-container { padding-top: 0.8rem; }
    }
</style>
""", unsafe_allow_html=True)

logo_col, title_col = st.columns([1.05, 2.45])
with logo_col:
    st.image(EMI_LOGO_PATH, use_container_width=True)
with title_col:
    st.markdown("""
    <div class="emi-header">
        <div class="emi-eyebrow">Escuela Militar de Ingeniería</div>
        <h1>Etapa 1 · Recepción de Requerimientos</h1>
        <p>Control, evaluación asistida y trazabilidad de Historias de Usuario mediante GitLab.</p>
    </div>
    """, unsafe_allow_html=True)

st.info("Las métricas e indicadores son valoraciones asistidas basadas en la evidencia disponible. Apoyan la decisión del responsable y no constituyen aprobación automática ni certificación.")

# Sidebar options
with st.sidebar:
    st.image(EMI_LOGO_PATH, use_container_width=True)
    st.markdown("### Sistema Multiagente")
    st.caption("Recepción y seguimiento de requerimientos")
    st.divider()
    st.header("Administración")
    if st.button("Limpiar Base de Seguimiento (Caché e Historial)"):
        limpiar_datos_seguimiento()
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
        st.session_state.milestones = adapter.obtener_hitos()
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
    for stale_key in ("last_batch_result", "batch_pdf", "batch_docx"):
        st.session_state.pop(stale_key, None)
    if not project_name:
        st.warning("Debes ingresar el Nombre del Proyecto.")
        st.stop()
        
    milestone_val = milestone_options[selected_milestone]
    
    with st.spinner("Obteniendo issues de GitLab..."):
        # Solo traer los que sean Historia de Usuario
        issues = adapter.listar_issues_abiertos(milestone_title=milestone_val, labels=["Historia de Usuario"])
        
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
                from integrations.issue_service import procesar_flujo_lote
                batch_result = procesar_flujo_lote(batch, project_name, sprint_context)
                batch_results = batch_result["issues"]
                run_results.extend(batch_results)
                
                for res in batch_results:
                    iid = res["issue_iid"]
                    st.session_state.processed_results[iid] = res
                    if res.get("estado_procesamiento") == "informacion_insuficiente":
                        st.warning(f"**HU-{iid}** — Información insuficiente: {', '.join(res['validacion_entrada']['campos_faltantes'])}. No fue enviada al modelo.")
                        incomplete_stories.append(iid)
                    elif res["status"] == "ok":
                        st.markdown(f"**HU-{iid}** ✔ Procesamiento completo · Evaluación: {res['estado_evaluacion']}")
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
        if run_results:
            from core.utils import construir_resultado_lote
            st.session_state.last_batch_result = construir_resultado_lote(
                project_name, milestone_val or "Personalizado", run_results
            )
        else:
            st.info("No se generó un resumen ni documentos porque el lote no produjo resultados consolidados.")
        st.session_state.last_project_name = project_name
        st.session_state.last_milestone = milestone_val or "Personalizado"
            
    if failed_batches or incomplete_stories:
        st.error("El análisis del Sprint terminó con errores.")
    else:
        st.success("¡Análisis del Sprint finalizado!")

# Resultados y documentos consolidados del último lote
if st.session_state.get("last_batch_result", {}).get("issues"):
    st.divider()
    from core.utils import (
        generar_documento_formal_lote_docx, generar_reporte_lote_pdf,
    )
    batch_result = st.session_state.last_batch_result
    results = batch_result["issues"]
    summary = batch_result["summary"]
    st.subheader("Resumen global")
    st.write(f"**Milestone:** {st.session_state.last_milestone}")
    a, b, c, d = st.columns(4)
    a.metric("Historias procesadas", summary["procesadas"])
    b.metric("Con error", summary["errores"])
    c.metric("Índice parcial de calidad promedio", f"{summary['calidad_promedio'] * 100:.0f} %" if summary["calidad_promedio"] is not None else "N/D")
    d.metric("Cobertura documental de seguridad promedio", f"{summary['seguridad_promedio'] * 100:.0f} %" if summary["seguridad_promedio"] is not None else "N/D")
    st.write(f"**Veredictos:** {summary['veredictos']} — **Requerimientos sugeridos:** {summary['requerimientos']}")
    st.write(
        f"**Total:** {summary['total']} · **Aprobadas:** {summary['aprobadas']} · "
        f"**Requieren corrección:** {summary['requieren_correccion']} · **Alertas:** {summary['alertas']} · "
        f"**Información insuficiente:** {summary['informacion_insuficiente']}"
    )
    st.write(
        f"**Calidad mínima:** {summary['calidad_minima'] * 100:.0f} %" if summary["calidad_minima"] is not None else "**Calidad mínima:** N/D",
        f" · **Seguridad mínima:** {summary['seguridad_minima'] * 100:.0f} %" if summary["seguridad_minima"] is not None else " · **Seguridad mínima:** N/D",
        f" · **Historias bajo meta:** {summary['historias_bajo_meta']} · **Riesgos críticos:** {summary['riesgos_criticos']}"
    )

    st.subheader("Resultados por historia")
    for result in results:
        if result.get("estado_procesamiento") == "informacion_insuficiente":
            st.warning(f"HU-{result['issue_iid']:03d} — Información insuficiente: {', '.join(result['validacion_entrada']['campos_faltantes'])}")
            continue
        if result["status"] != "ok":
            st.error(f"HU-{result['issue_iid']:03d} — {' '.join(result['errors'])}")
            continue
        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        title = f"{central['historia_id']} — {central['titulo']}"
        with st.expander(title):
            quality_value = f"{quality['indice'] * 100:.0f} %" if quality.get("indice") is not None else "N/D"
            security_value = f"{security['indice'] * 100:.0f} %" if security.get("indice") is not None else "N/D"
            st.write(f"**Estado de evaluación asistida:** {result['estado_evaluacion']} · **Índice parcial de calidad funcional:** {quality_value} · **Índice de cobertura documental de seguridad:** {security_value} · **Nivel de aseguramiento recomendado — LoT:** {security.get('lot_recomendado', 'No informado')}")
            st.caption("El LoT no representa la confianza del modelo. La aceptación final requiere revisión humana.")
            st.write(f"**Requerimientos sugeridos:** {len(central['requerimientos'])} · **Correcciones obligatorias:** {len(evaluation.get('correcciones_obligatorias', []))}")
            st.write("**Métricas de calidad:**", quality.get("metricas", {}))
            st.write("**Métricas de seguridad:**", security.get("metricas", {}))
            st.write("**Riesgos:**", evaluation.get("riesgos_criticos", []))
            st.write("**Recomendaciones:**", quality.get("recomendaciones", []) + security.get("recomendaciones", []))
            st.write("**Comentario publicado en GitLab:**", "Sí" if result.get("comment_published") else "No")

    st.subheader("Matriz de trazabilidad completa")
    try:
        rows = batch_result["traceability_rows"]
        if not rows:
            raise ValueError("No fue posible construir la matriz porque el Agente Central no devolvió requerimientos formalizados.")
        st.dataframe(rows, use_container_width=True, hide_index=True)
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
            st.session_state.batch_pdf = generar_reporte_lote_pdf(batch_result).getvalue()
        if st.session_state.get("batch_pdf"):
            st.download_button("Descargar PDF consolidado", st.session_state.batch_pdf, "Reporte_Ejecutivo_Lote.pdf", "application/pdf")
    with col_docx:
        if st.button("Generar Documento Formal Consolidado"):
            st.session_state.batch_docx = generar_documento_formal_lote_docx(batch_result).getvalue()
        if st.session_state.get("batch_docx"):
            st.download_button("Descargar DOCX consolidado", st.session_state.batch_docx, "Requerimientos_Consolidados.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
