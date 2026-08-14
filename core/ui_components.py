"""
Componentes visuales comunes para la interfaz Streamlit.

Extraídos del patrón de Recepción de Requerimientos para que Diseño
(y futuras etapas) reutilicen la misma jerarquía visual.

Solo presentación: no recalcula métricas ni modifica datos.
"""

from html import escape

import streamlit as st


# ---------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------

def _lista_ui(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _texto_hallazgo_ui(item):
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for field in ("recomendacion", "precision", "sugerencia", "funcion", "descripcion", "texto"):
            value = str(item.get(field) or "").strip()
            if value:
                return value
    return ""


# ---------------------------------------------------------
# Badge de estado
# ---------------------------------------------------------

_BADGE_CLASSES = {
    "CORREGIR": "state-corregir",
    "CONFORME CON MEJORAS": "state-mejoras",
    "CONFORME": "state-conforme",
}


def render_state_badge(estado: str) -> None:
    cls = _BADGE_CLASSES.get(estado, "state-revision")
    st.markdown(
        f'<span class="state-badge {cls}">{estado}</span>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Encabezado de resultado (Estado + métricas principales)
# ---------------------------------------------------------

def render_evaluation_header(
    titulo: str,
    estado: str,
    indice_calidad: str,
    indice_seguridad: str,
    explicacion_estado: str = "",
) -> None:
    st.subheader(titulo)
    render_state_badge(estado)

    m1, m2 = st.columns(2)
    m1.metric("Índice de Calidad", indice_calidad)
    m2.metric("Índice de Seguridad", indice_seguridad)

    if explicacion_estado:
        st.info(f"**¿Por qué este estado?**\n\n{explicacion_estado}")


# ---------------------------------------------------------
# Card de métrica individual (MC-01, MC-02, MC-03, etc.)
# ---------------------------------------------------------

def render_metric_card(
    codigo: str,
    nombre: str,
    valor_porcentaje: str,
    numerador: int,
    denominador: int,
    descripcion_calculo: str,
    estado_texto: str = "",
) -> None:
    st.markdown(f"### {codigo} — {nombre}")
    st.metric(f"Resultado {codigo}", valor_porcentaje)

    st.markdown(
        f'<div class="metric-detail">'
        f'{numerador} de {denominador} {descripcion_calculo}.'
        f'{"<br><strong>Estado:</strong> " + estado_texto if estado_texto else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Sección de métricas (calidad o seguridad)
# ---------------------------------------------------------

def render_metric_section(titulo: str, metricas: list) -> None:
    st.markdown(f"### {titulo}")
    for metrica in metricas:
        render_metric_card(**metrica)
        st.divider()


# ---------------------------------------------------------
# Sección de hallazgos (correcciones, precisiones, oportunidades)
# ---------------------------------------------------------

def render_findings_section(
    correcciones: list,
    precisiones: list,
    oportunidades: list,
) -> None:
    panels = (
        (
            "Correcciones necesarias",
            correcciones,
            "finding-correction",
            "No se identificaron correcciones necesarias.",
        ),
        (
            "Precisiones necesarias",
            precisiones,
            "finding-precision",
            "No se identificaron precisiones necesarias.",
        ),
        (
            "Oportunidades de mejora",
            oportunidades,
            "finding-opportunity",
            "No se identificaron oportunidades adicionales.",
        ),
    )

    columns = st.columns(3)
    for index, (column, panel) in enumerate(zip(columns, panels)):
        title, items, css_class, empty_message = panel
        with column:
            # El conteo funciona como cabecera visual de cada categoría y el
            # detalle queda alineado inmediatamente debajo, en la misma columna.
            st.metric(title, len(items))
            if items:
                for item in items:
                    text = _texto_hallazgo_ui(item)
                    if text:
                        safe_text = escape(text).replace("\n", "<br>")
                        st.markdown(
                            f'<div class="finding-block {css_class}">{safe_text}</div>',
                            unsafe_allow_html=True,
                        )
            elif index == 0:
                st.success(empty_message)
            else:
                st.caption(empty_message)


# ---------------------------------------------------------
# Sección de trazabilidad (colapsable)
# ---------------------------------------------------------

def render_traceability_section(titulo: str, filas: list, columnas: list = None) -> None:
    with st.expander(titulo, expanded=False):
        if not filas:
            st.info("No hay datos de trazabilidad disponibles.")
            return
        if columnas:
            import pandas as pd
            df = pd.DataFrame(filas)
            columnas_disponibles = [col for col in columnas if col in df.columns]
            st.dataframe(
                df[columnas_disponibles] if columnas_disponibles else df,
                width="stretch",
                hide_index=True,
            )
        else:
            st.table(filas)


# ---------------------------------------------------------
# Sección de artefactos y acciones
# ---------------------------------------------------------

def render_artifact_actions(descargas: list) -> None:
    st.subheader("Artefactos generados")
    cols = st.columns(len(descargas))
    for col, descarga in zip(cols, descargas):
        with col:
            st.download_button(**descarga)


# ---------------------------------------------------------
# Retroalimentación de GitLab
# ---------------------------------------------------------

def render_gitlab_feedback(publicado: bool) -> None:
    if publicado:
        st.success("Retroalimentación publicada correctamente en GitLab.")
    else:
        st.warning("La retroalimentación no fue publicada en GitLab.")


# ---------------------------------------------------------
# Aviso de decisión humana
# ---------------------------------------------------------

def render_human_decision_notice(texto: str) -> None:
    st.info(texto)
