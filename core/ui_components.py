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
# Navegación interna de una etapa
# ---------------------------------------------------------

def create_stage_step_panels(stage_prefix: str, resultados_presentes: bool = False):
    """Crea las tres vistas progresivas comunes sin alterar su contenido.

    El panel abierto se rastrea con un único índice en `st.session_state`
    (`<stage_prefix>_active_step`), recalculado en cada ejecución igual que
    antes lo hacía `resultados_presentes`. Esto permite que
    `render_next_phase_button` avance de panel sin depender del `key` nativo
    de `st.expander`, que no admite reabrirse/cerrarse por programación.
    """
    step_key = f"{stage_prefix}_active_step"
    if step_key not in st.session_state:
        st.session_state[step_key] = 2 if resultados_presentes else 0
    elif resultados_presentes:
        st.session_state[step_key] = 2
    active_step = st.session_state[step_key]

    paso_entrada = st.expander("A. Revisión de entradas", expanded=active_step == 0)
    paso_analisis = st.expander("B. Ejecución del análisis", expanded=active_step == 1)
    paso_resultados = st.expander("C. Resultados y artefactos", expanded=active_step == 2)
    return paso_entrada, paso_analisis, paso_resultados, step_key


def create_coding_step_panels(stage_prefix: str, resultados_presentes: bool = False):
    """Crea la navegación progresiva propia de la etapa de Codificación.

    Ver `create_stage_step_panels` para el propósito del índice de paso activo.
    """
    step_key = f"{stage_prefix}_active_step"
    if step_key not in st.session_state:
        st.session_state[step_key] = 3 if resultados_presentes else 0
    elif resultados_presentes:
        st.session_state[step_key] = 3
    active_step = st.session_state[step_key]

    paso_entrada = st.expander("A. Entrada de codificación", expanded=active_step == 0)
    paso_repositorio = st.expander("B. Información técnica del repositorio", expanded=active_step == 1)
    paso_analisis = st.expander("C. Ejecución del análisis", expanded=active_step == 2)
    paso_resultados = st.expander("D. Resultados y artefactos", expanded=active_step == 3)
    return paso_entrada, paso_repositorio, paso_analisis, paso_resultados, step_key


# ---------------------------------------------------------
# Navegación entre fases (botón discreto de avance)
# ---------------------------------------------------------

def render_next_phase_button(
    container,
    step_key: str,
    target_step: int,
    label: str = "Siguiente fase →",
) -> None:
    """Botón discreto que cierra el panel actual y abre el siguiente.

    Solo afecta el estado visual (abierto/cerrado) de los expanders creados por
    `create_stage_step_panels` / `create_coding_step_panels`; no altera datos ni
    lógica de la etapa.
    """
    container.divider()
    _, col_button = container.columns([5, 1.4])
    if col_button.button(
        label,
        key=f"next_phase__{step_key}__{target_step}",
        width="stretch",
    ):
        st.session_state[step_key] = target_step
        st.rerun()


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
# Resumen general de la etapa (mismo formato en todas las etapas)
# ---------------------------------------------------------

def _formatear_promedio(valor) -> str:
    """Formatea un índice promedio 0..1 como porcentaje; 'No evaluado' si no hay dato."""
    if isinstance(valor, (int, float)):
        return f"{round(valor * 100)} %"
    return "No evaluado"


def promedio_indices(valores) -> float:
    """Promedia solo los valores numéricos de una colección (ignora None/no numéricos)."""
    numericos = [v for v in (valores or []) if isinstance(v, (int, float))]
    return sum(numericos) / len(numericos) if numericos else None


def render_stage_summary(
    container,
    *,
    etiqueta_items: str,
    total_items: int,
    requieren_correccion: int,
    con_error: int,
    calidad_promedio,
    seguridad_promedio,
    aviso: str,
    subtitulo: str = "",
) -> None:
    """Resumen general homogéneo para todas las etapas.

    Primera fila: conteos (ítems evaluados · requieren corrección · con error).
    Segunda fila: porcentajes promedio de la etapa (calidad y seguridad).
    Cierra con el aviso de decisión humana. Solo presentación: no recalcula.
    """
    container.subheader("Resumen general de resultados")
    if subtitulo:
        container.caption(subtitulo)

    fila_conteos = container.columns(3)
    fila_conteos[0].metric(etiqueta_items, total_items)
    fila_conteos[1].metric("Requieren corrección", requieren_correccion)
    fila_conteos[2].metric("Con error", con_error)

    fila_promedios = container.columns(2)
    fila_promedios[0].metric("Calidad promedio", _formatear_promedio(calidad_promedio))
    fila_promedios[1].metric("Seguridad promedio", _formatear_promedio(seguridad_promedio))

    with container:
        render_human_decision_notice(aviso)


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
