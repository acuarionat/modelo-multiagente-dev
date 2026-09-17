"""Panel del proyecto (dashboard) de SOLO LECTURA.

Agrega y presenta información relevante del proyecto a partir de la base de
seguimiento local (historial, versiones de matrices) y de GitLab (avance por
etapa y trazabilidad de las matrices TRZ). No modifica Issues, no publica
comentarios ni ejecuta análisis: únicamente lee y muestra.
"""

import statistics

import streamlit as st

from integrations.gitlab_adapter import (
    PENDING_LABEL,
    REVIEWED_LABEL,
    REWORK_LABEL,
    LEGACY_COMPLETED_LABELS,
    _normalizar_etiqueta,
)
from database.repository import obtener_historial, obtener_versiones_matrices

# Mismos milestones que MILESTONES_BY_STAGE en app.py. Se replican aquí para no
# importar app.py (que es el punto de entrada de Streamlit).
ETAPAS = (
    ("requerimientos", "Requerimientos", "Recepción de Requerimientos"),
    ("diseno", "Diseño", "Diseño"),
    ("codificacion", "Codificación", "Codificación"),
    ("pruebas", "Pruebas", "Pruebas"),
)

ESTADOS_FLUJO = ("Revisada", "Requiere modificación", "Pendiente", "Sin estado")


# ---------------------------------------------------------------------------
# Funciones puras (sin Streamlit ni GitLab) — fáciles de probar
# ---------------------------------------------------------------------------
def clasificar_estado_flujo(labels) -> str:
    """Traduce las etiquetas de un Issue al estado del ciclo de revisión."""
    norm = {_normalizar_etiqueta(label) for label in (labels or [])}
    completadas = {
        _normalizar_etiqueta(REVIEWED_LABEL),
        *(_normalizar_etiqueta(label) for label in LEGACY_COMPLETED_LABELS),
    }
    if norm & completadas:
        return "Revisada"
    if _normalizar_etiqueta(REWORK_LABEL) in norm:
        return "Requiere modificación"
    if _normalizar_etiqueta(PENDING_LABEL) in norm:
        return "Pendiente"
    return "Sin estado"


def resumir_historial(historial: list) -> dict:
    """Calcula promedios, distribución de veredictos y últimos datos del historial."""
    calidades = [h["quality_index"] for h in historial if isinstance(h.get("quality_index"), (int, float))]
    seguridades = [h["security_index"] for h in historial if isinstance(h.get("security_index"), (int, float))]
    tiempos = [h["execution_time"] for h in historial if isinstance(h.get("execution_time"), (int, float))]
    veredictos = {}
    for h in historial:
        etiqueta = (h.get("verdict") or "").strip() or "Sin veredicto"
        veredictos[etiqueta] = veredictos.get(etiqueta, 0) + 1
    return {
        "total_analisis": len(historial),
        "calidad_promedio": statistics.mean(calidades) if calidades else None,
        "seguridad_promedio": statistics.mean(seguridades) if seguridades else None,
        "tiempo_promedio": statistics.mean(tiempos) if tiempos else None,
        "veredictos": veredictos,
        "ultimo_analisis": historial[-1]["analysis_date"] if historial else None,
    }


def _pct(valor) -> str:
    """Formatea un índice 0..1 como porcentaje; '—' si no hay dato."""
    if valor is None:
        return "—"
    try:
        return f"{float(valor) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


# ---------------------------------------------------------------------------
# Recolección desde GitLab (con manejo de errores; nunca rompe el panel)
# ---------------------------------------------------------------------------
def recolectar_avance(adapter) -> dict:
    """Cuenta, por etapa, los Issues abiertos según su estado de revisión.
    Excluye los Issues de matriz (TRZ-xxx). Cada etapa se aísla: un error de
    GitLab en una etapa no impide mostrar las demás."""
    avance = {}
    for stage_id, _nombre, milestone in ETAPAS:
        try:
            issues = adapter.listar_issues_abiertos(milestone_title=milestone)
        except Exception as exc:
            avance[stage_id] = {"error": str(exc)}
            continue
        conteo = {estado: 0 for estado in ESTADOS_FLUJO}
        conteo["total"] = 0
        for issue in issues:
            titulo = str(getattr(issue, "title", "")).strip().upper()
            if titulo.startswith("TRZ"):
                continue
            estado = clasificar_estado_flujo(getattr(issue, "labels", []))
            conteo[estado] = conteo.get(estado, 0) + 1
            conteo["total"] += 1
        avance[stage_id] = conteo
    return avance


