"""
Vista de la etapa de Pruebas para app.py.

Regla de esta capa: orquestar y mostrar. No recalcula métricas, no
reconstruye trazabilidad, no llama manualmente a Central/Quality/Security.
Todo el cómputo real ya vive en core/graph.py (construir_grafo_pruebas),
core/testing_traceability.py, core/testing_validation.py,
core/testing_metrics.py, core/testing_context.py y core/testing_presentation.py
— este módulo solo los invoca y organiza sus resultados para Streamlit.
Reutiliza el mismo patrón visual que Diseño y Codificación
(core/ui_components.py): solo cambia el contenido.

No modifica ningún archivo de Requerimientos, Diseño ni Codificación:
recibe la Matriz de Trazabilidad — Etapa Codificación vigente desde
TRZ-003 (integrations/issue_service.py::obtener_issue_matriz_trazabilidad_codificacion).
"""

from core.graph import construir_grafo_pruebas
from core.testing_presentation import construir_presentacion_resultado_pruebas
from core.testing_traceability import (
    construir_filas_matriz_pruebas,
    resumir_trazabilidad_pruebas,
)
from core.testing_validation import validar_entrada_pruebas
from core.traceability_export import exportar_filas_xlsx
from core.ui_components import (
    chip_html,
    contar,
    create_stage_step_panels,
    crear_subsecciones_entrada,
    entrada_fila_html,
    kpi_strip_html,
    promedio_indices,
    render_evaluation_header,
    render_findings_section,
    render_gitlab_feedback,
    render_next_phase_button,
    render_stage_summary,
    rotulo_bloque_html,
    selector_resultados,
    tarjeta_estado_entrada_html,
    titulo_item,
)
from core.utils import (
    extraer_porcentaje,
    generar_documento_formal_pruebas_docx,
    generar_reporte_pruebas_pdf,
)
from database.repository import cargar_estado_etapa, guardar_estado_etapa, leer_version_matriz
from integrations.issue_service import (
    actualizar_etiqueta_resultado_tecnico,
    obtener_issue_matriz_trazabilidad_codificacion,
)
from integrations.testing_service import (
    crear_o_actualizar_issue_matriz_trazabilidad_pruebas,
    obtener_issues_pruebas,
    publicar_aviso_referencias_invalidas_pruebas,
    publicar_comentario_pruebas,
)
from datetime import datetime
import copy

SPRINT_CONTEXT_PRUEBAS = "Pruebas"


# ---------------------------------------------------------
# Preparación de datos (puras, sin Streamlit, testeables)
# ---------------------------------------------------------

def preparar_prevalidacion_pruebas(issues_pruebas: list, matriz_codificacion: list) -> dict:
    """Valida, sin recalcular, cada Issue PRU-xxx contra la matriz de Codificación vigente."""
    validaciones = {}
    for issue in issues_pruebas:
        prueba_id = issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"
        validaciones[prueba_id] = validar_entrada_pruebas(issue, matriz_codificacion)
    return validaciones


def construir_tabla_pruebas(issue_pruebas: dict) -> list:
    """Tabla unificada (ID, Tipo, Elemento, Resultado) combinando pruebas funcionales y de seguridad."""
    filas = []
    for prueba in issue_pruebas.get("pruebas_funcionales") or []:
        filas.append({
            "ID": prueba.get("id", ""), "Tipo": "Funcional",
            "Elemento": prueba.get("funcionalidad", ""),
            "Resultado": prueba.get("estado") or "No reconocido",
        })
    for prueba in issue_pruebas.get("pruebas_seguridad") or []:
        filas.append({
            "ID": prueba.get("id", ""), "Tipo": "Seguridad",
            "Elemento": prueba.get("prueba_realizada", ""),
            "Resultado": prueba.get("estado") or "No reconocido",
        })
    return filas


def _estado_metrica_texto(metrica: dict) -> str:
    estado = metrica.get("estado")
    if estado == "EVALUADO":
        return "CUMPLE" if metrica.get("cumple") else "NO CUMPLE"
    return estado


def _construir_presentacion(issue: dict, resultado_grafo: dict) -> dict:
    """Delega a construir_presentacion_resultado_pruebas() sin recalcular."""
    return construir_presentacion_resultado_pruebas(
        issue_pruebas=issue,
        contexto=resultado_grafo["testing_context"][0],
        central_result=resultado_grafo["testing_central_result"],
        quality_result=resultado_grafo["testing_quality_result"],
        security_result=resultado_grafo["testing_security_result"],
        evaluator_result=resultado_grafo["testing_evaluator_result"],
        testing_summary=resultado_grafo["testing_summary"],
    )


