import streamlit as st
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_service import procesar_flujo_lote
from database.repository import (
    cargar_estado_etapa,
    guardar_estado_etapa,
    limpiar_datos_seguimiento,
    limpiar_estado_etapas,
)
from project_config import load_project_config, save_project_config
from core.design_ui import render_design_stage
from core.coding_ui import render_coding_stage
from core.testing_ui import render_testing_stage
from core.ui_components import (
    _lista_ui as lista_ui,
    _texto_hallazgo_ui as texto_hallazgo_ui,
    create_stage_step_panels,
    render_findings_section,
    render_gitlab_feedback,
    render_next_phase_button,
    render_state_badge,
)
from core.ui_theme import (
    inject_global_styles,
    render_brand_header,
    render_sidebar_brand,
    render_stage_context,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMI_LOGO_PATH = os.path.join(BASE_DIR, "assets", "emi_logo.png")
TRACEDEV_LOGO_PATH = os.path.join(BASE_DIR, "assets", "tracedev_logo.svg")

st.set_page_config(page_title="TraceDev | Control y Trazabilidad", page_icon="◈", layout="wide")

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
        min-height: 135px;
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
        min-height: 94px;
        padding: 0.8rem 1rem;
        margin: 0.7rem 0 0 0;
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

    /* Streamlit renders form submitters in a separate component, so they
       require their own selectors to retain the institutional palette. */
    div[data-testid="stFormSubmitButton"] > button {
        min-height: 2.85rem;
        border: 2px solid var(--emi-blue) !important;
        border-radius: 7px;
        background: #FFFFFF !important;
        color: var(--emi-blue-dark) !important;
        font-weight: 750;
    }

    div[data-testid="stFormSubmitButton"] > button:hover {
        border-color: var(--emi-yellow) !important;
        background: var(--emi-yellow-soft) !important;
        color: var(--emi-blue-dark) !important;
    }

    div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
        border-color: var(--emi-blue) !important;
        background: var(--emi-blue) !important;
        color: #FFFFFF !important;
        box-shadow: 0 5px 14px rgba(7, 84, 154, 0.2);
    }

    div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
        border-color: var(--emi-yellow) !important;
        background: var(--emi-blue-dark) !important;
        color: var(--emi-yellow) !important;
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
    [data-testid="stSelectbox"] div[data-baseweb="select"] span,
    [data-testid="stSelectbox"] div[data-baseweb="select"] input {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    [data-testid="stTextInput"] input::placeholder {
        color: #66788A !important;
        -webkit-text-fill-color: #66788A !important;
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
        color: var(--emi-ink) !important;
    }

    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] div {
        color: var(--emi-ink) !important;
        -webkit-text-fill-color: var(--emi-ink) !important;
        opacity: 1 !important;
    }

    /* Cargador de archivos integrado con la paleta clara de la aplicaciÃ³n. */
    [data-testid="stFileUploaderDropzone"] {
        background: #F8FBFE !important;
        border: 2px dashed #9BC6E8 !important;
        border-radius: 9px !important;
    }

    [data-testid="stFileUploaderDropzone"] p,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small {
        color: var(--emi-ink) !important;
        -webkit-text-fill-color: var(--emi-ink) !important;
        opacity: 1 !important;
    }

    [data-testid="stFileUploaderDropzone"] button {
        background: #FFFFFF !important;
        border: 1px solid var(--emi-blue) !important;
        color: var(--emi-blue-dark) !important;
        -webkit-text-fill-color: var(--emi-blue-dark) !important;
    }

    /* Las tablas estÃ¡ticas deben conservar contraste dentro de expanders. */
    [data-testid="stTable"] {
        background: #FFFFFF !important;
        color: var(--emi-ink) !important;
    }

    [data-testid="stTable"] table {
        border-collapse: collapse !important;
        background: #FFFFFF !important;
    }

    [data-testid="stTable"] th {
        background: var(--emi-blue-soft) !important;
        border-color: #B8CADB !important;
        color: var(--emi-blue-dark) !important;
        -webkit-text-fill-color: var(--emi-blue-dark) !important;
        font-weight: 750 !important;
    }

    [data-testid="stTable"] td {
        background: #FFFFFF !important;
        border-color: var(--emi-line) !important;
        color: var(--emi-ink) !important;
        -webkit-text-fill-color: var(--emi-ink) !important;
    }

    [data-testid="stTable"] th *,
    [data-testid="stTable"] td * {
        color: inherit !important;
        -webkit-text-fill-color: inherit !important;
        opacity: 1 !important;
    }

    /* ConfirmaciÃ³n previa de DiseÃ±o: texto y control mÃ¡s visibles. */
    .st-key-diseno_matriz_confirmada [data-testid="stCheckbox"] label {
        gap: 0.75rem !important;
        padding: 0.35rem 0 !important;
    }

    .st-key-diseno_matriz_confirmada [data-testid="stCheckbox"] label p {
        color: var(--emi-blue-dark) !important;
        -webkit-text-fill-color: var(--emi-blue-dark) !important;
        font-size: 1.05rem !important;
        font-weight: 750 !important;
        line-height: 1.4 !important;
    }

    .st-key-diseno_matriz_confirmada [data-baseweb="checkbox"] > div:first-child,
    .st-key-diseno_matriz_confirmada [data-testid="stCheckbox"] div[role="checkbox"] {
        width: 1.45rem !important;
        min-width: 1.45rem !important;
        height: 1.45rem !important;
        min-height: 1.45rem !important;
    }

    hr {
        border-color: var(--emi-yellow) !important;
        opacity: 0.7;
    }

    [data-testid="stCaptionContainer"] {
        color: #5B7187;
    }

    /* Mantener visibles las etiquetas de las pestañas sobre el fondo blanco. */
    [data-testid="stTabs"] [data-baseweb="tab"] {
        color: var(--emi-blue-dark) !important;
        -webkit-text-fill-color: var(--emi-blue-dark) !important;
        opacity: 1 !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] p,
    [data-testid="stTabs"] [data-baseweb="tab"] span {
        color: inherit !important;
        -webkit-text-fill-color: inherit !important;
        opacity: 1 !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
        color: var(--emi-blue) !important;
        -webkit-text-fill-color: var(--emi-blue) !important;
        font-weight: 800;
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

    .result-intro {
        padding: 0.85rem 1rem;
        margin: 0.6rem 0 1rem;
        border: 1px solid var(--emi-line);
        border-left: 5px solid var(--emi-blue);
        border-radius: 8px;
        background: #F8FBFE;
    }

    .result-intro strong {
        color: var(--emi-blue-dark);
    }

    .result-section {
        margin: 1rem 0;
        padding: 0.9rem 1rem;
        border: 1px solid var(--emi-line);
        border-radius: 8px;
        background: #FFFFFF;
    }

    .result-section h4 {
        margin-top: 0;
        color: var(--emi-blue-dark);
    }

    .state-badge {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.03em;
    }

    .state-corregir {
        background: #FFF1D6;
        color: #8A5200;
        border: 1px solid #E7B44D;
    }

    .state-conforme {
        background: #E9F7EF;
        color: #176B3A;
        border: 1px solid #8BC9A6;
    }

    .state-mejoras {
        background: #EAF3FB;
        color: #07549A;
        border: 1px solid #9BC6E8;
    }

    .state-revision {
        background: #F1F3F5;
        color: #4E5D6C;
        border: 1px solid #C8D0D8;
    }

    .finding-block {
        padding: 0.75rem 0.9rem;
        margin: 0.55rem 0;
        border-radius: 7px;
        background: #F8FBFE;
        border-left: 4px solid #9CBFD9;
    }

    .finding-correction {
        border-left-color: #D99B26;
        background: #FFFBF2;
    }

    .finding-precision {
        border-left-color: #3787C8;
    }

    .finding-opportunity {
        border-left-color: #7A8A99;
    }

    .metric-detail {
        padding: 0.8rem 1rem;
        border-radius: 8px;
        background: #F8FBFE;
        border: 1px solid #DCE7F0;
        margin-bottom: 0.8rem;
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

# Capa visual TraceDev. Se inyecta después de los estilos heredados para conservar
# compatibilidad con todos los componentes ya existentes en las cuatro etapas.
inject_global_styles()

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
                    width="content",
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
        if st.button("← Volver a Recepción de requerimientos", type="primary", width="stretch"):
            st.session_state["etapa_actual"] = "requerimientos"
            st.rerun()

render_brand_header(EMI_LOGO_PATH, TRACEDEV_LOGO_PATH)

saved_config = load_project_config()
editing_config = st.session_state.get("editing_project_config", False)

if saved_config is None or editing_config:
    st.subheader("Configuración del Proyecto")
    st.caption("Identifica el proyecto y valida la conexión con GitLab para habilitar las etapas.")
    defaults = saved_config or {}
    with st.form("project_configuration"):
        st.markdown("### Identificación")
        cfg_name = st.text_input(
            "Nombre del proyecto *",
            value=defaults.get("name", ""),
            placeholder="Ej.: Sistema de Gestión de Citas Médicas",
        )
        st.divider()
        st.markdown("### Integración con GitLab")
        st.caption("Estos datos se utilizan para consultar los issues y verificar los milestones del flujo.")
        gitlab_col, project_col = st.columns([1.35, 1])
        with gitlab_col:
            gitlab_url = st.text_input("URL del servidor GitLab *", value=defaults.get("gitlab_url", os.getenv("GITLAB_URL", "")))
        with project_col:
            gitlab_project = st.text_input("Proyecto GitLab *", value=defaults.get("gitlab_project", os.getenv("GITLAB_PROJECT_ID", "")), help="ID numérico o ruta namespace/proyecto")
        gitlab_token = st.text_input("Token de acceso *", value=defaults.get("gitlab_token", os.getenv("GITLAB_TOKEN", "")), type="password")

        values = {
            "name": cfg_name, "gitlab_url": gitlab_url,
            "gitlab_project": gitlab_project, "gitlab_token": gitlab_token,
        }
        connection_signature = (gitlab_url.strip(), gitlab_project.strip(), gitlab_token.strip())
        test_col, save_col = st.columns([1, 2])
        test_connection = test_col.form_submit_button("Probar conexión", width="stretch")
        save_and_start = save_col.form_submit_button("Guardar configuración e iniciar proyecto", type="primary", width="stretch")

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
    c1, c2 = st.columns(2)
    c1.metric("GitLab", "Conectado" if verified else "Pendiente")
    c2.metric("Milestones", "Verificados" if verified else "Pendientes")

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
            limpiar_estado_etapas()
            st.rerun()
    st.stop()

project_config = saved_config
render_stage_navigation()

st.info("Las métricas e indicadores son valoraciones asistidas basadas en la evidencia disponible. Apoyan la decisión del responsable y no constituyen aprobación automática ni certificación.")

# Sidebar options
with st.sidebar:
    render_sidebar_brand(TRACEDEV_LOGO_PATH, project_config)
    st.divider()
    if st.button("Editar configuración", width="stretch"):
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
stage_name = next(stage[2] for stage in STAGES if stage[0] == stage_id)
render_stage_context(stage_name, milestone_val)

# Las etapas de Diseño y Codificación tienen su propio bloque, separado del
# de Requerimientos (no comparten nodos ni lógica). Las demás etapas aún no
# implementadas conservan el placeholder existente.
if stage_id == "diseno":
    render_design_stage(project_name, project_config, adapter)
    st.stop()
elif stage_id == "codificacion":
    render_coding_stage(project_name, project_config, adapter)
    st.stop()
elif stage_id == "pruebas":
    render_testing_stage(project_name, project_config, adapter)
    st.stop()
elif stage_id != "requerimientos":
    render_coming_soon(stage_id)
    st.stop()

if "last_batch_result" not in st.session_state:
    persisted_requerimientos = cargar_estado_etapa("requerimientos")
    if persisted_requerimientos:
        st.session_state.last_batch_result = persisted_requerimientos.get("last_batch_result")
        st.session_state.last_project_name = persisted_requerimientos.get("last_project_name")
        st.session_state.last_milestone = persisted_requerimientos.get("last_milestone")

paso_entrada, paso_analisis, paso_resultados, _req_step_key = create_stage_step_panels(
    "req",
    bool(st.session_state.get("last_batch_result", {}).get("issues")),
)

ISSUE_FILTER_VERSION = "pending-or-rework-v1"
if st.session_state.get("issue_filter_version") != ISSUE_FILTER_VERSION:
    st.session_state.pop("issues_by_stage", None)
    st.session_state["issue_filter_version"] = ISSUE_FILTER_VERSION

if "issues_by_stage" not in st.session_state:
    st.session_state.issues_by_stage = {}
refresh_issues = paso_entrada.button("Actualizar desde GitLab", width="stretch")
if refresh_issues or stage_id not in st.session_state.issues_by_stage:
    with paso_entrada.spinner("Consultando issues del milestone..."):
        st.session_state.issues_by_stage[stage_id] = adapter.listar_issues_pendientes(milestone_title=milestone_val)
issues = st.session_state.issues_by_stage[stage_id]
paso_entrada.write(f"**Issues encontrados:** {len(issues)}")
if issues:
    with paso_entrada.expander("Lista de issues", expanded=True):
        for issue in issues:
            st.markdown(f"- **#{issue.iid}** — {issue.title}")
else:
    paso_entrada.info("No se encontraron issues abiertos en este milestone.")

render_next_phase_button(paso_entrada, _req_step_key, 1)

start_analysis = paso_analisis.button("Iniciar análisis", type="primary", width="stretch", disabled=not issues)
if start_analysis:
    for stale_key in ("last_batch_result", "batch_pdf", "batch_docx"):
        st.session_state.pop(stale_key, None)
    if not project_name:
        paso_analisis.warning("Debes ingresar el Nombre del Proyecto.")
        st.stop()
        
    issues_to_process = issues
        
    paso_analisis.markdown(f"### Milestone {milestone_val}")
    paso_analisis.write(f"**{len(issues_to_process)} issues encontrados.**")
    
    # Construir Contexto del Sprint
    sprint_context = f"Proyecto: {project_name}\nSprint: {milestone_val or 'Sin milestone'}\nHistorias a analizar: {len(issues_to_process)}\n"
    sprint_context += "Títulos:\n" + "\n".join([f"- {i.title}" for i in issues_to_process])
    
    status_container = paso_analisis.container()
    metrics_container = paso_analisis.container()
    
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
            global_ph.markdown(f"**Procesando lote {batch_num} de {total_batches} ({len(batch)} historias)**... ⏳\n*(Central → Calidad → Seguridad → Evaluador → Formalización final)*")
            
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
                partial_summary_path = getattr(e, "summary_path", None)
                if partial_summary_path:
                    st.session_state["last_partial_summary_path"] = partial_summary_path
                    st.caption(
                        "Resumen parcial sanitizado: "
                        f"{partial_summary_path}"
                    )
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
            st.session_state.last_project_name = project_name
            st.session_state.last_milestone = milestone_val or "Personalizado"
            guardar_estado_etapa("requerimientos", {
                "last_batch_result": st.session_state.last_batch_result,
                "last_project_name": st.session_state.last_project_name,
                "last_milestone": st.session_state.last_milestone,
            })
        else:
            paso_analisis.info("No se generó un resumen ni documentos porque el lote no produjo resultados consolidados.")
            
    if failed_batches or incomplete_stories:
        paso_analisis.error("El análisis del Sprint terminó con errores.")
    else:
        paso_analisis.success("¡Análisis del Sprint finalizado!")

render_next_phase_button(paso_analisis, _req_step_key, 2)


_texto_hallazgo_ui = texto_hallazgo_ui
_lista_ui = lista_ui


def _porcentaje_ui(value):
    if value is None:
        return "N/D"

    try:
        return f"{float(value) * 100:.0f} %"
    except (TypeError, ValueError):
        return "N/D"


def _porcentaje_metrica_ui(metric):
    value = metric.get("porcentaje")

    if value is None:
        return "N/D"

    try:
        return f"{float(value):.0f} %"
    except (TypeError, ValueError):
        return "N/D"


def _funciones_documentadas_mc01(mc01):
    values = (
        mc01.get("funciones_necesarias_documentadas")
        or mc01.get("funciones_explicitas")
        or mc01.get("funciones_incluidas")
        or []
    )

    result = []

    for item in _lista_ui(values):
        if isinstance(item, dict):
            text = str(
                item.get("funcion")
                or item.get("nombre")
                or item.get("descripcion")
                or ""
            ).strip()
        else:
            text = str(item or "").strip()

        if text:
            result.append(text)

    return result


def _gaps_mc01(mc01):
    gaps = (
        mc01.get("funciones_necesarias_faltantes")
        or []
    )

    return [
        gap
        for gap in gaps
        if isinstance(gap, dict)
    ]


def _explicar_estado_ui(result):
    estado = (
        result.get("estado_orientativo")
        or result.get("estado_evaluacion")
        or "REVISIÓN HUMANA"
    )

    correcciones = _lista_ui(
        result.get("correcciones_necesarias")
    )

    quality = result.get("quality") or {}
    security = result.get("security") or {}

    q = _porcentaje_ui(quality.get("indice"))
    s = _porcentaje_ui(security.get("indice"))

    if estado == "CORREGIR":
        if correcciones:
            return (
                f"El estado es CORREGIR porque se identificaron "
                f"{len(correcciones)} correcciones necesarias. "
                f"La evaluación actual registra Calidad {q} y "
                f"Seguridad {s}."
            )

        return (
            "El estado es CORREGIR porque al menos una de las "
            "métricas evaluadas presenta brechas que requieren revisión."
        )

    if estado == "CONFORME CON MEJORAS":
        return (
            "Las métricas evaluadas cumplen los criterios establecidos, "
            "pero existen precisiones u oportunidades adicionales que "
            "pueden fortalecer la especificación."
        )

    if estado == "CONFORME":
        return (
            "Las métricas evaluadas cumplen los criterios establecidos "
            "y no se identificaron correcciones necesarias."
        )

    return (
        "La evaluación requiere revisión humana debido a evidencia "
        "insuficiente o a condiciones que no pudieron resolverse "
        "automáticamente."
    )


# Resultados y documentos consolidados del último lote
if (
    st.session_state.get("last_batch_result", {}).get("issues")
    and cargar_estado_etapa("requerimientos") is None
):
    # Resultados ya en memoria de una ejecución anterior a esta persistencia: respaldarlos ahora.
    guardar_estado_etapa("requerimientos", {
        "last_batch_result": st.session_state.last_batch_result,
        "last_project_name": st.session_state.get("last_project_name"),
        "last_milestone": st.session_state.get("last_milestone"),
    })

if not st.session_state.get("last_batch_result", {}).get("issues"):
    paso_resultados.info("Ejecuta el análisis para ver resultados.")

if st.session_state.get("last_batch_result", {}).get("issues"):
    paso_resultados.divider()
    from core.utils import (
        construir_filas_trazabilidad, generar_documento_formal_lote_docx,
        generar_reporte_lote_pdf,
    )
    batch_result = st.session_state.last_batch_result
    results = batch_result["issues"]
    summary = batch_result["summary"]

    resumen_general, detalle_resultados, artefactos = paso_resultados.tabs(
        ["Resumen general", "Detalle por historia", "Matriz y documentos"]
    )

    resumen_general.subheader("Resumen global")
    resumen_general.caption(
        f"Milestone: {st.session_state.last_milestone}"
    )

    r1, r2, r3 = resumen_general.columns(3)

    r1.metric(
        "Historias procesadas",
        summary["procesadas"],
    )

    r2.metric(
        "Con error",
        summary["errores"],
    )

    r3.metric(
        "Requieren corrección",
        summary["requieren_correccion"],
    )

    r4, r5, r6 = resumen_general.columns(3)

    r4.metric(
        "Calidad promedio",
        (
            f"{summary['calidad_promedio'] * 100:.0f} %"
            if summary["calidad_promedio"] is not None
            else "N/D"
        ),
    )

    r5.metric(
        "Seguridad promedio",
        (
            f"{summary['seguridad_promedio'] * 100:.0f} %"
            if summary["seguridad_promedio"] is not None
            else "N/D"
        ),
    )

    r6.metric(
        "Requerimientos formalizados propuestos",
        summary["requerimientos"],
    )

    quality_min = (
        f"{summary['calidad_minima'] * 100:.0f} %"
        if summary["calidad_minima"] is not None
        else "N/D"
    )

    security_min = (
        f"{summary['seguridad_minima'] * 100:.0f} %"
        if summary["seguridad_minima"] is not None
        else "N/D"
    )

    resumen_general.caption(
        f"Calidad mínima: {quality_min} · "
        f"Seguridad mínima: {security_min} · "
        f"Información insuficiente: "
        f"{summary['informacion_insuficiente']} · "
        f"Historias bajo meta: {summary['historias_bajo_meta']}"
    )

    detalle_resultados.subheader("Resultados por historia")
    for result in results:
        if result.get("estado_procesamiento") == "informacion_insuficiente":
            detalle_resultados.warning(f"HU-{result['issue_iid']:03d} — Información insuficiente: {', '.join(result['validacion_entrada']['campos_faltantes'])}")
            continue
        if result["status"] != "ok":
            detalle_resultados.error(f"HU-{result['issue_iid']:03d} — {' '.join(result['errors'])}")
            continue

        central = result.get("central") or {}
        quality = result.get("quality") or {}
        security = result.get("security") or {}

        fallback_id = (
            f"HU-{result.get('issue_iid', '???')}"
        )

        historia_id = central.get(
            "historia_id",
            fallback_id,
        )

        titulo = central.get(
            "titulo",
            "Sin título",
        )

        estado = (
            result.get("estado_orientativo")
            or result.get("estado_evaluacion")
            or "REVISIÓN HUMANA"
        )

        expander_title = (
            f"{historia_id} — {titulo} · {estado}"
        )

        with detalle_resultados.expander(
            expander_title,
            expanded=False,
        ):
            actor = str(
                central.get("actor") or "No identificado"
            ).strip()

            objetivo = str(
                central.get("objetivo") or "No identificado"
            ).strip()

            st.markdown(
                f"""
                <div class="result-intro">
                    <strong>Actor:</strong> {actor}<br>
                    <strong>Objetivo:</strong> {objetivo}
                </div>
                """,
                unsafe_allow_html=True,
            )

            requirements = [
                req
                for req in central.get("requerimientos", [])
                if isinstance(req, dict)
            ]

            m1, m2, m3, m4 = st.columns(4)

            m1.metric(
                "Calidad",
                _porcentaje_ui(quality.get("indice")),
            )

            m2.metric(
                "Seguridad",
                _porcentaje_ui(security.get("indice")),
            )

            m3.metric(
                "LoT recomendado",
                security.get("lot_recomendado", "N/D"),
            )

            m4.metric(
                "Requerimientos",
                len(requirements),
            )

            st.info(
                "**¿Por qué este estado?**\n\n"
                + _explicar_estado_ui(result)
            )

            tab_resumen, tab_calidad, tab_seguridad, tab_formalizacion = st.tabs(
                [
                    "Resumen",
                    "Calidad",
                    "Seguridad",
                    "Formalización",
                ]
            )

            with tab_resumen:
                correcciones = _lista_ui(
                    result.get("correcciones_necesarias")
                )

                precisiones = _lista_ui(
                    result.get("precisiones_necesarias")
                )

                oportunidades = _lista_ui(
                    result.get("mejoras_sugeridas")
                    or result.get("oportunidades_adicionales")
                )

                render_findings_section(correcciones, precisiones, oportunidades)

                st.markdown("#### Retroalimentación")
                render_gitlab_feedback(result.get("comment_published", False))

            with tab_calidad:
                quality_metrics = (
                    quality.get("metricas")
                    if isinstance(quality.get("metricas"), dict)
                    else {}
                )

                mc01 = quality_metrics.get("cobertura_funcional") or {}
                mc02 = quality_metrics.get("adecuacion_funcional") or {}

                st.markdown("### MC-01 — Cobertura Funcional")

                mc01_pct = _porcentaje_metrica_ui(mc01)

                documentadas = _funciones_documentadas_mc01(mc01)
                faltantes = _gaps_mc01(mc01)
                total_necesarias = len(documentadas) + len(faltantes)

                st.metric("Resultado MC-01", mc01_pct)

                st.markdown(
                    "**Fórmula aplicada:** "
                    "Funciones necesarias documentadas / "
                    "Total de funciones necesarias identificadas"
                )

                st.markdown(
                    f"**Cálculo:** "
                    f"{len(documentadas)} / {total_necesarias} = {mc01_pct}"
                )

                q1, q2, q3 = st.columns(3)

                q1.metric("Documentadas", len(documentadas))
                q2.metric("Necesarias faltantes", len(faltantes))
                q3.metric("Total necesarias", total_necesarias)

                st.markdown(
                    f"#### Documentadas en la evidencia original "
                    f"({len(documentadas)})"
                )

                if documentadas:
                    for funcion in documentadas:
                        st.markdown(f"- {funcion}")
                else:
                    st.caption("Ninguna.")

                st.markdown(
                    f"#### Funciones necesarias no documentadas "
                    f"({len(faltantes)})"
                )

                if faltantes:
                    for gap in faltantes:
                        funcion = str(
                            gap.get("funcion") or "Función no identificada"
                        ).strip()

                        st.markdown(f"**{funcion}**")

                        evidencia = str(
                            gap.get("evidencia_relacionada") or ""
                        ).strip()

                        motivo = str(
                            gap.get("justificacion_necesidad")
                            or gap.get("motivo_necesidad")
                            or ""
                        ).strip()

                        consecuencia = str(
                            gap.get("consecuencia_ausencia") or ""
                        ).strip()

                        confianza = str(
                            gap.get("confianza") or ""
                        ).strip()

                        if evidencia:
                            st.caption(f"Evidencia relacionada: {evidencia}")

                        if motivo:
                            st.markdown(f"**Motivo de necesidad:** {motivo}")

                        if consecuencia:
                            st.markdown(
                                f"**Consecuencia de la ausencia:** {consecuencia}"
                            )

                        if confianza:
                            st.markdown(
                                f"**Confianza de la inferencia:** "
                                f"{confianza.capitalize()}"
                            )

                        st.divider()
                else:
                    st.success(
                        "No se identificaron funciones "
                        "necesarias faltantes con confianza alta."
                    )

                if faltantes:
                    st.info(
                        f"Si se formalizan las {len(faltantes)} funciones "
                        f"necesarias faltantes identificadas, MC-01 podría "
                        f"alcanzar una cobertura potencial del 100 %."
                    )
                else:
                    st.caption(
                        "La cobertura funcional evaluada ya alcanza el 100 %."
                    )

                st.divider()

                st.markdown("### MC-02 — Adecuación Funcional")

                mc02_pct = _porcentaje_metrica_ui(mc02)

                alineadas = _lista_ui(mc02.get("funciones_alineadas"))
                no_alineadas = _lista_ui(mc02.get("funciones_no_alineadas"))

                objetivo_evaluado = str(
                    mc02.get("objetivo_evaluado")
                    or central.get("objetivo")
                    or ""
                ).strip()

                total_mc02 = len(alineadas) + len(no_alineadas)

                st.metric("Resultado MC-02", mc02_pct)

                st.markdown(
                    "**Fórmula aplicada:** "
                    "Funciones alineadas / "
                    "Funciones documentadas evaluables"
                )

                st.markdown(
                    f"**Cálculo:** "
                    f"{len(alineadas)} / {total_mc02} = {mc02_pct}"
                )

                if objetivo_evaluado:
                    st.markdown(f"**Objetivo evaluado:** {objetivo_evaluado}")

                st.markdown(f"#### Funciones alineadas ({len(alineadas)})")

                if alineadas:
                    for value in alineadas:
                        st.markdown(f"- {value}")
                else:
                    st.caption("Ninguna.")

                st.markdown(
                    f"#### Funciones no alineadas ({len(no_alineadas)})"
                )

                if no_alineadas:
                    for value in no_alineadas:
                        st.markdown(f"- {value}")
                else:
                    st.caption("Ninguna.")

            with tab_seguridad:
                security_metrics = (
                    security.get("metricas")
                    if isinstance(security.get("metricas"), dict)
                    else {}
                )

                ms01 = security_metrics.get("cobertura_seguridad") or {}
                ms02 = security_metrics.get("clasificacion_datos") or {}

                st.markdown("### MS-01 — Cobertura de Seguridad")

                st.metric(
                    "Resultado MS-01",
                    _porcentaje_metrica_ui(ms01),
                )

                aplicables = _lista_ui(ms01.get("aspectos_aplicables"))
                documentados_seg = _lista_ui(ms01.get("aspectos_documentados"))
                faltantes_seg = _lista_ui(ms01.get("aspectos_faltantes"))

                s1, s2, s3 = st.columns(3)

                s1.metric("Aplicables", len(aplicables))
                s2.metric("Documentados", len(documentados_seg))
                s3.metric("Pendientes", len(faltantes_seg))

                st.markdown("#### Aspectos documentados")

                if documentados_seg:
                    for value in documentados_seg:
                        st.markdown(f"- {value}")
                else:
                    st.caption("Ninguno.")

                st.markdown("#### Aspectos pendientes")

                if faltantes_seg:
                    for value in faltantes_seg:
                        st.markdown(f"- {value}")
                else:
                    st.success(
                        "No existen aspectos aplicables pendientes."
                    )

                st.divider()

                st.markdown("### MS-02 — Clasificación de Datos")

                st.metric(
                    "Resultado MS-02",
                    _porcentaje_metrica_ui(ms02),
                )

                identificados = _lista_ui(ms02.get("datos_identificados"))
                clasificados = _lista_ui(ms02.get("datos_clasificados"))
                sin_clasificacion = _lista_ui(
                    ms02.get("datos_sin_clasificacion")
                )

                d1, d2, d3 = st.columns(3)

                d1.metric("Identificados", len(identificados))
                d2.metric("Clasificados", len(clasificados))
                d3.metric("Pendientes", len(sin_clasificacion))

                st.markdown("#### Datos identificados")

                if identificados:
                    for value in identificados:
                        st.markdown(
                            f"- {_texto_hallazgo_ui(value) or value}"
                        )
                else:
                    st.caption("Ninguno.")

                st.markdown("#### Pendientes de clasificación")

                if sin_clasificacion:
                    for value in sin_clasificacion:
                        st.markdown(
                            f"- {_texto_hallazgo_ui(value) or value}"
                        )
                else:
                    st.success(
                        "No existen datos identificados "
                        "pendientes de clasificación."
                    )

                st.divider()

                lot = security.get("lot_recomendado", "No informado")

                st.info(
                    f"**Nivel de aseguramiento recomendado: {lot}**\n\n"
                    "El LoT representa el nivel de aseguramiento "
                    "recomendado según la evidencia de seguridad "
                    "disponible. No representa la confianza del "
                    "modelo ni constituye una certificación."
                )

            with tab_formalizacion:
                st.caption(
                    "Los siguientes requerimientos corresponden "
                    "a la formalización propuesta por el modelo "
                    "y requieren validación del responsable."
                )

                if not requirements:
                    st.info(
                        "No se generaron requerimientos formalizados."
                    )

                for req in requirements:
                    code = str(
                        req.get("codigo")
                        or req.get("id")
                        or req.get("temp_id")
                        or ""
                    ).strip()

                    name = str(
                        req.get("nombre") or "Requerimiento"
                    ).strip()

                    with st.expander(
                        f"{code} — {name}",
                        expanded=False,
                    ):
                        st.markdown(
                            str(
                                req.get("descripcion_formal") or ""
                            )
                        )

                        tipo = req.get("tipo", "No definido")

                        prioridad_original = str(
                            req.get("prioridad_original")
                            or req.get("prioridad")
                            or ""
                        ).strip()

                        prioridad_sugerida = str(
                            req.get("prioridad_sugerida") or ""
                        ).strip()

                        if prioridad_sugerida:
                            prioridad_visible = (
                                f"{prioridad_sugerida} "
                                "(sugerida, pendiente de validación)"
                            )
                        elif prioridad_original:
                            prioridad_visible = prioridad_original
                        else:
                            prioridad_visible = "Pendiente de definición"

                        st.markdown(f"**Tipo:** {tipo}")
                        st.markdown(f"**Prioridad:** {prioridad_visible}")

                        origen_tipo = str(
                            req.get("origen_tipo") or ""
                        ).strip()

                        procedencia = str(
                            req.get("procedencia") or ""
                        ).strip()

                        if procedencia or origen_tipo:
                            st.caption(
                                f"Procedencia: "
                                f"{procedencia or 'No indicada'}"
                                + (
                                    f" · {origen_tipo}"
                                    if origen_tipo
                                    else ""
                                )
                            )

                        pendientes_req = _lista_ui(
                            req.get("pendientes_definicion")
                        )

                        if pendientes_req:
                            st.warning(
                                "Este requerimiento tiene "
                                "aspectos pendientes de definición."
                            )

                            for pending in pendientes_req:
                                text = _texto_hallazgo_ui(pending)
                                if text:
                                    st.markdown(f"- {text}")

    with artefactos.expander(
        "Matriz de trazabilidad",
        expanded=False,
    ):
        try:
            rows = construir_filas_trazabilidad(
                results,
                batch_result.get("generated_at"),
            )

            batch_result["traceability_rows"] = rows

            if not rows:
                raise ValueError(
                    "No fue posible construir la matriz "
                    "porque no existen requerimientos "
                    "formalizados."
                )

            import pandas as pd

            df = pd.DataFrame(rows)

            columnas_preferidas = [
                "Código",
                "Nombre",
                "Tipo",
                "Historia de origen",
                "Estado de revisión",
            ]

            columnas_disponibles = [
                col
                for col in columnas_preferidas
                if col in df.columns
            ]

            st.dataframe(
                (
                    df[columnas_disponibles]
                    if columnas_disponibles
                    else df
                ),
                width="stretch",
                hide_index=True,
            )

            import csv
            import io

            csv_buffer = io.StringIO(newline="")

            writer = csv.DictWriter(
                csv_buffer,
                fieldnames=rows[0].keys(),
                delimiter=";",
                quoting=csv.QUOTE_MINIMAL,
            )

            writer.writeheader()
            writer.writerows(rows)

            st.download_button(
                "Descargar matriz CSV",
                csv_buffer.getvalue().encode("utf-8-sig"),
                "matriz_trazabilidad.csv",
                "text/csv",
            )

        except ValueError as exc:
            st.error(str(exc))

    artefactos.subheader("Documentos consolidados")

    col_pdf, col_docx = artefactos.columns(2)

    with col_pdf:
        st.markdown("### Reporte Ejecutivo")
        st.caption(
            "Presenta métricas, hallazgos, brechas, "
            "precisiones y oportunidades del análisis."
        )

        if st.button(
            "Generar Reporte Ejecutivo",
            width="stretch",
            key="generate_batch_pdf",
        ):
            st.session_state.batch_pdf = (
                generar_reporte_lote_pdf(
                    batch_result
                ).getvalue()
            )

        if st.session_state.get("batch_pdf"):
            st.download_button(
                "Descargar Reporte PDF",
                st.session_state.batch_pdf,
                "Reporte_Ejecutivo_Lote.pdf",
                "application/pdf",
                width="stretch",
            )

    with col_docx:
        st.markdown("### Documento Formal")
        st.caption(
            "Consolida requerimientos formalizados, "
            "trazabilidad, prioridades y aspectos "
            "pendientes de revisión."
        )

        if st.button(
            "Generar Documento Formal",
            width="stretch",
            key="generate_batch_docx",
        ):
            st.session_state.batch_docx = (
                generar_documento_formal_lote_docx(
                    batch_result
                ).getvalue()
            )

        if st.session_state.get("batch_docx"):
            st.download_button(
                "Descargar Documento DOCX",
                st.session_state.batch_docx,
                "Requerimientos_Consolidados.docx",
                (
                    "application/vnd.openxmlformats-"
                    "officedocument.wordprocessingml.document"
                ),
                width="stretch",
            )