def recolectar_trazabilidad(project_id) -> dict:
    """Lee las matrices TRZ-002/003/004 desde GitLab y resume su cobertura.
    Cada etapa se aísla con try/except; si una matriz no existe, queda como None."""
    trazabilidad = {}

    def _seguro(getter, resumidor):
        try:
            _issue, filas = getter(project_id)
        except Exception:
            return None
        if not filas:
            return None
        try:
            resumen = resumidor(filas)
        except Exception:
            resumen = None
        return {"filas": len(filas), "resumen": resumen}

    try:
        from integrations.issue_service import (
            obtener_issue_matriz_trazabilidad_diseno,
            obtener_issue_matriz_trazabilidad_codificacion,
        )
        from integrations.testing_service import obtener_issue_matriz_trazabilidad_pruebas
        from core.design_traceability import resumir_trazabilidad_diseno
        from core.coding_traceability import resumir_trazabilidad_codificacion
        from core.testing_traceability import resumir_trazabilidad_pruebas
    except Exception:
        return trazabilidad

    trazabilidad["diseno"] = _seguro(obtener_issue_matriz_trazabilidad_diseno, resumir_trazabilidad_diseno)
    trazabilidad["codificacion"] = _seguro(obtener_issue_matriz_trazabilidad_codificacion, resumir_trazabilidad_codificacion)
    trazabilidad["pruebas"] = _seguro(obtener_issue_matriz_trazabilidad_pruebas, resumir_trazabilidad_pruebas)
    return trazabilidad


