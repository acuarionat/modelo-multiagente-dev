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
from project_config import load_project_config, save_project_config

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
        margin:  1rem 0 0 0;
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
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border-color: #B8CADB;
        border-radius: 7px;
        color: #111111 !important;
    }

    [data-testid="stTextInput"] input {
        background: #FFFFFF !important;
    }

    [data-testid="stTextArea"] textarea {
        background: #FFFFFF !important;
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
        border-color: #B8CADB;
        border-radius: 7px;
    }

    /* Los formularios se muestran sobre fondo blanco: sus etiquetas deben
       conservar contraste sin afectar las etiquetas blancas del sidebar. */
    [data-testid="stMain"] [data-testid="stWidgetLabel"],
    [data-testid="stMain"] [data-testid="stWidgetLabel"] p,
    [data-testid="stMain"] [data-testid="stWidgetLabel"] span,
    [data-testid="stMain"] label,
    [data-testid="stMain"] label p,
    [data-testid="stMain"] label span {
        color: var(--emi-ink) !important;
        -webkit-text-fill-color: var(--emi-ink) !important;
        opacity: 1 !important;
        font-weight: 650;
    }

    [data-testid="stMain"] [data-testid="stTextInput"] input,
    [data-testid="stMain"] [data-testid="stTextArea"] textarea {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    [data-testid="stMain"] [data-testid="stTextInput"] input::placeholder,
    [data-testid="stMain"] [data-testid="stTextArea"] textarea::placeholder {
        color: #66788A !important;
        -webkit-text-fill-color: #66788A !important;
        opacity: 1 !important;
    }

    [data-testid="stMain"] [data-testid="stCaptionContainer"],
    [data-testid="stMain"] [data-testid="InputInstructions"] {
        color: #5B7187 !important;
        -webkit-text-fill-color: #5B7187 !important;
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

    .st-key-stage_shell {
        position: relative;
        max-width: 1040px;
        margin: 0.9rem auto 0.7rem;
        padding: 0.7rem 1.25rem 0.45rem;
        background: #FFFFFF;
        border-top: 1px solid #E5ECF3;
        border-bottom: 1px solid #D8E2EC;
    }

    .stage-track {
        position: absolute;
        top: 2.55rem;
        left: 12.5%;
        right: 12.5%;
        height: 2px;
        background: #DCE5EE;
        z-index: 0;
    }

    .stage-label {
        min-height: 1.35rem;
        margin-top: 0.15rem;
        color: #8A9DB5;
        font-size: 0.75rem;
        font-weight: 700;
        line-height: 1.15;
        text-align: center;
    }

    .stage-label.active { color: var(--emi-blue-dark); }

    .stage-status {
        display: none;
    }

    [class*="st-key-stage_nav_"] {
        position: relative;
        z-index: 1;
        display: flex;
        justify-content: center;
    }

    .st-key-stage_shell [class*="st-key-stage_nav_"] button {
        width: 3.3rem !important;
        min-width: 3.3rem !important;
        height: 3.3rem !important;
        min-height: 3.3rem !important;
        padding: 0.15rem;
        border: 2px solid #FFFFFF !important;
        border-radius: 50% !important;
        background: #0878D1 !important;
        color: var(--emi-yellow) !important;
        -webkit-text-fill-color: var(--emi-yellow) !important;
        font-size: 1.4rem !important;
        font-weight: 850;
        line-height: 1;
        position: relative;
        text-shadow: 0 1px 1px rgba(6, 58, 107, 0.35);
        box-shadow: 0 0 0 4px #FFFFFF, 0 3px 8px rgba(7, 84, 154, 0.16);
    }

    .st-key-stage_shell [class*="st-key-stage_nav_"] button::after {
        position: absolute;
        right: -0.18rem;
        bottom: -0.12rem;
        display: grid;
        place-items: center;
        width: 1.12rem;
        height: 1.12rem;
        border: 2px solid #FFFFFF;
        border-radius: 50%;
        background: var(--emi-yellow);
        color: var(--emi-blue-dark);
        -webkit-text-fill-color: var(--emi-blue-dark) !important;
        font-size: 0.62rem;
        font-weight: 900;
        line-height: 1;
        text-shadow: none;
    }

    .st-key-stage_shell [class*="st-key-stage_nav_"] button p {
        margin: 0 !important;
        color: var(--emi-yellow) !important;
        -webkit-text-fill-color: var(--emi-yellow) !important;
        font-size: 1.4rem !important;
        line-height: 1 !important;
    }

    [class*="st-key-stage_nav_requerimientos_"] button::after { content: "1"; }
    [class*="st-key-stage_nav_diseno_"] button::after { content: "2"; }
    [class*="st-key-stage_nav_codificacion_"] button::after { content: "3"; }
    [class*="st-key-stage_nav_pruebas_"] button::after { content: "4"; }

    .st-key-stage_shell [class*="st-key-stage_nav_"] button:hover {
        border-color: var(--emi-yellow) !important;
        background: #0968B5 !important;
        color: #FFE24A !important;
        -webkit-text-fill-color: #FFE24A !important;
        transform: translateY(-1px);
    }

    .st-key-stage_shell [class*="st-key-stage_nav_"][class*="_active"] button {
        border: 2px solid #FFFFFF !important;
        background: #005CB9 !important;
        color: var(--emi-yellow) !important;
        -webkit-text-fill-color: var(--emi-yellow) !important;
        box-shadow: 0 0 0 5px #79B9EC, 0 3px 10px rgba(6, 58, 107, 0.28);
    }

    .coming-soon {
        margin-top: 1rem;
        padding: 2.5rem 2rem;
        border: 1px solid var(--emi-line);
        border-top: 6px solid var(--emi-yellow);
        border-radius: 12px;
        background: linear-gradient(145deg, #FFFFFF, #F5F9FD);
        box-shadow: 0 8px 24px rgba(7, 84, 154, 0.09);
        text-align: center;
    }

    .coming-soon-icon { font-size: 3rem; }
    .coming-soon h2 { border: 0; margin: 0.6rem 0; }
    .coming-soon-badge {
        display: inline-block;
        margin-top: 0.8rem;
        padding: 0.3rem 0.75rem;
        border-radius: 999px;
        background: var(--emi-yellow-soft);
        color: var(--emi-blue-dark);
        font-size: 0.82rem;
        font-weight: 800;
        text-transform: uppercase;
    }

    @media (max-width: 800px) {
        .emi-header { min-height: auto; padding: 1rem; }
        .st-key-stage_shell { padding: 0.6rem 0.2rem 0.35rem; }
        .stage-track { left: 13%; right: 13%; }
        .st-key-stage_shell [class*="st-key-stage_nav_"] button {
            width: 2.85rem !important; min-width: 2.85rem !important;
            height: 2.85rem !important; min-height: 2.85rem !important;
            font-size: 0.9rem !important;
        }
        .st-key-stage_shell [class*="st-key-stage_nav_"] button p { font-size: 1.15rem !important; }
        .stage-label { font-size: 0.65rem; }
        [data-testid="stAppViewContainer"] > .main .block-container { padding-top: 0.8rem; }
    }
</style>
""", unsafe_allow_html=True)

STAGES = (
    ("requerimientos", "Requerimientos", "Recepción de requerimientos", "☷"),
    ("diseno", "Diseño", "Diseño", "◇"),
    ("codificacion", "Codificación", "Codificación", "</>"),
    ("pruebas", "Pruebas", "Pruebas", "✓"),
)

MILESTONES_BY_STAGE = {
    "requerimientos": "Recepción de Requerimientos",
    "diseno": "Diseño",
    "codificacion": "Codificación",
    "pruebas": "Pruebas",
}
REQUIRED_MILESTONES = tuple(MILESTONES_BY_STAGE.values())


def render_stage_navigation():
    """Renderiza el menú no lineal y conserva la etapa elegida en la sesión."""
    if st.session_state.get("etapa_actual") not in {stage[0] for stage in STAGES}:
        st.session_state["etapa_actual"] = "requerimientos"

    current = st.session_state["etapa_actual"]
    with st.container(key="stage_shell"):
        st.markdown('<div class="stage-track"></div>', unsafe_allow_html=True)
        columns = st.columns(4)
        for index, (stage_id, short_name, full_name, icon) in enumerate(STAGES, start=1):
            with columns[index - 1]:
                state_suffix = "active" if current == stage_id else "pending"
                if st.button(
                    icon,
                    key=f"stage_nav_{stage_id}_{state_suffix}",
                    help=full_name,
                    use_container_width=False,
                ):
                    st.session_state["etapa_actual"] = stage_id
                    st.rerun()
                label_class = "stage-label active" if current == stage_id else "stage-label"
                st.markdown(f'<div class="{label_class}" title="{full_name}">{short_name}</div>', unsafe_allow_html=True)
        current_name = next(stage[2] for stage in STAGES if stage[0] == current)
        st.markdown(f'<div class="stage-status">Etapa actual: {current_name}</div>', unsafe_allow_html=True)


def render_coming_soon(stage_id):
    stage = next(item for item in STAGES if item[0] == stage_id)
    st.markdown(
        f"""
        <div class="coming-soon">
            <div class="coming-soon-icon">{stage[3]}</div>
            <h2>Etapa de {stage[2]}</h2>
            <p>Esta etapa forma parte del flujo de control, seguimiento y trazabilidad del
            desarrollo de software. Su funcionalidad será incorporada en una siguiente
            versión del sistema.</p>
            <span class="coming-soon-badge">Próximamente</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 1.3, 1])
    with center:
        if st.button("← Volver a Recepción de requerimientos", type="primary", use_container_width=True):
            st.session_state["etapa_actual"] = "requerimientos"
            st.rerun()

logo_col, title_col = st.columns([1.05, 2.45])
with logo_col:
    st.image(EMI_LOGO_PATH, use_container_width=True)
with title_col:
    st.markdown("""
    <div class="emi-header">
        <div class="emi-eyebrow">Escuela Militar de Ingeniería</div>
        <h1>Modelo Multiagente de Control y Seguimiento</h1>
        <p>Proceso adaptativo para el desarrollo y la trazabilidad de software.</p>
    </div>
    """, unsafe_allow_html=True)

saved_config = load_project_config()
editing_config = st.session_state.get("editing_project_config", False)

if saved_config is None or editing_config:
    st.subheader("Configuración del Proyecto")
    st.caption("Define el contexto del proyecto y valida GitLab antes de acceder a las etapas.")
    defaults = saved_config or {}
    with st.form("project_configuration"):
        st.markdown("### Información General")
        left, right = st.columns(2)
        with left:
            cfg_name = st.text_input("Nombre del proyecto *", value=defaults.get("name", ""))
            cfg_description = st.text_area("Descripción general *", value=defaults.get("description", ""))
            cfg_general_objective = st.text_area("Objetivo general *", value=defaults.get("general_objective", ""))
        with right:
            cfg_specific_objectives = st.text_area("Objetivos específicos *", value=defaults.get("specific_objectives", ""))
            cfg_scope = st.text_area("Alcance *", value=defaults.get("scope", ""))
            cfg_actors = st.text_area("Actores principales *", value=defaults.get("actors", ""))

        st.markdown("### Integración con GitLab")
        gitlab_url = st.text_input("URL del servidor GitLab *", value=defaults.get("gitlab_url", os.getenv("GITLAB_URL", "")))
        gitlab_project = st.text_input("Proyecto GitLab *", value=defaults.get("gitlab_project", os.getenv("GITLAB_PROJECT_ID", "")), help="ID numérico o ruta namespace/proyecto")
        gitlab_token = st.text_input("Token de acceso *", value=defaults.get("gitlab_token", os.getenv("GITLAB_TOKEN", "")), type="password")

        values = {
            "name": cfg_name, "description": cfg_description,
            "general_objective": cfg_general_objective,
            "specific_objectives": cfg_specific_objectives, "scope": cfg_scope,
            "actors": cfg_actors, "gitlab_url": gitlab_url,
            "gitlab_project": gitlab_project, "gitlab_token": gitlab_token,
        }
        connection_signature = (gitlab_url.strip(), gitlab_project.strip(), gitlab_token.strip())
        test_col, save_col = st.columns([1, 2])
        test_connection = test_col.form_submit_button("Probar conexión", use_container_width=True)
        save_and_start = save_col.form_submit_button("Guardar configuración e iniciar proyecto", type="primary", use_container_width=True)

    if test_connection:
        if not all(connection_signature):
            st.error("Completa la URL, el proyecto y el token de GitLab.")
        else:
            try:
                with st.spinner("Validando GitLab y verificando milestones..."):
                    test_adapter = GitLabAdapter(*connection_signature[::2], project_id=connection_signature[1])
                    milestone_status = test_adapter.asegurar_hitos(list(REQUIRED_MILESTONES))
                st.session_state["verified_gitlab"] = connection_signature
                st.session_state["milestone_status"] = milestone_status
                st.success(f"Conexión verificada con {test_adapter.project.name}. Milestones verificados sin duplicados.")
            except Exception as exc:
                st.session_state.pop("verified_gitlab", None)
                st.error(f"No se pudo validar la conexión: {exc}")

    verified = st.session_state.get("verified_gitlab") == connection_signature
    st.markdown("### Estado")
    c1, c2, c3 = st.columns(3)
    c1.metric("GitLab", "Conectado" if verified else "Pendiente")
    c2.metric("Milestones", "Verificados" if verified else "Pendientes")
    c3.metric("Contexto", defaults.get("context_version", "v1.0"))

    if save_and_start:
        missing = [key for key, value in values.items() if not str(value).strip()]
        if missing:
            st.error("Completa todos los campos obligatorios.")
        elif not verified:
            st.error("Primero debes probar correctamente esta conexión con GitLab.")
        else:
            st.session_state["project_config"] = save_project_config(values)
            st.session_state["editing_project_config"] = False
            for key in ("issues_by_stage", "last_batch_result", "milestones"):
                st.session_state.pop(key, None)
            st.rerun()
    st.stop()

project_config = saved_config
render_stage_navigation()

st.info("Las métricas e indicadores son valoraciones asistidas basadas en la evidencia disponible. Apoyan la decisión del responsable y no constituyen aprobación automática ni certificación.")

# Sidebar options
with st.sidebar:
    st.image(EMI_LOGO_PATH, use_container_width=True)
    st.markdown("### Sistema Multiagente")
    st.caption("Recepción y seguimiento de requerimientos")
    st.markdown(f"**Proyecto:** {project_config['name']}")
    st.markdown("**GitLab:** 🟢 Conectado")
    st.markdown(f"**Contexto:** {project_config['context_version']}")
    st.divider()
    if st.button("Editar configuración", use_container_width=True):
        st.session_state["editing_project_config"] = True
        st.rerun()
    st.header("Administración")
    if st.button("Limpiar Base de Seguimiento (Caché e Historial)"):
        limpiar_datos_seguimiento()
        st.success("Base de datos limpia.")

try:
    adapter = GitLabAdapter(project_config["gitlab_url"], project_config["gitlab_token"], project_config["gitlab_project"])
except ValueError as e:
    st.error(f"Error de configuración: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"No se pudo conectar a GitLab: {str(e)}")
    st.stop()

project_name = project_config["name"]
stage_id = st.session_state["etapa_actual"]
milestone_val = MILESTONES_BY_STAGE[stage_id]
st.subheader(next(stage[2] for stage in STAGES if stage[0] == stage_id))
st.write(f"**Milestone asociado:** {milestone_val}")

ISSUE_FILTER_VERSION = "pending-or-rework-v1"
if st.session_state.get("issue_filter_version") != ISSUE_FILTER_VERSION:
    st.session_state.pop("issues_by_stage", None)
    st.session_state["issue_filter_version"] = ISSUE_FILTER_VERSION

if "issues_by_stage" not in st.session_state:
    st.session_state.issues_by_stage = {}
refresh_col, analysis_col = st.columns(2)
refresh_issues = refresh_col.button("Actualizar desde GitLab", use_container_width=True)
if refresh_issues or stage_id not in st.session_state.issues_by_stage:
    with st.spinner("Consultando issues del milestone..."):
        st.session_state.issues_by_stage[stage_id] = adapter.listar_issues_pendientes(milestone_title=milestone_val)
issues = st.session_state.issues_by_stage[stage_id]
st.write(f"**Issues encontrados:** {len(issues)}")
if issues:
    with st.expander("Lista de issues", expanded=True):
        for issue in issues:
            st.markdown(f"- **#{issue.iid}** — {issue.title}")
else:
    st.info("No se encontraron issues abiertos en este milestone.")

start_analysis = analysis_col.button("Iniciar análisis", type="primary", use_container_width=True, disabled=not issues)
if start_analysis:
    for stale_key in ("last_batch_result", "batch_pdf", "batch_docx"):
        st.session_state.pop(stale_key, None)
    if not project_name:
        st.warning("Debes ingresar el Nombre del Proyecto.")
        st.stop()
        
    issues_to_process = issues
        
    st.markdown(f"### Milestone {milestone_val}")
    st.write(f"**{len(issues_to_process)} issues encontrados.**")
    
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
                batch_result = procesar_flujo_lote(batch, project_name, sprint_context, adapter=adapter)
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
        construir_filas_trazabilidad, generar_documento_formal_lote_docx,
        generar_reporte_lote_pdf,
    )
    batch_result = st.session_state.last_batch_result
    results = batch_result["issues"]
    summary = batch_result["summary"]
    st.subheader("Resumen global")
    st.write(f"**Milestone:** {st.session_state.last_milestone}")
    a, b, c, d = st.columns(4)
    a.metric("Historias procesadas", summary["procesadas"])
    b.metric("Con error", summary["errores"])
    c.metric("Índice de Calidad de Requerimientos promedio", f"{summary['calidad_promedio'] * 100:.0f} %" if summary["calidad_promedio"] is not None else "N/D")
    d.metric("Índice de Seguridad en Requerimientos promedio", f"{summary['seguridad_promedio'] * 100:.0f} %" if summary["seguridad_promedio"] is not None else "N/D")
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
            st.write(f"**Estado de evaluación asistida:** {result['estado_evaluacion']} · **Índice de Calidad de Requerimientos:** {quality_value} · **Índice de Seguridad en Requerimientos:** {security_value} · **Nivel de aseguramiento recomendado — LoT:** {security.get('lot_recomendado', 'No informado')}")
            st.caption("El LoT no representa la confianza del modelo. La aceptación final requiere revisión humana.")
            st.write(f"**Requerimientos sugeridos:** {len(central['requerimientos'])} · **Correcciones obligatorias:** {len(evaluation.get('correcciones_obligatorias', []))}")
            st.write("**Métricas de calidad:**")
            for metric in (quality.get("metricas") or {}).values():
                if isinstance(metric, dict):
                    st.write(
                        f"{metric.get('codigo', '')} — {metric.get('nombre', '')}: "
                        f"{metric.get('porcentaje') if metric.get('porcentaje') is not None else 'N/D'} % "
                        f"({metric.get('estado_calculo', 'No evaluado')})"
                    )
                    st.caption(metric.get("justificacion", ""))
            st.write("**Métricas de seguridad:**")
            for metric in (security.get("metricas") or {}).values():
                if isinstance(metric, dict):
                    st.write(
                        f"{metric.get('codigo', '')} — {metric.get('nombre', '')}: "
                        f"{metric.get('porcentaje') if metric.get('porcentaje') is not None else 'N/D'} % "
                        f"({metric.get('estado_calculo', 'No evaluado')})"
                    )
                    st.caption(metric.get("justificacion", ""))
            st.write("**Riesgos:**", evaluation.get("riesgos_criticos", []))
            st.write("**Recomendaciones:**", quality.get("recomendaciones", []) + security.get("recomendaciones", []))
            st.write("**Comentario publicado en GitLab:**", "Sí" if result.get("comment_published") else "No")

    st.subheader("Matriz de trazabilidad")
    try:
        rows = construir_filas_trazabilidad(
            results, batch_result.get("generated_at")
        )
        batch_result["traceability_rows"] = rows
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
