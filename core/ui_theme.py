"""Identidad y sistema visual compartido de la interfaz Streamlit.

Este módulo solo contiene presentación. No modifica el contenido, las métricas
ni el comportamiento del flujo multiagente.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import streamlit as st


# Único rol existente hoy en la herramienta; se muestra bajo el nombre de la sesión.
SESSION_ROLE = "Encargado de DNTIC"


def _data_uri(path: str | Path, mime_type: str) -> str:
    payload = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{payload}"


def inject_global_styles() -> None:
    """Aplica la capa visual TraceDev sobre los componentes nativos de Streamlit."""
    st.markdown(
        """
        <style>
        :root {
            --emi-blue: #07549A;
            --emi-blue-dark: #063A6B;
            --emi-blue-deep: #052F56;
            --emi-blue-soft: #EAF3FB;
            --emi-yellow: #F2C300;
            --emi-yellow-soft: #FFF8D6;
            --nexo-canvas: #F4F7FA;
            --nexo-surface: #FFFFFF;
            --nexo-surface-muted: #F8FAFC;
            --nexo-ink: #17324D;
            --nexo-muted: #60758A;
            --nexo-line: #DCE5ED;
            --nexo-line-strong: #C8D6E2;
            --nexo-radius-sm: 10px;
            --nexo-radius: 16px;
            --nexo-radius-lg: 22px;
            --nexo-shadow-sm: 0 3px 12px rgba(5, 47, 86, .055);
            --nexo-shadow: 0 12px 34px rgba(5, 47, 86, .085);
            --nexo-focus: 0 0 0 3px rgba(7, 84, 154, .16);
        }

        html { scroll-behavior: smooth; }

        body,
        .stApp,
        [data-testid="stAppViewContainer"] {
            background: var(--nexo-canvas) !important;
            color: var(--nexo-ink) !important;
            font-family: Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }

        [data-testid="stHeader"] {
            height: 3.15rem;
            background: rgba(244, 247, 250, .92) !important;
            border-bottom: 1px solid rgba(200, 214, 226, .72) !important;
            backdrop-filter: blur(12px);
        }

        [data-testid="stAppViewContainer"] > .main .block-container,
        [data-testid="stMainBlockContainer"] {
            max-width: 1320px !important;
            width: 100% !important;
            padding: 1.55rem clamp(1rem, 2.25vw, 1.8rem) 5rem !important;
            transition: padding .24s ease, width .24s ease !important;
        }

        [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"] {
            gap: .92rem;
        }

        p, li { line-height: 1.62; }

        h1, h2, h3, h4 {
            color: var(--emi-blue-dark) !important;
            letter-spacing: -.025em !important;
        }

        h2, h3 {
            border: 0 !important;
            padding-bottom: 0 !important;
        }

        [data-testid="stMarkdownContainer"] h2 {
            margin: 2.2rem 0 .8rem !important;
            font-size: clamp(1.42rem, 2vw, 1.78rem) !important;
            font-weight: 780 !important;
        }

        [data-testid="stMarkdownContainer"] h3 {
            position: relative;
            margin: 1.1rem 0 .6rem !important;
            padding-left: .85rem !important;
            font-size: clamp(1.08rem, 1.5vw, 1.28rem) !important;
            font-weight: 760 !important;
        }

        [data-testid="stMarkdownContainer"] h3::before {
            content: "";
            position: absolute;
            top: .18rem;
            bottom: .16rem;
            left: 0;
            width: 4px;
            border-radius: 10px;
            background: var(--emi-yellow);
        }

        [data-testid="stMarkdownContainer"] h4 {
            margin: 1.35rem 0 .55rem !important;
            font-size: 1rem !important;
            font-weight: 760 !important;
        }

        /* Encabezado institucional + producto.
           Vive en la barra superior (header) de Streamlit, a la izquierda de
           Deploy / menú. Es position: fixed y queda por debajo del header
           nativo, que se vuelve transparente: así Deploy, el menú y el botón
           del sidebar siguen siendo clicables. Solo presentación. */
        :root {
            --nexo-header-h: 5.3rem;
            --nexo-sidebar-w: 292px;
            --nexo-toolbar-w: 13.4rem; /* Deploy + menú + indicador Running/Stop */
        }

        .stApp:has(.nexo-hero) [data-testid="stHeader"] {
            height: var(--nexo-header-h);
            border-bottom: 0 !important;
            background: transparent !important;
            backdrop-filter: none !important;
            pointer-events: none;
        }

        .stApp:has(.nexo-hero) [data-testid="stToolbar"] {
            height: 100%;
        }

        .stApp:has(.nexo-hero) [data-testid="stHeader"] button,
        .stApp:has(.nexo-hero) [data-testid="stHeader"] a,
        .stApp:has(.nexo-hero) [data-testid="stStatusWidget"] {
            pointer-events: auto;
        }

        /* Controles nativos sobre el fondo azul del banner */
        .stApp:has(.nexo-hero) [data-testid="stHeader"] button,
        .stApp:has(.nexo-hero) [data-testid="stHeader"] button *,
        .stApp:has(.nexo-hero) [data-testid="stStatusWidget"],
        .stApp:has(.nexo-hero) [data-testid="stStatusWidget"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        .stApp:has(.nexo-hero) [data-testid="stHeader"] button:hover {
            background: rgba(255,255,255,.14) !important;
        }

        /* El banner sale del flujo: se anula el hueco que dejaba su contenedor
           y el contenido arranca justo debajo del header. */
        .stApp:has(.nexo-hero) [data-testid="stElementContainer"]:has(.nexo-hero) {
            height: 0 !important;
            min-height: 0 !important;
            margin-bottom: -.92rem !important;
            overflow: visible !important;
        }

        .stApp:has(.nexo-hero) [data-testid="stMainBlockContainer"] {
            padding-top: calc(var(--nexo-header-h) + 1.3rem) !important;
        }

        .nexo-hero {
            position: fixed;
            top: 0;
            left: var(--nexo-sidebar-w);
            right: 0;
            z-index: 999989;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            gap: clamp(.75rem, 1.3vw, 1.25rem);
            height: var(--nexo-header-h);
            margin: 0;
            padding: .5rem var(--nexo-toolbar-w) .5rem clamp(1rem, 2vw, 1.75rem);
            overflow: hidden;
            border-bottom: 1px solid rgba(255,255,255,.16);
            background:
                radial-gradient(circle at 92% 8%, rgba(242,195,0,.19), transparent 24%),
                linear-gradient(118deg, var(--emi-blue-deep), var(--emi-blue) 72%, #0A63AE);
            box-shadow: 0 6px 22px rgba(5, 47, 86, .16);
            transition: left .26s ease;
        }

        /* Con el sidebar cerrado el banner arranca donde termina el riel de
           íconos (todo el ancho en pantallas angostas) y deja libre, a la
           izquierda, el botón nativo que vuelve a abrir el menú. */
        .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .nexo-hero {
            left: var(--nexo-collapsed-w, 0px);
            padding-left: 3.6rem;
        }

        /* Sesión activa: nombre y rol de quien inició sesión, junto al logo de
           TraceDev en el header. Solo presentación (no altera st.login/st.logout). */
        .nexo-session-badge {
            display: inline-flex;
            grid-area: session;
            align-items: center;
            justify-self: start;
            gap: .6rem;
            min-width: 0;
            max-width: 100%;
            padding: .3rem .95rem .3rem .4rem;
            border: 1px solid rgba(255,255,255,.32);
            border-radius: 14px;
            background: rgba(6, 58, 107, .4);
            backdrop-filter: blur(8px);
        }

        .nexo-session-avatar {
            display: inline-grid;
            flex: 0 0 auto;
            place-items: center;
            width: 1.9rem;
            height: 1.9rem;
            border-radius: 50%;
            background: var(--emi-yellow);
            color: var(--emi-blue-deep);
            font-size: .8rem;
            font-weight: 820;
        }

        .nexo-session-text {
            display: flex;
            flex-direction: column;
            min-width: 0;
            line-height: 1.25;
        }

        .nexo-session-name,
        .nexo-session-role {
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }

        .nexo-session-name {
            color: #FFFFFF;
            font-size: .78rem;
            font-weight: 700;
        }

        .nexo-session-role {
            color: var(--emi-yellow);
            font-size: .68rem;
            font-weight: 600;
        }

        .nexo-entity {
            display: flex;
            flex: 0 0 auto;
            align-items: center;
            justify-content: center;
            height: 100%;
            padding: .3rem .7rem;
            border: 1px solid rgba(255,255,255,.8);
            border-radius: 12px;
            background: rgba(255,255,255,.97);
        }

        .nexo-entity img {
            display: block;
            width: auto;
            max-width: 170px;
            height: 100%;
            object-fit: contain;
        }

        .nexo-hero-divider {
            flex: 0 0 auto;
            width: 1px;
            height: 2.9rem;
            background: linear-gradient(transparent, rgba(255,255,255,.48), transparent);
        }

        .nexo-product {
            display: grid;
            flex: 0 6 auto;
            grid-template-columns: auto minmax(0, 1fr);
            grid-template-areas:
                "kicker kicker"
                "logo   session";
            align-items: center;
            column-gap: 1rem;
            row-gap: .22rem;
            min-width: 0;
        }

        .nexo-product-kicker {
            display: inline-flex;
            grid-area: kicker;
            align-items: center;
            gap: .5rem;
            color: var(--emi-yellow);
            font-size: .62rem;
            font-weight: 800;
            letter-spacing: .15em;
            line-height: 1.2;
            text-transform: uppercase;
        }

        .nexo-product-kicker::before {
            content: "";
            width: 1.5rem;
            height: 2px;
            border-radius: 2px;
            background: currentColor;
        }

        .nexo-product img {
            display: block;
            grid-area: logo;
            width: auto;
            max-width: 100%;
            height: 3rem;
            object-fit: contain;
            object-position: left center;
        }

        /* Navegación por etapas */
        .st-key-stage_shell {
            max-width: none !important;
            margin: .7rem 0 1.05rem !important;
            padding: 1rem 1.1rem .82rem !important;
            overflow: hidden;
            border: 1px solid var(--nexo-line) !important;
            border-radius: var(--nexo-radius) !important;
            background: var(--nexo-surface) !important;
            box-shadow: var(--nexo-shadow-sm);
        }

        .st-key-stage_shell [data-testid="stHorizontalBlock"] {
            gap: .75rem !important;
        }

        .stage-track {
            top: 2.55rem !important;
            left: 9% !important;
            right: 9% !important;
            height: 2px !important;
            background: linear-gradient(90deg, var(--emi-blue-soft), #B8D3E8, var(--emi-blue-soft)) !important;
        }

        [class*="st-key-stage_nav_"] { width: 100%; }

        .st-key-stage_shell [class*="st-key-stage_nav_"] button {
            width: 3.05rem !important;
            min-width: 3.05rem !important;
            height: 3.05rem !important;
            min-height: 3.05rem !important;
            padding: 0 !important;
            border: 1px solid #C5D8E8 !important;
            border-radius: 13px !important;
            background: #F7FAFD !important;
            color: var(--emi-blue) !important;
            -webkit-text-fill-color: var(--emi-blue) !important;
            text-shadow: none !important;
            box-shadow: 0 0 0 5px #FFFFFF, 0 5px 13px rgba(7,84,154,.10) !important;
            transform: rotate(0deg);
        }

        .st-key-stage_shell [class*="st-key-stage_nav_"] button p {
            color: inherit !important;
            -webkit-text-fill-color: inherit !important;
            font-size: 1.08rem !important;
        }

        .st-key-stage_shell [class*="st-key-stage_nav_"] button::after {
            right: -.3rem !important;
            bottom: -.3rem !important;
            width: 1.18rem !important;
            height: 1.18rem !important;
            border: 2px solid #FFFFFF !important;
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
            font-size: .62rem !important;
        }

        .st-key-stage_shell [class*="st-key-stage_nav_"] button:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
            -webkit-text-fill-color: var(--emi-blue-dark) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 0 0 5px #FFFFFF, 0 8px 18px rgba(7,84,154,.16) !important;
        }

        .st-key-stage_shell [class*="st-key-stage_nav_"][class*="_active"] button {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue) !important;
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
            box-shadow: 0 0 0 5px #D7E9F7, 0 8px 18px rgba(7,84,154,.2) !important;
        }

        .st-key-stage_shell [class*="st-key-stage_nav_"][class*="_active"] button::after {
            background: var(--emi-yellow) !important;
        }

        .stage-label {
            min-height: auto !important;
            margin-top: .48rem !important;
            color: #71869A !important;
            font-size: .78rem !important;
            font-weight: 680 !important;
        }

        .stage-label.active { color: var(--emi-blue-dark) !important; font-weight: 800 !important; }

        .stage-status {
            display: block !important;
            width: max-content;
            margin: .65rem auto 0;
            padding: .28rem .7rem;
            border-radius: 999px;
            background: var(--emi-blue-soft);
            color: var(--emi-blue-dark);
            font-size: .73rem;
            font-weight: 720;
        }

        /* Cabecera contextual de la etapa */
        .stage-context-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.25rem;
            margin: .25rem 0 .35rem;
            padding: 1.15rem 1.25rem;
            border: 1px solid var(--nexo-line);
            border-left: 5px solid var(--emi-yellow);
            border-radius: var(--nexo-radius);
            background: var(--nexo-surface);
            box-shadow: var(--nexo-shadow-sm);
        }

        .stage-context-copy > span {
            color: var(--nexo-muted);
            font-size: .7rem;
            font-weight: 800;
            letter-spacing: .13em;
            text-transform: uppercase;
        }

        .stage-context-copy h2 {
            margin: .18rem 0 0 !important;
            color: var(--emi-blue-dark) !important;
            font-size: clamp(1.35rem, 2vw, 1.72rem) !important;
            line-height: 1.2;
        }

        .milestone-chip {
            flex: 0 0 auto;
            min-width: 210px;
            padding: .68rem .85rem;
            border: 1px solid #D3E4F1;
            border-radius: 12px;
            background: var(--emi-blue-soft);
        }

        .milestone-chip small {
            display: block;
            margin-bottom: .13rem;
            color: var(--nexo-muted);
            font-size: .67rem;
            font-weight: 750;
            letter-spacing: .06em;
            text-transform: uppercase;
        }

        .milestone-chip strong { color: var(--emi-blue-dark); font-size: .88rem; }

        /* Título de área principal (Evaluación por etapas, Fases de la etapa, ...):
           icono institucional + rótulo con acento amarillo + nombre + línea suave. */
        .nexo-area-title {
            display: flex;
            align-items: center;
            gap: .9rem;
            margin: .7rem 0 .1rem;
        }

        .nexo-area-title-mark {
            display: grid;
            flex: 0 0 auto;
            place-items: center;
            width: 2.55rem;
            height: 2.55rem;
            border-radius: 13px;
            background: linear-gradient(135deg, var(--emi-blue-deep), var(--emi-blue));
            color: var(--emi-yellow);
            box-shadow: 0 7px 16px rgba(7, 84, 154, .22), inset 0 0 0 1px rgba(255,255,255,.14);
        }

        .nexo-area-title-mark svg { width: 1.3rem; height: 1.3rem; }

        .nexo-area-title-copy { min-width: 0; }

        .nexo-area-title-eyebrow {
            display: flex;
            align-items: center;
            gap: .5rem;
            color: var(--emi-blue);
            font-size: .68rem;
            font-weight: 800;
            letter-spacing: .15em;
            line-height: 1.2;
            text-transform: uppercase;
        }

        .nexo-area-title-eyebrow::before {
            content: "";
            width: 1.4rem;
            height: 2px;
            border-radius: 2px;
            background: var(--emi-yellow);
        }

        .nexo-area-title-name {
            margin: .12rem 0 0;
            color: var(--emi-blue-dark);
            font-size: clamp(1.28rem, 1.9vw, 1.6rem);
            font-weight: 800;
            letter-spacing: -.025em;
            line-height: 1.15;
        }

        .nexo-area-title-desc {
            margin: .22rem 0 0;
            color: var(--nexo-muted) !important;
            font-size: .84rem;
            line-height: 1.4;
        }

        .nexo-area-title-rule {
            flex: 1 1 auto;
            min-width: 1.5rem;
            height: 2px;
            border-radius: 2px;
            background: linear-gradient(90deg, var(--nexo-line-strong), rgba(200, 214, 226, 0));
        }

        /* Subtítulo de una acción dentro de un área (p. ej. «Seleccionar etapa»),
           con el mismo acento amarillo de los títulos de sección. */
        .nexo-subarea-title {
            position: relative;
            margin: .6rem 0 0;
            padding-left: .85rem;
            color: var(--emi-blue-dark);
            font-size: 1.05rem;
            font-weight: 780;
            letter-spacing: -.015em;
            line-height: 1.3;
        }

        .nexo-subarea-title::before {
            content: "";
            position: absolute;
            top: .12rem;
            bottom: .1rem;
            left: 0;
            width: 4px;
            border-radius: 10px;
            background: var(--emi-yellow);
        }

        /* Zona de configuración del proyecto: agrupa título, formulario y
           estado en un único bloque de ancho legible y centrado. */
        .st-key-config_workspace {
            max-width: 960px !important;
            margin: 0 auto !important;
        }

        .st-key-dashboard_title {
            margin-bottom: .8rem !important;
        }

        .st-key-config_status_panel {
            margin-top: .3rem !important;
            padding: 1.1rem 1.25rem 1.25rem !important;
            border: 1px solid var(--nexo-line) !important;
            border-radius: var(--nexo-radius-lg) !important;
            background: var(--nexo-surface) !important;
            box-shadow: var(--nexo-shadow-sm) !important;
        }

        .st-key-config_status_panel [data-testid="stMarkdownContainer"] h3 {
            margin-top: 0 !important;
        }

        /* Formularios y entradas */
        div[data-testid="stForm"] {
            padding: 1.35rem !important;
            border: 1px solid var(--nexo-line) !important;
            border-radius: var(--nexo-radius-lg) !important;
            background: var(--nexo-surface) !important;
            box-shadow: var(--nexo-shadow-sm) !important;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-baseweb="select"] > div {
            min-height: 2.85rem !important;
            border: 1px solid var(--nexo-line-strong) !important;
            border-radius: 11px !important;
            background: #FFFFFF !important;
            transition: border-color .18s ease, box-shadow .18s ease !important;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus,
        [data-baseweb="select"] > div:focus-within {
            border-color: var(--emi-blue) !important;
            box-shadow: var(--nexo-focus) !important;
        }

        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span {
            color: var(--nexo-ink) !important;
            font-size: .87rem !important;
            font-weight: 680 !important;
        }

        /* Botones */
        .stButton > button,
        .stDownloadButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 2.75rem !important;
            border: 1px solid #AFC7DA !important;
            border-radius: 11px !important;
            background: #FFFFFF !important;
            color: var(--emi-blue-dark) !important;
            font-size: .88rem !important;
            font-weight: 740 !important;
            box-shadow: 0 2px 7px rgba(5,47,86,.05) !important;
            transition: transform .16s ease, box-shadow .16s ease, background .16s ease !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 15px rgba(5,47,86,.1) !important;
        }

        /* Botón de enlace (p. ej. «Editar en GitLab»): mismo aspecto que los demás */
        [data-testid="stBaseLinkButton-secondary"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            gap: .4rem;
            min-height: 2.75rem !important;
            border: 1px solid #AFC7DA !important;
            border-radius: 11px !important;
            background: #FFFFFF !important;
            color: var(--emi-blue-dark) !important;
            font-size: .88rem !important;
            font-weight: 740 !important;
            text-decoration: none !important;
            box-shadow: 0 2px 7px rgba(5,47,86,.05) !important;
            transition: transform .16s ease, box-shadow .16s ease, background .16s ease !important;
        }

        [data-testid="stBaseLinkButton-secondary"] *,
        [data-testid="stBaseLinkButton-secondary"] p {
            color: inherit !important;
            font-weight: 400 !important;
        }

        [data-testid="stBaseLinkButton-secondary"]:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 15px rgba(5,47,86,.1) !important;
        }

        .stButton > button:focus-visible,
        .stDownloadButton > button:focus-visible,
        div[data-testid="stFormSubmitButton"] > button:focus-visible {
            outline: none !important;
            box-shadow: var(--nexo-focus) !important;
        }

        .stButton > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
            border-color: var(--emi-blue) !important;
            background: linear-gradient(135deg, var(--emi-blue), #0A67B5) !important;
            color: #FFFFFF !important;
            box-shadow: 0 7px 18px rgba(7,84,154,.18) !important;
        }

        .stButton > button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
            border-color: var(--emi-blue-dark) !important;
            background: var(--emi-blue-dark) !important;
            color: #FFFFFF !important;
        }

        button:disabled { opacity: .55 !important; transform: none !important; box-shadow: none !important; }

        /* Botón "Siguiente fase": discreto, al cierre de cada sección */
        [class*="st-key-next_phase__"] button {
            min-height: 2.15rem !important;
            padding: .3rem .8rem !important;
            border: 1px solid var(--nexo-line) !important;
            border-radius: 999px !important;
            background: var(--nexo-surface-muted) !important;
            color: var(--nexo-muted) !important;
            font-size: .76rem !important;
            font-weight: 640 !important;
            box-shadow: none !important;
        }

        [class*="st-key-next_phase__"] button:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
            transform: none !important;
            box-shadow: none !important;
        }

        /* Métricas */
        div[data-testid="stMetric"] {
            min-height: 104px !important;
            margin: .2rem 0 0 !important;
            padding: .95rem 1rem .86rem !important;
            overflow: hidden;
            border: 1px solid var(--nexo-line) !important;
            border-top: 1px solid var(--nexo-line) !important;
            border-radius: 14px !important;
            background: linear-gradient(145deg, #FFFFFF, #F8FBFD) !important;
            box-shadow: var(--nexo-shadow-sm) !important;
            position: relative;
        }

        div[data-testid="stMetric"]::before {
            content: "";
            position: absolute;
            top: 0;
            bottom: 0;
            left: 0;
            width: 4px;
            background: linear-gradient(var(--emi-yellow), #F7D94D);
        }

        [data-testid="stMetricLabel"] {
            color: var(--nexo-muted) !important;
            font-size: .77rem !important;
            font-weight: 700 !important;
            letter-spacing: .015em;
        }

        [data-testid="stMetricValue"] {
            color: var(--emi-blue-dark) !important;
            font-size: clamp(1.35rem, 2vw, 1.75rem) !important;
            font-weight: 820 !important;
        }

        /* Alertas */
        div[data-testid="stAlert"] {
            margin: .15rem 0 !important;
            padding: .8rem .95rem !important;
            border: 1px solid #C9DAE7 !important;
            border-left: 4px solid var(--emi-blue) !important;
            border-radius: 12px !important;
            background: #F2F7FB !important;
            box-shadow: none !important;
        }

        div[data-testid="stAlert"] p { font-size: .88rem !important; line-height: 1.55 !important; }

        /* Expanders: resultado resumido primero, detalle bajo demanda */
        div[data-testid="stExpander"] {
            margin: .55rem 0 !important;
            overflow: hidden !important;
            border: 1px solid var(--nexo-line) !important;
            border-radius: 14px !important;
            background: var(--nexo-surface) !important;
            box-shadow: var(--nexo-shadow-sm) !important;
            transition: border-color .18s ease, box-shadow .18s ease !important;
        }

        div[data-testid="stExpander"]:hover {
            border-color: #B9CFE0 !important;
            box-shadow: 0 8px 22px rgba(5,47,86,.075) !important;
        }

        div[data-testid="stExpander"] details summary {
            min-height: 3.3rem;
            padding: .2rem .3rem !important;
            background: linear-gradient(90deg, #F6F9FC, #FFFFFF) !important;
            color: var(--emi-blue-dark) !important;
            font-size: .92rem !important;
            font-weight: 730 !important;
        }

        div[data-testid="stExpander"] details[open] > summary {
            border-bottom: 1px solid var(--nexo-line);
            background: var(--emi-blue-soft) !important;
        }

        div[data-testid="stExpander"] details > div {
            padding: .45rem .85rem .9rem !important;
        }

        /* Fases de la etapa: barra de botones «Ver / Ocultar» y panel visible.
           Todos los paneles se generan siempre (la lógica de la etapa no
           cambia); los ocultos solo llevan display:none (clase phase_off_*). */
        [class*="st-key-phase_bar_"] {
            margin: .55rem 0 1rem;
            padding: .5rem;
            border: 1px solid var(--nexo-line);
            border-radius: 16px;
            background: #F1F5F8;
        }

        [class*="st-key-phase_bar_"] [data-testid="stHorizontalBlock"] {
            gap: .5rem !important;
        }

        [class*="st-key-phase_bar_"] button {
            min-height: 2.8rem;
            border: 1px solid var(--nexo-line-strong) !important;
            border-radius: 12px !important;
            background: #FFFFFF !important;
            box-shadow: none !important;
            transition: background .15s ease, border-color .15s ease, box-shadow .15s ease;
        }

        [class*="st-key-phase_bar_"] button,
        [class*="st-key-phase_bar_"] button * {
            color: var(--emi-blue-dark) !important;
            -webkit-text-fill-color: var(--emi-blue-dark) !important;
            font-weight: 740 !important;
        }

        [class*="st-key-phase_bar_"] button:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
        }

        [class*="st-key-phase_bar_"] button[data-testid="stBaseButton-primary"] {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue) !important;
            box-shadow: 0 6px 16px rgba(7,84,154,.22) !important;
        }

        [class*="st-key-phase_bar_"] button[data-testid="stBaseButton-primary"],
        [class*="st-key-phase_bar_"] button[data-testid="stBaseButton-primary"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        /* Selector de resultados: mismo estilo que la barra de fases */
        [class*="st-key-result_bar_"] {
            margin: .55rem 0 1rem;
            padding: .5rem;
            border: 1px solid var(--nexo-line);
            border-radius: 16px;
            background: #F1F5F8;
        }

        [class*="st-key-result_bar_"] [data-testid="stHorizontalBlock"] {
            gap: .5rem !important;
        }

        [class*="st-key-result_bar_"] button {
            min-height: 2.8rem;
            border: 1px solid var(--nexo-line-strong) !important;
            border-radius: 12px !important;
            background: #FFFFFF !important;
            box-shadow: none !important;
            transition: background .15s ease, border-color .15s ease, box-shadow .15s ease;
        }

        [class*="st-key-result_bar_"] button,
        [class*="st-key-result_bar_"] button * {
            color: var(--emi-blue-dark) !important;
            -webkit-text-fill-color: var(--emi-blue-dark) !important;
            font-weight: 740 !important;
        }

        [class*="st-key-result_bar_"] button:hover {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue-soft) !important;
        }

        [class*="st-key-result_bar_"] button[data-testid="stBaseButton-primary"] {
            border-color: var(--emi-blue) !important;
            background: var(--emi-blue) !important;
            box-shadow: 0 6px 16px rgba(7,84,154,.22) !important;
        }

        [class*="st-key-result_bar_"] button[data-testid="stBaseButton-primary"],
        [class*="st-key-result_bar_"] button[data-testid="stBaseButton-primary"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }

        [class*="st-key-phase_off_"],
        [data-testid="stLayoutWrapper"]:has(> [class*="st-key-phase_off_"]) {
            display: none !important;
        }

        [class*="st-key-phase_on_"] {
            padding: 1rem 1.2rem 1.25rem;
            border: 1px solid var(--nexo-line);
            border-top: 3px solid var(--emi-blue);
            border-radius: 16px;
            background: var(--nexo-surface);
            box-shadow: var(--nexo-shadow-sm);
        }

        .phase-panel-head {
            display: flex;
            align-items: center;
            gap: .65rem;
            margin-bottom: .5rem;
        }

        .phase-panel-letter {
            display: inline-grid;
            flex: 0 0 auto;
            place-items: center;
            width: 1.75rem;
            height: 1.75rem;
            border-radius: 9px;
            background: var(--emi-blue);
            color: #FFFFFF;
            font-size: .82rem;
            font-weight: 820;
        }

        .phase-panel-title {
            color: var(--emi-blue-dark);
            font-size: .98rem;
            font-weight: 780;
        }

        /* Entradas (issues) con su estado de revisión en GitLab */
        .entry-summary {
            display: flex;
            flex-wrap: wrap;
            gap: .4rem;
            margin: .2rem 0 .55rem;
        }

        .entry-row {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: .45rem .75rem;
            margin: .4rem 0;
            padding: .6rem .85rem;
            border: 1px solid var(--nexo-line);
            border-radius: 12px;
            background: #F9FBFD;
        }

        .entry-id {
            color: var(--emi-blue-dark);
            font-size: .88rem;
            font-weight: 800;
        }

        .entry-text {
            flex: 1 1 14rem;
            min-width: 0;
            color: var(--nexo-ink);
            font-size: .86rem;
            line-height: 1.4;
        }

        .wf-chip {
            display: inline-flex;
            align-items: center;
            padding: .16rem .62rem;
            border: 1px solid transparent;
            border-radius: 999px;
            font-size: .7rem;
            font-weight: 780;
            letter-spacing: .01em;
            white-space: nowrap;
        }

        .wf-chip.pendiente { border-color: #E6C340; background: #FFF6D1; color: #6F5400; }
        .wf-chip.rework { border-color: #E3A09B; background: #FDE8E6; color: #9A2A24; }
        .wf-chip.revisada { border-color: #9CC3EA; background: #E4EFFA; color: #17559A; }
        .wf-chip.sin-estado { border-color: var(--nexo-line-strong); background: #EEF2F6; color: var(--nexo-muted); }

        .wf-chip.tone-ok { border-color: #98D1AB; background: #E3F5E9; color: #176637; }
        .wf-chip.tone-warn { border-color: #E6C340; background: #FFF6D1; color: #6F5400; }
        .wf-chip.tone-bad { border-color: #E3A09B; background: #FDE8E6; color: #9A2A24; }
        .wf-chip.tone-info { border-color: #9CC3EA; background: #E4EFFA; color: #17559A; }
        .wf-chip.tone-muted { border-color: var(--nexo-line-strong); background: #EEF2F6; color: var(--nexo-muted); }

        /* Tarjeta de estado de una entrada: va al inicio de su propia pestaña */
        .entry-status-card {
            display: flex;
            flex-direction: column;
            gap: .5rem;
            margin: .1rem 0 .4rem;
            padding: .85rem 1.05rem;
            border: 1px solid var(--nexo-line);
            border-left: 4px solid var(--emi-yellow);
            border-radius: 14px;
            background: linear-gradient(145deg, #FFFFFF, #F8FBFD);
            box-shadow: var(--nexo-shadow-sm);
        }

        .entry-status-title {
            color: var(--emi-blue-dark);
            font-size: .92rem;
            font-weight: 800;
            letter-spacing: -.005em;
        }

        .entry-status-chips {
            display: flex;
            flex-wrap: wrap;
            gap: .35rem;
        }

        .entry-status-meta {
            color: var(--nexo-muted);
            font-size: .74rem;
            line-height: 1.35;
        }

        /* Fila de indicadores: mismo aspecto que las tarjetas st.metric, pero en
           una sola fila para no alargar la pantalla en vertical. */
        .kpi-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(8.4rem, 1fr));
            gap: .6rem;
            margin: .3rem 0 .75rem;
        }

        .kpi-item {
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: .25rem;
            min-height: 5.2rem;
            padding: .8rem .95rem .75rem 1.1rem;
            overflow: hidden;
            border: 1px solid var(--nexo-line);
            border-radius: 14px;
            background: linear-gradient(145deg, #FFFFFF, #F8FBFD);
            box-shadow: var(--nexo-shadow-sm);
        }

        .kpi-item::before {
            content: "";
            position: absolute;
            top: 0;
            bottom: 0;
            left: 0;
            width: 4px;
            background: linear-gradient(var(--emi-yellow), #F7D94D);
        }

        .kpi-value {
            color: var(--emi-blue-dark);
            font-size: clamp(1.3rem, 1.9vw, 1.6rem);
            font-weight: 820;
            line-height: 1.15;
        }

        .kpi-label {
            color: var(--nexo-muted);
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .015em;
            line-height: 1.25;
        }

        .kpi-strip.compact { grid-template-columns: repeat(auto-fit, minmax(7.4rem, 1fr)); }
        .kpi-strip.compact .kpi-item { min-height: 4.3rem; padding: .6rem .8rem .55rem 1rem; }
        .kpi-strip.compact .kpi-value { font-size: 1.2rem; }

        /* Rótulo de bloque dentro de una subsección (Ficha, Contenido, Acciones…) */
        .entry-block-label {
            margin: 1.05rem 0 .4rem;
            padding-bottom: .3rem;
            border-bottom: 1px solid var(--nexo-line);
            color: var(--emi-blue);
            font-size: .7rem;
            font-weight: 820;
            letter-spacing: .12em;
            text-transform: uppercase;
        }

        /* Tabs convertidas en selector claro y estable */
        [data-testid="stTabs"] {
            margin-top: .6rem;
        }

        [data-testid="stTabs"] [role="tablist"],
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: .35rem !important;
            padding: .32rem !important;
            overflow-x: auto;
            border: 1px solid var(--nexo-line);
            border-radius: 12px;
            background: #F1F5F8;
        }

        [data-testid="stTabs"] [role="tab"],
        [data-testid="stTabs"] [data-baseweb="tab"] {
            min-height: 2.55rem !important;
            padding: .48rem .95rem !important;
            border-radius: 9px !important;
            color: var(--nexo-muted) !important;
            -webkit-text-fill-color: var(--nexo-muted) !important;
            font-size: .85rem !important;
            font-weight: 680 !important;
        }

        [data-testid="stTabs"] [role="tab"]:hover,
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            background: rgba(255,255,255,.7) !important;
            color: var(--emi-blue-dark) !important;
        }

        [data-testid="stTabs"] [role="tab"][aria-selected="true"],
        [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
            background: #FFFFFF !important;
            color: var(--emi-blue-dark) !important;
            -webkit-text-fill-color: var(--emi-blue-dark) !important;
            box-shadow: 0 2px 8px rgba(5,47,86,.09) !important;
        }

        [data-testid="stTabs"] [role="tab"] p {
            color: inherit !important;
            -webkit-text-fill-color: inherit !important;
            font: inherit !important;
        }

        [data-testid="stTabs"] [data-baseweb="tab-highlight"],
        [data-testid="stTabs"] [class*="SelectionIndicator"] { display: none !important; }

        [data-testid="stTabs"] [data-baseweb="tab-panel"] {
            padding-top: 1rem !important;
        }

        /* Bloques internos de resultados */
        .result-intro,
        .metric-detail {
            margin: .72rem 0 !important;
            padding: .85rem 1rem !important;
            border: 1px solid var(--nexo-line) !important;
            border-left: 4px solid var(--emi-blue) !important;
            border-radius: 11px !important;
            background: var(--nexo-surface-muted) !important;
            color: var(--nexo-ink) !important;
            line-height: 1.55;
        }

        .finding-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .8rem;
            align-items: start;
            margin: .25rem 0 1rem;
        }

        .finding-panel {
            overflow: hidden;
            border: 1px solid var(--nexo-line);
            border-radius: 13px;
            background: #FFFFFF;
            box-shadow: var(--nexo-shadow-sm);
        }

        .finding-panel summary {
            display: flex;
            align-items: center;
            gap: .65rem;
            min-height: 3.3rem;
            padding: .72rem .78rem;
            cursor: pointer;
            list-style: none;
            color: var(--emi-blue-dark);
            font-size: .83rem;
            font-weight: 760;
            line-height: 1.25;
        }

        .finding-panel summary::-webkit-details-marker { display: none; }

        .finding-panel summary::before {
            content: "+";
            display: grid;
            place-items: center;
            flex: 0 0 auto;
            width: 1.35rem;
            height: 1.35rem;
            border-radius: 50%;
            background: var(--emi-blue-soft);
            color: var(--emi-blue-dark);
            font-size: .9rem;
        }

        .finding-panel[open] summary::before { content: "−"; }

        .finding-count {
            display: inline-grid;
            place-items: center;
            flex: 0 0 auto;
            min-width: 1.75rem;
            height: 1.75rem;
            margin-left: auto;
            padding: 0 .35rem;
            border-radius: 999px;
            background: var(--emi-blue-dark);
            color: #FFFFFF;
            font-size: .76rem;
            font-weight: 820;
        }

        .finding-panel-body { padding: 0 .75rem .75rem; }

        .finding-block {
            margin: .48rem 0 !important;
            padding: .72rem .78rem !important;
            border: 1px solid #DDE6EE !important;
            border-left: 4px solid #9CB8CF !important;
            border-radius: 9px !important;
            background: #F8FAFC !important;
            color: var(--nexo-ink) !important;
            font-size: .84rem;
            line-height: 1.5;
        }

        .finding-correction { border-left-color: #D18B20 !important; background: #FFFAF0 !important; }
        .finding-precision { border-left-color: var(--emi-blue) !important; background: #F3F8FC !important; }
        .finding-opportunity { border-left-color: #4C9870 !important; background: #F3FAF6 !important; }

        .finding-empty {
            margin: .45rem 0 0;
            padding: .7rem;
            border-radius: 9px;
            background: #F6F9FB;
            color: var(--nexo-muted);
            font-size: .81rem;
            line-height: 1.45;
        }

        .state-badge {
            display: inline-flex !important;
            align-items: center;
            gap: .35rem;
            padding: .35rem .68rem !important;
            border-radius: 999px !important;
            font-size: .7rem !important;
            font-weight: 820 !important;
            letter-spacing: .04em !important;
            text-transform: uppercase;
        }

        .state-badge::before {
            content: "";
            width: .43rem;
            height: .43rem;
            border-radius: 50%;
            background: currentColor;
        }

        /* Tablas y archivos */
        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"],
        [data-testid="stTable"],
        [data-testid="stFileUploaderDropzone"] {
            overflow: hidden;
            border: 1px solid var(--nexo-line) !important;
            border-radius: 13px !important;
            background: #FFFFFF !important;
            color: var(--nexo-ink) !important;
            box-shadow: var(--nexo-shadow-sm) !important;
        }

        /* Streamlit dibuja matrices interactivas con Glide Data Grid. El tema
           claro definido para la aplicación se refuerza aquí para impedir que
           el lienzo, la barra de herramientas o los controles hereden negro. */
        div[data-testid="stDataFrame"] > div,
        div[data-testid="stDataEditor"] > div,
        div[data-testid="stDataFrame"] [data-testid="stDataFrameGlideDataEditor"],
        div[data-testid="stDataEditor"] [data-testid="stDataFrameGlideDataEditor"],
        div[data-testid="stDataFrame"] canvas,
        div[data-testid="stDataEditor"] canvas {
            background-color: #FFFFFF !important;
            color: var(--nexo-ink) !important;
        }

        div[data-testid="stDataFrame"] button,
        div[data-testid="stDataEditor"] button,
        [data-testid="stElementToolbar"] button {
            border-color: var(--nexo-line) !important;
            background: #FFFFFF !important;
            color: var(--emi-blue-dark) !important;
        }

        div[data-testid="stDataFrame"] button:hover,
        div[data-testid="stDataEditor"] button:hover,
        [data-testid="stElementToolbar"] button:hover {
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
        }

        [data-testid="stTable"] table,
        [data-testid="stTable"] thead,
        [data-testid="stTable"] tbody,
        [data-testid="stTable"] tr {
            background: #FFFFFF !important;
            color: var(--nexo-ink) !important;
        }

        [data-testid="stTable"] th {
            border-color: #C7D9E7 !important;
            background: var(--emi-blue-soft) !important;
            color: var(--emi-blue-dark) !important;
            font-weight: 760 !important;
        }

        [data-testid="stTable"] td {
            border-color: var(--nexo-line) !important;
            background: #FFFFFF !important;
            color: var(--nexo-ink) !important;
        }

        [data-testid="stTable"] tbody tr:nth-child(even) td {
            background: #F7FAFC !important;
        }

        /* Otros contenedores que Streamlit muestra oscuros cuando el sistema
           operativo usa tema oscuro. Se mantienen claros y consistentes. */
        [data-testid="stJson"],
        [data-testid="stCodeBlock"],
        [data-testid="stException"],
        [data-baseweb="popover"],
        [data-baseweb="menu"],
        [role="listbox"] {
            border-color: var(--nexo-line) !important;
            background: #FFFFFF !important;
            color: var(--nexo-ink) !important;
        }

        [data-testid="stCodeBlock"] code,
        [data-testid="stCodeBlock"] pre,
        [data-testid="stJson"] pre,
        [data-baseweb="popover"] *,
        [data-baseweb="menu"] *,
        [role="listbox"] * {
            color: var(--nexo-ink) !important;
            -webkit-text-fill-color: var(--nexo-ink) !important;
        }

        [data-testid="stCodeBlock"] pre,
        [data-testid="stJson"] pre {
            background: #F7FAFC !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            padding: .85rem !important;
            border-style: dashed !important;
            background: #F7FAFC !important;
        }

        hr {
            margin: 1.45rem 0 !important;
            border-color: var(--nexo-line) !important;
            opacity: 1 !important;
        }

        [data-testid="stCaptionContainer"] {
            color: var(--nexo-muted) !important;
            font-size: .79rem !important;
            line-height: 1.5 !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            width: 292px !important;
            min-width: 292px !important;
            border-right: 0 !important;
            background:
                radial-gradient(circle at 15% 0%, rgba(16,112,183,.42), transparent 30%),
                linear-gradient(180deg, #063F70 0%, var(--emi-blue-deep) 100%) !important;
            box-shadow: 8px 0 28px rgba(5,47,86,.11);
            transition: width .26s ease, min-width .26s ease, transform .26s ease !important;
        }

        /* Al cerrarse, Streamlit traslada el panel pero conserva su ancho en
           el flujo. Liberarlo evita la franja vacía y permite que el contenido
           principal ocupe suavemente todo el espacio disponible. */
        [data-testid="stSidebar"][aria-expanded="false"] {
            width: 0 !important;
            min-width: 0 !important;
            border-right: 0 !important;
            box-shadow: none !important;
        }

        /* Riel de íconos: en escritorio, al cerrarse, el sidebar no desaparece por
           completo; queda una columna angosta con el símbolo de cada botón (el
           nombre se ve en el tooltip al pasar el cursor). En pantallas angostas
           se conserva el comportamiento anterior (oculto por completo). */
        :root {
            --nexo-rail-w: 4.5rem;
            --nexo-collapsed-w: 0px;
        }

        @media (min-width: 769px) {
            :root { --nexo-collapsed-w: var(--nexo-rail-w); }

            [data-testid="stSidebar"][aria-expanded="false"] {
                width: var(--nexo-rail-w) !important;
                min-width: var(--nexo-rail-w) !important;
                overflow: hidden !important;
                transform: none !important;
                box-shadow: 8px 0 28px rgba(5,47,86,.11) !important;
            }

            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarHeader"] {
                display: none;
            }

            /* Arriba se reserva el lugar del botón que vuelve a abrir el menú
               (ver más abajo): 1.1rem de margen + 2.9rem del botón. */
            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"] {
                padding: 4rem .55rem 1.5rem !important;
            }

            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarContent"]::before {
                content: "";
                display: block;
                height: 1px;
                margin: .85rem .6rem;
                background: rgba(255,255,255,.16);
            }

            /* Flecha para abrir el menú: Streamlit la dibuja en el header; aquí se
               ancla como primer elemento del riel, sobre los íconos. El header
               queda por debajo del sidebar en el apilado, así que se sube de
               capa (sigue sin capturar clics: es transparente y con
               pointer-events: none salvo sus botones). */
            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stHeader"] {
                z-index: 999992;
            }

            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"] {
                position: fixed;
                top: 1.1rem;
                left: calc((var(--nexo-rail-w) - 2.9rem) / 2);
                display: flex;
                align-items: center;
                justify-content: center;
                width: 2.9rem;
                height: 2.9rem;
                margin: 0;
                padding: 0;
                border: 1px solid rgba(255,255,255,.22);
                border-radius: 13px;
                background: rgba(255,255,255,.08);
                transition: background .15s ease, border-color .15s ease;
            }

            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"]:hover {
                border-color: var(--emi-yellow) !important;
                background: var(--emi-yellow) !important;
            }

            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"]:hover * {
                color: var(--emi-blue-deep) !important;
                -webkit-text-fill-color: var(--emi-blue-deep) !important;
            }

            /* Con la flecha en el riel, el banner ya no necesita dejarle sitio */
            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .nexo-hero {
                padding-left: clamp(1rem, 2vw, 1.75rem);
            }

            /* La tarjeta del proyecto y el rótulo que le sigue no se muestran en el riel */
            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stElementContainer"]:has(.sidebar-project-card),
            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stElementContainer"]:has(.sidebar-project-card) + [data-testid="stElementContainer"] {
                display: none;
            }

            /* Los rótulos de grupo pasan a ser separadores finos */
            [data-testid="stSidebar"][aria-expanded="false"] .sidebar-section-label {
                height: 1px;
                margin: .85rem .6rem;
                padding: 0;
                overflow: hidden;
                background: rgba(255,255,255,.16);
                font-size: 0;
            }

            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stTooltipHoverTarget"] {
                justify-content: center !important;
            }

            /* En el riel las etapas son íconos alineados con el resto: sin sangría */
            [data-testid="stSidebar"][aria-expanded="false"] .st-key-nav_stages {
                width: 100% !important;
                margin: 0;
                padding-left: 0;
                border-left: 0;
            }

            [data-testid="stSidebar"][aria-expanded="false"] .stButton button {
                width: 2.9rem !important;
                min-width: 2.9rem !important;
                height: 2.9rem;
                min-height: 2.9rem;
                padding: 0 !important;
                border-radius: 13px;
            }

            [data-testid="stSidebar"][aria-expanded="false"] .stButton button [data-testid="stMarkdownContainer"] {
                display: none;
            }

            /* Confirmaciones (p. ej. «Base de datos limpia»): solo el ícono */
            [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stAlertContent"] {
                display: none;
            }
        }

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 1.1rem .9rem 2rem !important;
        }

        .sidebar-section-label {
            margin: 1.1rem .1rem .48rem;
            color: var(--emi-yellow);
            font-size: .68rem;
            font-weight: 820;
            letter-spacing: .14em;
            text-transform: uppercase;
        }

        .sidebar-project-card {
            margin: 0 0 1.1rem;
            padding: .85rem;
            border: 1px solid rgba(255,255,255,.13);
            border-radius: 13px;
            background: rgba(255,255,255,.07);
        }

        .sidebar-project-card > small {
            display: block;
            color: #AFC9DF;
            font-size: .68rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        .sidebar-project-card > strong {
            display: block;
            margin: .18rem 0 .75rem;
            color: #FFFFFF;
            font-size: .9rem;
            line-height: 1.35;
        }

        .sidebar-meta {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: .42rem .6rem;
            padding-top: .7rem;
            border-top: 1px solid rgba(255,255,255,.12);
            font-size: .75rem;
        }

        .sidebar-meta span { color: #AFC9DF !important; }
        .sidebar-meta b { color: #FFFFFF !important; font-weight: 700; }
        .sidebar-dot { color: #7CE2A5 !important; }

        [data-testid="stSidebar"] h2 {
            margin-top: 1.25rem !important;
            color: #FFFFFF !important;
            font-size: .92rem !important;
            font-weight: 760 !important;
        }

        [data-testid="stSidebar"] hr {
            margin: 1rem 0 !important;
            border-color: rgba(255,255,255,.14) !important;
        }

        [data-testid="stSidebar"] .stButton button {
            width: 100% !important;
            border-color: rgba(255,255,255,.22) !important;
            background: rgba(255,255,255,.08) !important;
            color: #FFFFFF !important;
            font-size: .8rem !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] .stButton button:hover {
            border-color: var(--emi-yellow) !important;
            background: var(--emi-yellow) !important;
            color: var(--emi-blue-deep) !important;
        }

        /* Elemento activo del menú (etapa en curso o Panel del proyecto): relleno
           amarillo institucional, el mismo color del resalte al pasar el cursor,
           pero fijo y con texto en negrita para distinguirlo a simple vista. */
        [data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] {
            border-color: var(--emi-yellow) !important;
            background: var(--emi-yellow) !important;
            color: var(--emi-blue-deep) !important;
            font-weight: 780 !important;
            box-shadow: 0 0 0 3px rgba(242,195,0,.22) !important;
        }

        [data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] *,
        [data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"]:hover * {
            color: var(--emi-blue-deep) !important;
            -webkit-text-fill-color: var(--emi-blue-deep) !important;
        }

        /* Los nombres de las etapas se alinean a la izquierda (ícono + texto), para
           que queden alineados entre sí. Solo con el menú abierto: en el riel de
           íconos cada botón es solo un ícono centrado. */
        [data-testid="stSidebar"][aria-expanded="true"] .st-key-nav_stages .stButton button,
        [data-testid="stSidebar"][aria-expanded="true"] .st-key-nav_stages .stButton button > div,
        [data-testid="stSidebar"][aria-expanded="true"] .st-key-nav_stages .stButton button > div > span {
            justify-content: flex-start !important;
            text-align: left !important;
        }

        [data-testid="stSidebar"][aria-expanded="true"] .st-key-nav_stages .stButton button {
            padding-left: 1rem !important;
        }

        /* Las 4 etapas se despliegan bajo «Evaluación por etapas», con una guía
           lateral que las agrupa visualmente bajo ese elemento. */
        [data-testid="stSidebar"] .st-key-nav_stages {
            gap: .45rem !important;
            width: calc(100% - 1.15rem) !important;
            margin: -.2rem 0 0 1.15rem;
            padding-left: .7rem;
            border-left: 1px solid rgba(255,255,255,.2);
        }

        /* En pantallas angostas el sidebar se abre como panel superpuesto: el
           banner ocupa todo el ancho y queda por debajo de él. */
        @media (max-width: 768px) {
            .nexo-hero { left: 0; }
        }

        @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main .block-container,
            [data-testid="stMainBlockContainer"] {
                padding: 1rem 1rem 3.5rem !important;
            }

            .finding-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 640px) {
            :root { --nexo-toolbar-w: 7.8rem; }
            .stApp:has([data-testid="stSidebar"][aria-expanded="false"]) .nexo-hero { padding-left: 3.2rem; }
            .nexo-area-title-rule { display: none; }
            .nexo-hero-divider,
            .nexo-product-kicker,
            .nexo-session-text { display: none; }
            .nexo-session-badge { padding: .3rem; border-radius: 999px; }
            .nexo-entity { padding: .3rem .45rem; }
            .nexo-entity img { max-width: 84px; }
            .nexo-product img { height: 1.7rem; }
            .stage-context-card { align-items: flex-start; flex-direction: column; }
            .milestone-chip { width: 100%; min-width: 0; }
            .st-key-stage_shell { padding-inline: .45rem !important; }
            .st-key-stage_shell [data-testid="stHorizontalBlock"] { gap: .2rem !important; }
            .stage-label { font-size: .65rem !important; }
        }

        @media (max-width: 480px) {
            .nexo-session-badge { display: none; }
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
                animation-duration: .01ms !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_header(
    entity_logo_path: str | Path,
    tool_logo_path: str | Path,
    session_name: str | None = None,
    session_role: str = SESSION_ROLE,
) -> None:
    entity_logo = _data_uri(entity_logo_path, "image/png")
    tool_logo = _data_uri(tool_logo_path, "image/svg+xml")

    session_badge_html = ""
    nombre = (session_name or "").strip()
    if nombre:
        inicial = escape(nombre[:1].upper())
        session_badge_html = (
            '<div class="nexo-session-badge" title="Sesión activa">'
            f'<span class="nexo-session-avatar">{inicial}</span>'
            '<span class="nexo-session-text">'
            f'<span class="nexo-session-name">{escape(nombre)}</span>'
            f'<span class="nexo-session-role">{escape(session_role)}</span>'
            "</span>"
            "</div>"
        )

    st.markdown(
        f"""
        <header class="nexo-hero">
            <div class="nexo-entity">
                <img src="{entity_logo}" alt="Escuela Militar de Ingeniería">
            </div>
            <div class="nexo-hero-divider" aria-hidden="true"></div>
            <div class="nexo-product">
                <div class="nexo-product-kicker">Herramienta multiagente</div>
                <img src="{tool_logo}" alt="TraceDev — Desarrollo, trazabilidad y decisión">{session_badge_html}
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_stage_context(stage_name: str, milestone: str) -> None:
    st.markdown(
        f"""
        <section class="stage-context-card">
            <div class="stage-context-copy">
                <span>Etapa activa</span>
                <h2>{escape(stage_name)}</h2>
            </div>
            <div class="milestone-chip">
                <small>Milestone asociado</small>
                <strong>{escape(milestone)}</strong>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


_AREA_ICON_ATTRS = (
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"'
)

_AREA_ICONS = {
    # Ruta con nodos: flujo no lineal de etapas.
    "etapas": (
        f"<svg {_AREA_ICON_ATTRS}>"
        '<circle cx="5" cy="6" r="2.2"/><circle cx="19" cy="18" r="2.2"/>'
        '<path d="M7.2 6H14a3 3 0 0 1 0 6h-4a3 3 0 0 0 0 6h6.8"/></svg>'
    ),
    # Engranaje: configuración del proyecto.
    "configuracion": (
        f"<svg {_AREA_ICON_ATTRS}>"
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 '
        '1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1'
        'a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1'
        'a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5h0'
        'a1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1'
        'a1.7 1.7 0 0 0-1.5 1z"/></svg>'
    ),
    # Tablero: panel de seguimiento del proyecto.
    "panel": (
        f"<svg {_AREA_ICON_ATTRS}>"
        '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
        '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>'
    ),
    # Lista de verificación: fases internas de una etapa.
    "fases": (
        f"<svg {_AREA_ICON_ATTRS}>"
        '<path d="M9 6h11M9 12h11M9 18h11"/>'
        '<path d="m3.5 6 1.2 1.2L7 4.8M3.5 12l1.2 1.2L7 10.8M3.5 18l1.2 1.2L7 16.8"/></svg>'
    ),
}


def render_section_title(
    title: str,
    eyebrow: str = "",
    description: str = "",
    icon: str = "etapas",
) -> None:
    """Título visual de un área principal de la herramienta. Solo presentación."""
    eyebrow_html = f'<span class="nexo-area-title-eyebrow">{escape(eyebrow)}</span>' if eyebrow else ""
    description_html = f'<p class="nexo-area-title-desc">{escape(description)}</p>' if description else ""
    st.markdown(
        '<div class="nexo-area-title">'
        f'<div class="nexo-area-title-mark">{_AREA_ICONS.get(icon, _AREA_ICONS["etapas"])}</div>'
        '<div class="nexo-area-title-copy">'
        f"{eyebrow_html}"
        f'<div class="nexo-area-title-name" role="heading" aria-level="2">{escape(title)}</div>'
        f"{description_html}"
        "</div>"
        '<div class="nexo-area-title-rule" aria-hidden="true"></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def render_subsection_title(text: str) -> None:
    """Subtítulo de una acción dentro de un área principal. Solo presentación."""
    st.markdown(
        f'<div class="nexo-subarea-title" role="heading" aria-level="3">{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar_section_label(text: str) -> None:
    """Rótulo de grupo del sidebar, con el mismo estilo que «Proyecto activo»."""
    st.markdown(
        f'<div class="sidebar-section-label">{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_login_card(
    entity_logo_path: str | Path,
    tool_logo_path: str | Path,
    background_path: str | Path | None = None,
) -> "st.delta_generator.DeltaGenerator":
    """Renderiza la pantalla de acceso institucional (pre-login) y devuelve el
    contenedor de la tarjeta para que el botón de Microsoft 365 se dibuje
    dentro de ella; app.py resuelve el clic (st.login())."""
    background_css = "linear-gradient(135deg, var(--emi-blue-deep), var(--emi-blue) 65%, #0A63AE)"
    if background_path and Path(background_path).exists():
        mime = "image/png" if Path(background_path).suffix.lower() == ".png" else "image/jpeg"
        # "cover" llena toda la pantalla sin las franjas de color que dejaba
        # "contain" con una imagen vertical en pantallas anchas; el degradado
        # institucional superpuesto uniforma el tono y mantiene el contraste
        # del texto/tarjeta sobre cualquier zona de la foto.
        background_css = (
            "linear-gradient(135deg, rgba(6, 58, 107, .45), rgba(10, 99, 174, .25)), "
            f"url('{_data_uri(background_path, mime)}') center/cover no-repeat fixed"
        )

    entity_logo = _data_uri(entity_logo_path, "image/png")
    tool_logo = _data_uri(tool_logo_path, "image/svg+xml")

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: {background_css} !important;
        }}
        [data-testid="stHeader"] {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 100% !important;
            padding: 0 !important;
        }}
        @keyframes loginFadeUp {{
            from {{ opacity: 0; transform: translateY(26px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .st-key-login_shell {{
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - 3.2rem);
            padding: 1rem 1.25rem;
        }}
        .st-key-login_shell::before {{
            content: "";
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at 24% 22%, rgba(242, 195, 0, .12), transparent 45%),
                radial-gradient(circle at 76% 78%, rgba(10, 99, 174, .22), transparent 45%);
            pointer-events: none;
        }}
        .st-key-login_frame {{
            position: relative;
            z-index: 1;
            width: min(94vw, 460px);
            max-height: calc(100vh - 2rem);
            margin: 0 auto !important;
            padding: 12px;
            overflow-y: auto;
            background: rgba(255, 255, 255, .16);
            backdrop-filter: blur(22px) saturate(140%);
            -webkit-backdrop-filter: blur(22px) saturate(140%);
            border: 1px solid rgba(255, 255, 255, .45);
            border-radius: 30px;
            box-shadow: 0 30px 80px rgba(2, 16, 34, .5), inset 0 1px 0 rgba(255, 255, 255, .3);
            animation: loginFadeUp .65s ease-out;
        }}
        .st-key-login_frame::-webkit-scrollbar {{
            display: none;
        }}
        .st-key-login_card {{
            width: 100%;
            margin: 0 !important;
            padding: clamp(1.3rem, 3vw, 1.8rem) clamp(1.3rem, 3vw, 1.7rem) 1.4rem;
            background: rgba(255, 255, 255, .98);
            border: 1px solid rgba(255, 255, 255, .7);
            border-radius: 22px;
            box-shadow: 0 10px 30px rgba(4, 30, 58, .2);
            text-align: center;
        }}
        .login-logo {{
            display: block;
            width: min(100%, 140px);
            margin: 0 auto .5rem;
        }}
        .login-tool-badge {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: fit-content;
            margin: 0 auto .5rem;
            padding: .35rem .8rem;
            border-radius: 12px;
            background: linear-gradient(118deg, var(--emi-blue-deep), var(--emi-blue) 72%, #0A63AE);
            box-shadow: 0 8px 20px rgba(5,47,86,.18);
        }}
        .login-tool-logo {{
            display: block;
            width: min(100%, 130px);
            height: auto;
        }}
        .login-kicker {{
            margin: 0 0 .7rem;
            color: var(--emi-blue-dark);
            font-size: clamp(.92rem, 2vw, 1.05rem);
            font-weight: 800;
            line-height: 1.35;
            letter-spacing: -.01em;
            text-align: center !important;
        }}
        .login-divider {{
            position: relative;
            height: 1px;
            margin: 0 auto .75rem;
            background: linear-gradient(90deg, transparent, var(--nexo-line-strong), transparent);
        }}
        .login-divider::after {{
            content: "";
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--emi-yellow);
            box-shadow: 0 0 7px rgba(242, 195, 0, .65);
        }}
        .login-welcome {{
            margin: 0 0 .4rem;
            color: var(--emi-blue-dark) !important;
            font-size: clamp(1.15rem, 2.6vw, 1.4rem);
            font-weight: 800;
            text-align: center !important;
        }}
        .login-caption {{
            margin: 0 0 .9rem;
            color: var(--nexo-muted);
            font-size: .88rem;
            line-height: 1.45;
        }}
        .st-key-login_card .stButton > button {{
            position: relative;
            width: 100%;
            min-height: 2.85rem;
            border-radius: 10px;
            font-weight: 750;
            overflow: hidden;
            box-shadow: 0 10px 24px rgba(7, 84, 154, .28);
            transition: transform .2s ease, box-shadow .2s ease;
        }}
        .st-key-login_card .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 14px 30px rgba(7, 84, 154, .38);
        }}
        .st-key-login_card .stButton > button::before {{
            content: "";
            position: absolute;
            inset: 0;
            left: -100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, .28), transparent);
            transition: left .5s ease;
        }}
        .st-key-login_card .stButton > button:hover::before {{
            left: 100%;
        }}
        .login-help {{
            margin: .9rem 0 0;
            padding-top: .7rem;
            border-top: 1px solid var(--nexo-line);
            color: var(--nexo-muted);
            font-size: .74rem;
            line-height: 1.4;
        }}
        </style>
        <div></div>
        """,
        unsafe_allow_html=True,
    )

    shell = st.container(key="login_shell")
    frame = shell.container(key="login_frame")
    card = frame.container(key="login_card")
    card.markdown(
        f"""
        <img class="login-logo" src="{entity_logo}" alt="Escuela Militar de Ingeniería">
        <div class="login-tool-badge">
            <img class="login-tool-logo" src="{tool_logo}" alt="TraceDev">
        </div>
        <p class="login-kicker">Control y Trazabilidad del Desarrollo de Software</p>
        <div class="login-divider"></div>
        <h1 class="login-welcome">Bienvenido</h1>
        <p class="login-caption">Inicia sesión con tu cuenta institucional de Microsoft 365 para continuar.</p>
        """,
        unsafe_allow_html=True,
    )
    return card


def render_login_help(card: "st.delta_generator.DeltaGenerator") -> None:
    """Nota de soporte al pie de la tarjeta de login; se dibuja después del
    botón de Microsoft 365 porque este último se resuelve en app.py."""
    card.markdown(
        '<p class="login-help">Si tienes problemas para iniciar sesión, '
        "contacta con el área de Tecnologías de la Información de la EMI.</p>",
        unsafe_allow_html=True,
    )


def render_sidebar_project(project_config) -> None:
    configurado = project_config is not None
    project_config = project_config or {}
    project_name = escape(str(project_config.get("name", "") or "Sin proyecto configurado"))
    context_version = escape(str(project_config.get("context_version", "") or "—"))
    estado_gitlab = (
        '<i class="sidebar-dot">●</i> Conectado' if configurado else "Pendiente"
    )
    st.markdown(
        f"""
        <div class="sidebar-section-label">Proyecto activo</div>
        <div class="sidebar-project-card">
            <small>Proyecto</small>
            <strong>{project_name}</strong>
            <div class="sidebar-meta">
                <span>GitLab</span><b>{estado_gitlab}</b>
                <span>Contexto</span><b>{context_version}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