def _explicar_estado_pruebas(p: dict) -> str:
    estado = p.get("estado_orientativo", "REVISAR")

    if estado == "CORREGIR":
        return "El estado es CORREGIR porque al menos una métrica evaluada no supera el umbral del 80 %."
    if estado == "REVISAR":
        return (
            "El estado es REVISAR porque al menos una métrica quedó sin evidencia suficiente "
            "para juzgarla (no confundir con métricas legítimamente NO_APLICA)."
        )
    if estado == "APROBADO":
        return "Todas las métricas evaluables superan el umbral del 80 %."
    return (
        "La evaluación requiere revisión humana debido a un fallo técnico que impidió "
        "completar el análisis."
    )


def _indicador_general_pruebas(presentacion: dict, codigos: tuple[str, ...]):
    """Promedia solo métricas evaluadas para el indicador visual de la categoría."""
    valores = []
    metricas = presentacion.get("metricas") or {}
    for codigo in codigos:
        metrica = metricas.get(codigo) or {}
        valor = metrica.get("valor")
        if metrica.get("estado_calculo") == "EVALUADO" and isinstance(valor, (int, float)):
            valores.append(valor)
    return sum(valores) / len(valores) if valores else None


# ---------------------------------------------------------
# Vista Streamlit
# ---------------------------------------------------------