# ---------------------------------------------------------------------------
# Vista Streamlit
# ---------------------------------------------------------------------------
def render_dashboard(project_name: str, project_config: dict, adapter) -> None:
    st.header(f"Panel del proyecto — {project_name}")
    st.caption(
        "Vista de solo lectura: agrega información del proyecto desde la base de "
        "seguimiento local y GitLab. No modifica Issues ni ejecuta análisis."
    )

    if st.button("Actualizar datos de GitLab"):
        st.session_state.pop("dashboard_avance", None)
        st.session_state.pop("dashboard_trazabilidad", None)
        st.rerun()

    # ---- Datos locales (instantáneos) ----
    historial = obtener_historial()
    resumen = resumir_historial(historial)
    versiones = obtener_versiones_matrices()

    # ---- 1. Salud del proyecto ----
    st.subheader("Salud del proyecto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Versión de contexto", project_config.get("context_version", "—"))
    c2.metric("Análisis registrados", resumen["total_analisis"])
    c3.metric("Calidad promedio", _pct(resumen["calidad_promedio"]))
    c4.metric("Seguridad promedio", _pct(resumen["seguridad_promedio"]))
    linea_inferior = []
    if resumen["tiempo_promedio"] is not None:
        linea_inferior.append(f"Tiempo promedio por análisis: {resumen['tiempo_promedio']:.1f} s")
    if resumen["ultimo_analisis"]:
        linea_inferior.append(f"Último análisis registrado: {resumen['ultimo_analisis']}")
    if linea_inferior:
        st.caption(" · ".join(linea_inferior))

    st.divider()

    # ---- 2. Avance por etapa (GitLab) ----
    st.subheader("Avance por etapa")
    if "dashboard_avance" not in st.session_state:
        with st.spinner("Consultando Issues en GitLab..."):
            st.session_state["dashboard_avance"] = recolectar_avance(adapter)
    avance = st.session_state["dashboard_avance"]

    columnas = st.columns(len(ETAPAS))
    filas_grafico = {}
    for (stage_id, nombre, _milestone), columna in zip(ETAPAS, columnas):
        datos = avance.get(stage_id, {})
        with columna:
            st.markdown(f"**{nombre}**")
            if "error" in datos:
                st.warning("No disponible")
                st.caption(datos["error"])
                continue
            total = datos.get("total", 0)
            revisadas = datos.get("Revisada", 0)
            porcentaje = f"{(revisadas / total * 100):.0f}%" if total else "—"
            st.metric("Revisadas", f"{revisadas}/{total}", delta=porcentaje, delta_color="off")
            st.caption(
                f"Requiere modificación: {datos.get('Requiere modificación', 0)} · "
                f"Pendiente: {datos.get('Pendiente', 0)} · "
                f"Sin estado: {datos.get('Sin estado', 0)}"
            )
            filas_grafico[nombre] = {
                "Revisada": revisadas,
                "Requiere modificación": datos.get("Requiere modificación", 0),
                "Pendiente": datos.get("Pendiente", 0),
                "Sin estado": datos.get("Sin estado", 0),
            }

    if filas_grafico:
        try:
            import pandas as pd
            import altair as alt

            # El orden del eje X sigue el flujo del proyecto (Requerimientos →
            # Diseño → Codificación → Pruebas), no el alfabético que Streamlit
            # aplicaría por defecto.
            orden_etapas = [nombre for _sid, nombre, _m in ETAPAS if nombre in filas_grafico]
            df_avance = (
                pd.DataFrame(filas_grafico).T[list(ESTADOS_FLUJO)]
                .reset_index()
                .rename(columns={"index": "Etapa"})
                .melt(id_vars="Etapa", var_name="Estado", value_name="Cantidad")
            )
            grafico = (
                alt.Chart(df_avance)
                .mark_bar()
                .encode(
                    x=alt.X("Etapa:N", sort=orden_etapas, title="Etapa"),
                    y=alt.Y("Cantidad:Q", title="Issues"),
                    color=alt.Color("Estado:N", sort=list(ESTADOS_FLUJO), title="Estado"),
                    order=alt.Order("Estado:N"),
                )
            )
            st.altair_chart(grafico, use_container_width=True)
        except Exception:
            pass

    st.divider()

    # ---- 3. Tendencia de calidad y seguridad (historial) ----
    st.subheader("Tendencia de calidad y seguridad")
    if not historial:
        st.info("Aún no hay análisis registrados en el historial. Ejecuta al menos un análisis de Requerimientos.")
    else:
        try:
            import pandas as pd
            df_tendencia = pd.DataFrame(
                {
                    "Calidad": [h.get("quality_index") for h in historial],
                    "Seguridad": [h.get("security_index") for h in historial],
                }
            )
            df_tendencia.index = range(1, len(df_tendencia) + 1)
            df_tendencia.index.name = "Análisis"
            st.line_chart(df_tendencia)
            st.caption("Índices por análisis registrado (0 a 1). Los valores no evaluables se omiten.")
        except Exception:
            st.info("No se pudo generar la gráfica de tendencia.")

    st.divider()

    # ---- 4. Trazabilidad por matriz (GitLab) ----
    st.subheader("Trazabilidad por matriz")
    st.caption(
        "Cada matriz mide qué proporción de los elementos de la etapa anterior "
        "quedó cubierta por la etapa siguiente. Se lee en el orden del flujo: "
        "el **Diseño** cubre los **requisitos**, la **Codificación** implementa los "
        "**elementos de diseño** y las **Pruebas** verifican las **codificaciones**. "
        "El formato es siempre «cubiertos / total (porcentaje)»."
    )
    if "dashboard_trazabilidad" not in st.session_state:
        with st.spinner("Leyendo matrices de trazabilidad en GitLab..."):
            st.session_state["dashboard_trazabilidad"] = recolectar_trazabilidad(adapter.project_id)
    trazabilidad = st.session_state["dashboard_trazabilidad"]

    tz_col1, tz_col2, tz_col3 = st.columns(3)
    _render_trazabilidad_diseno(tz_col1, trazabilidad.get("diseno"))
    _render_trazabilidad_codificacion(tz_col2, trazabilidad.get("codificacion"))
    _render_trazabilidad_pruebas(tz_col3, trazabilidad.get("pruebas"))

    st.divider()

    # ---- 5. Versiones de las matrices de trazabilidad ----
    st.subheader("Versiones de las matrices de trazabilidad")
    if not versiones:
        st.info("Aún no se ha publicado ninguna matriz de trazabilidad.")
    else:
        nombres = {
            "requerimientos": "TRZ-001 · Requerimientos",
            "diseno": "TRZ-002 · Diseño",
            "codificacion": "TRZ-003 · Codificación",
            "pruebas": "TRZ-004 · Pruebas",
        }
        st.table(
            [
                {
                    "Matriz": nombres.get(v["stage"], v["stage"]),
                    "Versión": v["version"],
                    "Última modificación": v["updated_at"],
                }
                for v in versiones
            ]
        )


