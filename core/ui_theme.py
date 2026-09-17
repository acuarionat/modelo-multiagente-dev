"""Identidad y sistema visual compartido de la interfaz Streamlit.

Este módulo solo contiene presentación. No modifica el contenido, las métricas
ni el comportamiento del flujo multiagente.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import streamlit as st


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
            margin: 1.7rem 0 .72rem !important;
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

        /* Encabezado institucional + producto */
        .nexo-hero {
            position: relative;
            display: grid;
            grid-template-columns: minmax(190px, 26%) 1px 1fr;
            align-items: center;
            gap: clamp(1.15rem, 2.5vw, 2.2rem);
            min-height: 154px;
            margin: .25rem 0 1rem;
            padding: 1.35rem clamp(1.25rem, 3vw, 2.5rem);
            overflow: hidden;
            border: 1px solid rgba(255,255,255,.16);
            border-radius: var(--nexo-radius-lg);
            background:
                radial-gradient(circle at 92% 8%, rgba(242,195,0,.19), transparent 24%),
                linear-gradient(118deg, var(--emi-blue-deep), var(--emi-blue) 72%, #0A63AE);
            box-shadow: var(--nexo-shadow);
        }

        /* Sesión activa: identidad del usuario visible en el header, esquina
           superior derecha. Solo presentación (no altera st.login/st.logout). */
        .nexo-session-badge {
            position: absolute;
            top: 1rem;
            right: 1.35rem;
            z-index: 2;
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            max-width: min(46%, 260px);
            padding: .38rem .8rem .38rem .5rem;
            border: 1px solid rgba(255,255,255,.32);
            border-radius: 999px;
            background: rgba(6, 58, 107, .4);
            backdrop-filter: blur(8px);
        }

        .nexo-session-avatar {
            display: inline-grid;
            flex: 0 0 auto;
            place-items: center;
            width: 1.65rem;
            height: 1.65rem;
            border-radius: 50%;
            background: var(--emi-yellow);
            color: var(--emi-blue-deep);
            font-size: .74rem;
            font-weight: 820;
        }

        .nexo-session-name {
            overflow: hidden;
            color: #FFFFFF;
            font-size: .8rem;
            font-weight: 700;
            white-space: nowrap;
            text-overflow: ellipsis;
        }

        .nexo-entity {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 112px;
            padding: .9rem 1rem;
            border: 1px solid rgba(255,255,255,.8);
            border-radius: 14px;
            background: rgba(255,255,255,.97);
        }

        .nexo-entity img {
            display: block;
            width: min(100%, 240px);
            max-height: 96px;
            object-fit: contain;
        }

        .nexo-hero-divider {
            width: 1px;
            height: 92px;
            background: linear-gradient(transparent, rgba(255,255,255,.48), transparent);
        }

        .nexo-product { min-width: 0; }

        .nexo-product-kicker {
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            margin-bottom: .48rem;
            color: var(--emi-yellow);
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .15em;
            text-transform: uppercase;
        }

        .nexo-product-kicker::before {
            content: "";
            width: 1.75rem;
            height: 2px;
            border-radius: 2px;
            background: currentColor;
        }

        .nexo-product img {
            display: block;
            width: min(100%, 470px);
            height: 86px;
            object-fit: contain;
            object-position: left center;
        }

        .nexo-product p {
            margin: .2rem 0 0;
            color: #DCEAF6 !important;
            font-size: .95rem;
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

        .stage-context-copy span {
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

        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding: 1.1rem .9rem 2rem !important;
        }

        .nexo-sidebar-brand {
            padding: .78rem .78rem .9rem;
            border: 1px solid rgba(255,255,255,.14);
            border-radius: 15px;
            background: rgba(255,255,255,.055);
        }

        .nexo-sidebar-brand img {
            display: block;
            width: 100%;
            height: 72px;
            object-fit: contain;
            object-position: left center;
        }

        .nexo-sidebar-brand p {
            margin: .3rem 0 0;
            color: #CFE0EF !important;
            font-size: .76rem;
            line-height: 1.45;
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

        [data-testid="stSidebar"] .stButton > button {
            width: 100% !important;
            border-color: rgba(255,255,255,.22) !important;
            background: rgba(255,255,255,.08) !important;
            color: #FFFFFF !important;
            font-size: .8rem !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: var(--emi-yellow) !important;
            background: var(--emi-yellow) !important;
            color: var(--emi-blue-deep) !important;
        }

        @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main .block-container,
            [data-testid="stMainBlockContainer"] {
                padding: 1rem 1rem 3.5rem !important;
            }

            .nexo-hero {
                grid-template-columns: 150px 1px 1fr;
                min-height: 132px;
                padding: 1rem;
            }

            .nexo-entity { min-height: 90px; padding: .65rem; }
            .nexo-product img { height: 72px; }
            .finding-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 640px) {
            .nexo-hero {
                grid-template-columns: 1fr;
                gap: .75rem;
            }

            .nexo-entity { min-height: 76px; }
            .nexo-entity img { max-height: 68px; }
            .nexo-hero-divider { width: 100%; height: 1px; }
            .nexo-product-kicker { margin-top: .15rem; }
            .nexo-product img { height: 62px; }
            .nexo-session-badge { top: .6rem; right: .6rem; max-width: 55%; padding: .3rem .6rem .3rem .4rem; }
            .nexo-session-name { font-size: .72rem; }
            .stage-context-card { align-items: flex-start; flex-direction: column; }
            .milestone-chip { width: 100%; min-width: 0; }
            .st-key-stage_shell { padding-inline: .45rem !important; }
            .st-key-stage_shell [data-testid="stHorizontalBlock"] { gap: .2rem !important; }
            .stage-label { font-size: .65rem !important; }
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
            f'<span class="nexo-session-name">{escape(nombre)}</span>'
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
                <img src="{tool_logo}" alt="TraceDev — Desarrollo, trazabilidad y decisión">
                <p>Proceso adaptativo para el desarrollo y la trazabilidad de software.</p>
            </div>
            {session_badge_html}
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
        # "contain" evita el recorte/zoom que produce "cover" con una imagen
        # vertical sobre pantallas anchas; el color de respaldo rellena los
        # márgenes que deja de sobra con el mismo tono del fondo institucional.
        background_css = (
            f"url('{_data_uri(background_path, mime)}') center/contain no-repeat fixed "
            "var(--emi-blue-deep)"
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
            padding: 2rem 1.25rem;
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
            margin: 0 auto !important;
            padding: 16px;
            background: rgba(255, 255, 255, .16);
            backdrop-filter: blur(22px) saturate(140%);
            -webkit-backdrop-filter: blur(22px) saturate(140%);
            border: 1px solid rgba(255, 255, 255, .45);
            border-radius: 30px;
            box-shadow: 0 30px 80px rgba(2, 16, 34, .5), inset 0 1px 0 rgba(255, 255, 255, .3);
            animation: loginFadeUp .65s ease-out;
        }}
        .st-key-login_card {{
            width: 100%;
            margin: 0 !important;
            padding: clamp(2rem, 4.5vw, 2.7rem) clamp(1.7rem, 4vw, 2.3rem) 2.2rem;
            background: rgba(255, 255, 255, .98);
            border: 1px solid rgba(255, 255, 255, .7);
            border-radius: 22px;
            box-shadow: 0 10px 30px rgba(4, 30, 58, .2);
            text-align: center;
        }}
        .login-logo {{
            display: block;
            width: min(100%, 230px);
            margin: 0 auto .95rem;
        }}
        .login-tool-badge {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: fit-content;
            margin: 0 auto .95rem;
            padding: .6rem 1.1rem;
            border-radius: 14px;
            background: linear-gradient(118deg, var(--emi-blue-deep), var(--emi-blue) 72%, #0A63AE);
            box-shadow: 0 8px 20px rgba(5,47,86,.18);
        }}
        .login-tool-logo {{
            display: block;
            width: min(100%, 190px);
            height: auto;
        }}
        .login-kicker {{
            margin: 0 0 1.1rem;
            color: var(--emi-blue-dark);
            font-size: clamp(1rem, 2.3vw, 1.15rem);
            font-weight: 800;
            line-height: 1.35;
            letter-spacing: -.01em;
            text-align: center !important;
        }}
        .login-divider {{
            position: relative;
            height: 1px;
            margin: 0 auto 1.15rem;
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
            margin: 0 0 .6rem;
            color: var(--emi-blue-dark) !important;
            font-size: clamp(1.3rem, 3vw, 1.55rem);
            font-weight: 800;
            text-align: center !important;
        }}
        .login-caption {{
            margin: 0 0 1.6rem;
            color: var(--nexo-muted);
            font-size: .92rem;
            line-height: 1.55;
        }}
        .st-key-login_card .stButton > button {{
            position: relative;
            width: 100%;
            min-height: 3.1rem;
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
            margin: 1.6rem 0 0;
            padding-top: 1rem;
            border-top: 1px solid var(--nexo-line);
            color: var(--nexo-muted);
            font-size: .78rem;
            line-height: 1.5;
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


def render_sidebar_brand(tool_logo_path: str | Path, project_config: dict) -> None:
    tool_logo = _data_uri(tool_logo_path, "image/svg+xml")
    project_name = escape(str(project_config.get("name", "")))
    context_version = escape(str(project_config.get("context_version", "")))
    st.markdown(
        f"""
        <div class="nexo-sidebar-brand">
            <img src="{tool_logo}" alt="TraceDev">
            <p>Herramienta Multiagente<br>Control y seguimiento del Desarrollo de Software</p>
        </div>
        <div class="sidebar-section-label">Proyecto activo</div>
        <div class="sidebar-project-card">
            <small>Proyecto</small>
            <strong>{project_name}</strong>
            <div class="sidebar-meta">
                <span>GitLab</span><b><i class="sidebar-dot">●</i> Conectado</b>
                <span>Contexto</span><b>{context_version}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