def render_testing_stage(project_name: str, project_config: dict, adapter) -> None:
    import streamlit as st

    session = st.session_state
    if "pruebas_resultados" not in session:
        persisted = cargar_estado_etapa("pruebas")
        session["pruebas_resultados"] = (persisted or {}).get("pruebas_resultados", {})
        if persisted:
            session["pruebas_matriz_snapshot"] = persisted.get("pruebas_matriz_snapshot")
            session["pruebas_matriz_snapshot_metadata"] = persisted.get("pruebas_matriz_snapshot_metadata")
            session["pruebas_issue_snapshot"] = persisted.get("pruebas_issue_snapshot")
    elif (
        session["pruebas_resultados"] and session.get("pruebas_matriz_snapshot")
        and cargar_estado_etapa("pruebas") is None
    ):
        # Resultados ya en memoria de una ejecución anterior a esta persistencia: respaldarlos ahora.
        guardar_estado_etapa("pruebas", {
            "pruebas_resultados": session["pruebas_resultados"],
            "pruebas_matriz_snapshot": session["pruebas_matriz_snapshot"],
            "pruebas_matriz_snapshot_metadata": session.get("pruebas_matriz_snapshot_metadata"),
            "pruebas_issue_snapshot": session.get("pruebas_issue_snapshot"),
        })
    session.setdefault("pruebas_matriz_confirmada", False)

    paso_entrada, paso_analisis, paso_resultados, step_key = create_stage_step_panels(
        "pruebas",
        bool(session["pruebas_resultados"]),
    )

    # ============================================================
    # A. Entradas: matriz de Codificación (TRZ-003) + Issues de Pruebas
    # ============================================================
    # La fase se ordena en un resumen de estado y dos subsecciones (pestañas).
    # Los contenedores se crean por adelantado y se rellenan cuando hay datos; la
    # lógica de carga y validación es la misma de siempre.

    sub = crear_subsecciones_entrada(paso_entrada, "Issues de Pruebas")

    sub.acciones.markdown(rotulo_bloque_html("Acciones sobre la matriz"), unsafe_allow_html=True)
    sub.acciones.caption(
        "La matriz de Pruebas se usa tal como la dejó Codificación (solo lectura): "
        "para modificarla, edítala en GitLab y presiona «Actualizar desde GitLab»."
    )
    col_actualizar, col_gitlab = sub.acciones.columns(2)
    actualizar_gitlab = col_actualizar.button(
        "Actualizar desde GitLab", icon=":material/refresh:", key="pruebas_actualizar_trz003", width="stretch",
    )
    if "pruebas_matriz_carga" not in session or actualizar_gitlab:
        with sub.avisos.spinner("Consultando TRZ-003 en GitLab..."):
            issue_trz003, matriz_trz003 = obtener_issue_matriz_trazabilidad_codificacion(adapter.project_id)
        if matriz_trz003 is not None:
            session["pruebas_matriz_carga"] = matriz_trz003
            session["pruebas_issue_trz003"] = issue_trz003
            session["pruebas_matriz_fuente"] = "GitLab — TRZ-003"
            session["pruebas_matriz_confirmada"] = False

    if "pruebas_matriz_carga" not in session:
        sub.avisos.info(
            "TRZ-003 no está disponible en GitLab todavía. Ejecute primero la etapa de "
            "Codificación para generarla."
        )
        sub.resumen_matriz.markdown(
            tarjeta_estado_entrada_html("Matriz de trazabilidad · Codificación", [chip_html("No disponible", "bad")]),
            unsafe_allow_html=True,
        )
        sub.resumen_issues.markdown(
            tarjeta_estado_entrada_html("Issues de Pruebas", [chip_html("Requiere la matriz", "muted")]),
            unsafe_allow_html=True,
        )
        return

    matriz_codificacion = session["pruebas_matriz_carga"]
    # Resumen de la matriz de entrada (mismos datos en todas las etapas:
    # Fuente vigente · Versión · Estado · Validación · Filas de la matriz). La etapa de
    # Pruebas usa la matriz heredada de Codificación (TRZ-003) tal cual, sin edición ni
    # recomparación local: por eso Estado y Validación son constantes.
    sub.resumen_matriz.markdown(
        tarjeta_estado_entrada_html(
            "Matriz de trazabilidad · Codificación",
            [
                chip_html("ORIGINAL", "ok"),
                chip_html("VÁLIDA", "ok"),
                chip_html(contar(len(matriz_codificacion), "fila", "filas"), "info"),
            ],
            meta=(
                f"{session.get('pruebas_matriz_fuente', 'GitLab — TRZ-003')} · "
                f"Versión {leer_version_matriz('codificacion') or 'No informada'}"
            ),
        ),
        unsafe_allow_html=True,
    )
    sub.tabla.dataframe(matriz_codificacion, width="stretch")

    issue_trz003 = session.get("pruebas_issue_trz003")
    if issue_trz003 is not None:
        col_gitlab.link_button("Ver TRZ-003 en GitLab", issue_trz003.web_url, icon=":material/open_in_new:", width="stretch")

    # ============================================================
    # Issues de Pruebas detectados
    # ============================================================

    if "pruebas_issues_detectados" not in session:
        with sub.tab_issues.spinner("Consultando Issues de Pruebas en GitLab..."):
            session["pruebas_issues_detectados"] = obtener_issues_pruebas(
                adapter.project_id, milestone_title="Pruebas",
            )
    issues_pruebas = session["pruebas_issues_detectados"]

    if sub.tab_issues.button(
        "Actualizar issues", icon=":material/refresh:", key="pruebas_actualizar_issues", width="content",
    ):
        session.pop("pruebas_issues_detectados", None)
        st.rerun()

    if not issues_pruebas:
        sub.resumen_issues.markdown(
            tarjeta_estado_entrada_html("Issues de Pruebas", [chip_html(contar(0, "detectado", "detectados"), "muted")]),
            unsafe_allow_html=True,
        )
        sub.tab_issues.info("No se encontraron Issues de Pruebas en el milestone.")
        return

    validaciones = preparar_prevalidacion_pruebas(issues_pruebas, matriz_codificacion)
    pruebas_validas = [
        issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"
        for issue in issues_pruebas
        if validaciones[issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"]["entrada_valida"]
    ]
    bloqueadas = [
        pid for pid, v in validaciones.items() if not v["entrada_valida"]
    ]

    sub.resumen_issues.markdown(
        tarjeta_estado_entrada_html("Issues de Pruebas", [
            chip_html(contar(len(issues_pruebas), "detectado", "detectados"), "info"),
            chip_html(contar(len(pruebas_validas), "válido", "válidos"), "ok"),
            chip_html(contar(len(bloqueadas), "bloqueado", "bloqueados"), "bad" if bloqueadas else "muted"),
        ]),
        unsafe_allow_html=True,
    )

    # Cada entrada se muestra con su estado de revisión en GitLab (Pendiente o
    # Requiere modificación) junto a la validez de su entrada.
    for issue in issues_pruebas:
        prueba_id = issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"
        validacion = validaciones[prueba_id]
        icono = "🟢" if validacion["entrada_valida"] else "🔴"
        sub.tab_issues.markdown(
            entrada_fila_html(f"{icono} {prueba_id}", validacion["estado"], issue.get("labels")),
            unsafe_allow_html=True,
        )
        if validacion["campos_faltantes"]:
            sub.tab_issues.caption(f"Campos faltantes: {', '.join(validacion['campos_faltantes'])}")
        if validacion["referencias_invalidas"]:
            sub.tab_issues.caption(
                f"Codificaciones inexistentes en TRZ-003: {', '.join(validacion['referencias_invalidas'])}"
            )

    render_next_phase_button(paso_entrada, step_key, 1)

    # ============================================================
    # C. Ejecución del análisis
    # ============================================================

    paso_analisis.markdown("### Ejecución del análisis")

    session["pruebas_matriz_confirmada"] = paso_analisis.checkbox(
        "Confirmo que la Matriz de Trazabilidad — Etapa Codificación mostrada corresponde a la "
        "versión vigente que debe considerarse en la etapa de Pruebas.",
        value=session["pruebas_matriz_confirmada"], key="pruebas_matriz_confirmada_check",
    )

    puede_ejecutar = session["pruebas_matriz_confirmada"] and bool(pruebas_validas)
    ejecutar = paso_analisis.button(
        "Iniciar análisis de Pruebas", icon=":material/play_arrow:", type="primary",
        disabled=not puede_ejecutar, key="pruebas_ejecutar",
    )
    if ejecutar:
        matriz_snapshot = copy.deepcopy(matriz_codificacion)
        metadata_matriz = {"fuente": session.get("pruebas_matriz_fuente", "GitLab — TRZ-003")}
        session["pruebas_matriz_snapshot"] = matriz_snapshot
        session["pruebas_matriz_snapshot_metadata"] = metadata_matriz
        session["pruebas_issue_snapshot"] = copy.deepcopy(issues_pruebas)

        grafo = construir_grafo_pruebas()
        for prueba_id in pruebas_validas:
            with paso_analisis.spinner(f"Ejecutando el análisis multiagente para {prueba_id}..."):
                issue = next(
                    i for i in issues_pruebas
                    if (i.get("prueba_id") or f"issue-{i.get('issue_iid')}") == prueba_id
                )
                initial_state = {
                    "project_name": project_name,
                    "sprint_context": SPRINT_CONTEXT_PRUEBAS,
                    "testing_issues": [issue],
                    "testing_input_matrix": matriz_snapshot,
                    "testing_input_matrix_metadata": metadata_matriz,
                }
                session["pruebas_resultados"][prueba_id] = grafo.invoke(initial_state)
        # Issues bloqueadas por codificaciones inexistentes: no se analizan, pero se
        # deja constancia en GitLab (comentario + etiqueta 'Requiere modificación').
        avisos_publicados = session.setdefault("pruebas_avisos_referencias_publicados", set())
        for issue in issues_pruebas:
            prueba_id = issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"
            referencias_invalidas = validaciones[prueba_id]["referencias_invalidas"]
            if not referencias_invalidas or prueba_id in avisos_publicados:
                continue
            try:
                publicar_aviso_referencias_invalidas_pruebas(
                    adapter.project_id, issue.get("issue_iid"), prueba_id, referencias_invalidas, adapter=adapter,
                )
                avisos_publicados.add(prueba_id)
                paso_analisis.info(
                    f"{prueba_id}: no analizado por codificaciones inexistentes "
                    f"({', '.join(referencias_invalidas)}). Aviso publicado en GitLab."
                )
            except Exception as exc:
                paso_analisis.warning(
                    f"No se pudo publicar el aviso de codificaciones inexistentes para "
                    f"{prueba_id} en GitLab: {exc}"
                )
        guardar_estado_etapa("pruebas", {
            "pruebas_resultados": session["pruebas_resultados"],
            "pruebas_matriz_snapshot": session["pruebas_matriz_snapshot"],
            "pruebas_matriz_snapshot_metadata": session["pruebas_matriz_snapshot_metadata"],
            "pruebas_issue_snapshot": session["pruebas_issue_snapshot"],
        })
        paso_analisis.success(f"Análisis completado para: {', '.join(pruebas_validas)}.")

    render_next_phase_button(paso_analisis, step_key, 2)

    # ============================================================
    # D. Resultados y artefactos
    # ============================================================

    resultados = session["pruebas_resultados"]
    if not resultados:
        paso_resultados.info("Ejecuta el análisis para ver resultados.")
        return

    paso_resultados.divider()
    issues_por_id = {
        (issue.get("prueba_id") or f"issue-{issue.get('issue_iid')}"): issue
        for issue in session.get("pruebas_issue_snapshot", issues_pruebas)
    }
    presentaciones = {
        prueba_id: _construir_presentacion(issues_por_id[prueba_id], resultado_grafo)
        for prueba_id, resultado_grafo in resultados.items()
        if prueba_id in issues_por_id
    }

    testing_summaries = [resultado_grafo["testing_summary"] for resultado_grafo in resultados.values()]
    matriz_para_trazabilidad = session.get("pruebas_matriz_snapshot", matriz_codificacion)
    filas_matriz = construir_filas_matriz_pruebas(matriz_para_trazabilidad, testing_summaries)
    resumen_trazabilidad = resumir_trazabilidad_pruebas(filas_matriz)

    hubo_error_global = any(
        resultado.get("testing_summary", {}).get("estado_orientativo") == "ERROR"
        for resultado in resultados.values()
    )
    if ejecutar and filas_matriz and not hubo_error_global:
        crear_o_actualizar_issue_matriz_trazabilidad_pruebas(
            project_id=adapter.project_id,
            filas_matriz=filas_matriz,
            metadata=session.get("pruebas_matriz_snapshot_metadata"),
        )

    # Tras el análisis, actualizar automáticamente la etiqueta de flujo de cada
    # Issue de Pruebas evaluado (Revisada / Requiere modificación). Los estados
    # ERROR no modifican la etiqueta. El comentario de retroalimentación también
    # se publica automáticamente en GitLab (sin botón).
    if ejecutar:
        for prueba_id, p in presentaciones.items():
            if p["estado_orientativo"] == "ERROR":
                continue
            actualizar_etiqueta_resultado_tecnico(
                adapter.project_id, p["issue_iid"], p["estado_orientativo"], adapter=adapter,
            )
            try:
                publicar_comentario_pruebas(
                    adapter.project_id, p["issue_iid"], resultados[prueba_id]["testing_summary"],
                    adapter=adapter,
                )
                session[f"pruebas_publicado_{prueba_id}"] = True
            except Exception as exc:
                session[f"pruebas_publicado_{prueba_id}"] = False
                st.warning(f"{prueba_id}: no se pudo publicar la retroalimentación en GitLab ({exc}).")

    resumen_general, detalle_resultados, artefactos = paso_resultados.tabs(
        ["Resumen general", "Detalle por prueba", "Matriz y documentos"]
    )

    total_pruebas = len(presentaciones)
    requieren_correccion = sum(
        1 for p in presentaciones.values() if p.get("estado_orientativo") == "CORREGIR"
    )
    con_error = sum(
        1 for p in presentaciones.values() if p.get("estado_orientativo") == "ERROR"
    )
    render_stage_summary(
        resumen_general,
        etiqueta_items="Pruebas evaluadas",
        total_items=total_pruebas,
        requieren_correccion=requieren_correccion,
        con_error=con_error,
        calidad_promedio=promedio_indices(
            _indicador_general_pruebas(p, ("MC-07", "MC-08")) for p in presentaciones.values()
        ),
        seguridad_promedio=promedio_indices(
            _indicador_general_pruebas(p, ("MS-08", "MS-09")) for p in presentaciones.values()
        ),
        aviso=(
            "Los resultados constituyen apoyo al control y seguimiento de las pruebas. "
            "La aceptación final requiere revisión humana."
        ),
    )

    elegido = selector_resultados(
        detalle_resultados, "pruebas",
        [(identificador, pres["estado_orientativo"]) for identificador, pres in presentaciones.items()],
    )
    for prueba_id, p in presentaciones.items():
        if prueba_id != elegido:
            continue
        resultado_grafo = resultados[prueba_id]
        expander_title = titulo_item(p['prueba_id'], p['titulo'], p['estado_orientativo'])

        # Un resultado a la vez (selector de arriba): evita una página larga en vertical.
        with detalle_resultados.container(border=True):
            st.markdown(f"### {expander_title}")
            render_evaluation_header(
                titulo="Resultado de evaluación asistida",
                estado=p["estado_orientativo"],
                indice_calidad=extraer_porcentaje(_indicador_general_pruebas(p, ("MC-07", "MC-08"))),
                indice_seguridad=extraer_porcentaje(_indicador_general_pruebas(p, ("MS-08", "MS-09"))),
                explicacion_estado=_explicar_estado_pruebas(p),
            )

            tab_resumen, tab_calidad, tab_seguridad, tab_formalizacion = st.tabs(
                ["Resumen", "Calidad", "Seguridad", "Formalización"]
            )

            with tab_resumen:
                render_findings_section(
                    p["correcciones_necesarias"],
                    p["precisiones_necesarias"],
                    p["oportunidades_mejora"],
                )

                st.markdown("#### Retroalimentación")
                if p["estado_orientativo"] == "ERROR":
                    st.caption("No se publica retroalimentación cuando existe error técnico.")
                else:
                    render_gitlab_feedback(bool(session.get(f"pruebas_publicado_{prueba_id}")))

            with tab_calidad:
                mc07 = p["metricas"]["MC-07"]
                mc08 = p["metricas"]["MC-08"]
                with st.expander(f"{mc07['codigo']} — {mc07['nombre']} · {extraer_porcentaje(mc07['valor'])}", expanded=False):
                    st.metric(f"Resultado {mc07['codigo']}", extraer_porcentaje(mc07["valor"]))
                    st.markdown(f"**Qué mide esta métrica:**\n\n{mc07['que_mide']}")
                    st.markdown("**Funcionalidades con brecha:**")
                    for item in mc07.get("funcionalidades_con_brecha", []):
                        st.markdown(f"- **{item.get('funcionalidad', '')}**: {item.get('explicacion', '')}")
                    st.markdown(f"**Resultado:** {mc07['resultado']}")
                    if mc07.get("conclusion"):
                        st.markdown(mc07["conclusion"])

                with st.expander(f"{mc08['codigo']} — {mc08['nombre']} · {extraer_porcentaje(mc08['valor'])}", expanded=False):
                    st.metric(f"Resultado {mc08['codigo']}", extraer_porcentaje(mc08["valor"]))
                    st.caption(
                        f"Fallos detectados/corregidos/verificados: "
                        f"{mc08.get('fallos_detectados')}/{mc08.get('fallos_corregidos')}/{mc08.get('fallos_corregidos_verificados')}"
                    )
                    st.markdown(f"**Qué mide esta métrica:**\n\n{mc08['que_mide']}")
                    st.markdown("**Fallos pendientes:**")
                    for item in mc08.get("fallos_pendientes", []):
                        st.markdown(f"- **{item.get('fallo', '')}**: {item.get('explicacion', '')}")
                    st.markdown(f"**Resultado:** {mc08['resultado']}")
                    if mc08.get("conclusion"):
                        st.markdown(mc08["conclusion"])

            with tab_seguridad:
                ms08 = p["metricas"]["MS-08"]
                ms09 = p["metricas"]["MS-09"]
                with st.expander(f"MS-08 — {ms08['nombre']} · {extraer_porcentaje(ms08['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms08['codigo']}", extraer_porcentaje(ms08["valor"]))
                    st.markdown(f"**Qué mide esta métrica:**\n\n{ms08['que_mide']}")
                    st.markdown("**Controles no verificados:**")
                    for item in ms08.get("controles_no_verificados", []):
                        st.markdown(f"- **{item.get('control', '')}**: {item.get('explicacion', '')}")
                    st.markdown(f"**Resultado:** {ms08['resultado']}")
                    if ms08.get("conclusion"):
                        st.markdown(ms08["conclusion"])

                with st.expander(f"MS-09 — {ms09['nombre']} · {extraer_porcentaje(ms09['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms09['codigo']}", extraer_porcentaje(ms09["valor"]))
                    st.markdown(f"**Qué mide esta métrica:**\n\n{ms09['que_mide']}")
                    st.markdown("**Pruebas fallidas:**")
                    for item in ms09.get("pruebas_fallidas", []):
                        st.markdown(f"- **{item.get('prueba_realizada', '')}**: {item.get('explicacion', '')}")
                    st.markdown(f"**Resultado:** {ms09['resultado']}")
                    if ms09.get("conclusion"):
                        st.markdown(ms09["conclusion"])

            with tab_formalizacion:
                if p.get("recomendacion_revision"):
                    st.markdown("#### Recomendación de revisión")
                    st.markdown(p["recomendacion_revision"])

                st.markdown("#### Trazabilidad heredada de esta Prueba")
                trazabilidad = p.get("trazabilidad", {})
                if trazabilidad:
                    for codificacion_id, datos in trazabilidad.items():
                        st.markdown(f"**{codificacion_id}**")
                        st.markdown(f"- Elementos de Diseño: {', '.join(datos.get('elementos_diseno', [])) or 'Ninguno.'}")
                        st.markdown(f"- Requisitos: {', '.join(datos.get('requisitos', [])) or 'Ninguno.'}")
                        st.markdown(f"- Historias: {', '.join(datos.get('historias', [])) or 'Ninguna.'}")
                else:
                    st.info("Sin trazabilidad heredada resuelta.")

    # ---- Matriz de Trazabilidad de la etapa ----
    with artefactos.expander("Matriz de Trazabilidad de la etapa — Pruebas", expanded=False):
        import pandas as pd
        columnas_trz = [
            "HU origen", "Código requisito", "Tipo", "Nombre del requisito",
            "Descripción", "Diseño", "Elementos de Diseño",
            "Estado de trazabilidad", "Estado de Diseño",
            "Codificación", "Estado de implementación", "Ubicación de implementación",
            "Estado de Codificación", "Observación de Codificación",
            "Pruebas", "Estado de Pruebas", "Observación de Pruebas",
        ]
        df = pd.DataFrame(filas_matriz)
        columnas_disponibles = [col for col in columnas_trz if col in df.columns]
        st.dataframe(df[columnas_disponibles] if columnas_disponibles else df, width="stretch", hide_index=True)

        fecha = datetime.now().strftime("%Y%m%d")
        exportar_filas_xlsx(
            filas_matriz, f"output/xlsx/matriz_pruebas_{fecha}.xlsx",
            nombre_hoja="Trazabilidad Pruebas", resumen=resumen_trazabilidad,
        )
        with open(f"output/xlsx/matriz_pruebas_{fecha}.xlsx", "rb") as handle:
            st.download_button(
                "Descargar matriz (Excel)", handle.read(),
                file_name="matriz_pruebas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    # ---- Documentos consolidados ----
    artefactos.subheader("Documentos consolidados")
    # Copia para no mutar el metadata de la sesión. Versión propia = matriz de
    # Pruebas (TRZ-004); versión de entrada = matriz de Codificación heredada
    # (TRZ-003). Ambas provienen del registro de versiones de matrices.
    matriz_metadata_documentos = dict(session.get("pruebas_matriz_snapshot_metadata", {}) or {})
    matriz_metadata_documentos["matriz_trazabilidad_version"] = leer_version_matriz("pruebas") or "No informada"
    matriz_metadata_documentos["matriz_entrada_version"] = leer_version_matriz("codificacion") or "No informada"
    lista_presentaciones = list(presentaciones.values())

    pdf_bytes = generar_reporte_pruebas_pdf(
        project_name, "Pruebas", lista_presentaciones, resumen_trazabilidad, matriz_metadata_documentos,
    )
    docx_bytes = generar_documento_formal_pruebas_docx(
        project_name, "Pruebas", lista_presentaciones, matriz_metadata_documentos,
        filas_trazabilidad=filas_matriz,
    )

    col_pdf, col_docx = artefactos.columns(2)

    with col_pdf:
        st.markdown("### Reporte Ejecutivo")
        st.caption(
            "Presenta métricas, interpretaciones, brechas y recomendaciones "
            "de la evaluación de las Pruebas."
        )
        st.download_button(
            "Descargar Reporte Ejecutivo", pdf_bytes.getvalue(),
            file_name="reporte_pruebas.pdf", mime="application/pdf",
            width="stretch",
        )

    with col_docx:
        st.markdown("### Documento Formal")
        st.caption(
            "Formaliza las pruebas realizadas, los resultados obtenidos, los fallos y su "
            "verificación, los controles de seguridad, las evidencias, los aspectos "
            "pendientes y la trazabilidad final."
        )
        st.download_button(
            "Descargar Documento Formal", docx_bytes.getvalue(),
            file_name="documento_formal_pruebas.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