def _cobertura(cubiertos, total) -> str:
    """Formatea la cobertura como 'cubiertos / total (porcentaje)'."""
    try:
        cubiertos = int(cubiertos or 0)
        total = int(total or 0)
    except (TypeError, ValueError):
        return "—"
    if total <= 0:
        return f"{cubiertos} / 0"
    return f"{cubiertos} / {total} ({cubiertos / total * 100:.0f}%)"


def _render_trazabilidad_diseno(columna, datos) -> None:
    with columna:
        st.markdown("**Diseño (TRZ-002)**")
        st.caption("Requisitos cubiertos por el diseño")
        if not datos or not datos.get("resumen"):
            st.caption("No disponible")
            return
        r = datos["resumen"]
        cubiertos = r.get("cubiertos", 0)
        total = r.get("requisitos_totales", 0)
        st.metric("Requisitos con diseño", _cobertura(cubiertos, total))
        st.caption(f"{cubiertos} de {total} requisitos tienen diseño que los cubre.")
        st.caption(
            f"Pendientes: {r.get('pendientes_relacion', 0)} · "
            f"Requieren revisión: {r.get('requieren_revision', 0)} · "
            f"No evaluados: {r.get('no_evaluados', 0)}"
        )


def _render_trazabilidad_codificacion(columna, datos) -> None:
    with columna:
        st.markdown("**Codificación (TRZ-003)**")
        st.caption("Elementos de diseño implementados en código")
        if not datos or not datos.get("resumen"):
            st.caption("No disponible")
            return
        r = datos["resumen"]
        implementados = r.get("implementados", 0)
        total = r.get("elementos_diseno_totales", 0)
        st.metric("Elementos implementados", _cobertura(implementados, total))
        st.caption(f"{implementados} de {total} elementos de diseño están implementados en código.")
        st.caption(
            f"No confirmados: {r.get('no_confirmados', 0)} · "
            f"No evaluados: {r.get('no_evaluados', 0)}"
        )


def _render_trazabilidad_pruebas(columna, datos) -> None:
    with columna:
        st.markdown("**Pruebas (TRZ-004)**")
        st.caption("Codificaciones verificadas con pruebas")
        if not datos or not datos.get("resumen"):
            st.caption("No disponible")
            return
        r = datos["resumen"]
        verificadas = r.get("verificadas", 0)
        total = r.get("codificaciones_totales", 0)
        st.metric("Codificaciones verificadas", _cobertura(verificadas, total))
        st.caption(f"{verificadas} de {total} codificaciones fueron verificadas mediante pruebas.")
        st.caption(
            f"Con fallo pendiente: {r.get('con_fallo_pendiente', 0)} · "
            f"Pendientes de revisión: {r.get('pendientes_revision', 0)} · "
            f"No evaluadas: {r.get('no_evaluadas', 0)}"
        )
