"""
Vista de la etapa de Codificación para app.py.

Regla de esta capa: orquestar y mostrar. No recalcula métricas, no
reconstruye trazabilidad, no llama manualmente a Central/Quality/Security.
Todo el cómputo real ya vive en core/graph.py (construir_grafo_codificacion),
core/coding_traceability.py, core/coding_matrix_input.py, core/coding_metrics.py,
core/coding_context.py, integrations/code_repository_service.py y
core/utils.py — este módulo solo los invoca y organiza sus resultados para
Streamlit. Reutiliza exactamente los mismos componentes visuales que
Diseño (core/ui_components.py): solo cambia el contenido.

No modifica ningún archivo de Requerimientos ni de Diseño: recibe la matriz
de Diseño vigente desde TRZ-002 o desde una carga de Excel.
"""

import copy
from datetime import datetime

from core.code_analysis.orchestrator import obtener_evidencia_por_metrica
from core.coding_context import construir_contexto_codificacion
from core.coding_contract import validar_entrada_codificacion
from core.coding_matrix_input import (
    ESTADO_MATRIZ_INVALIDA,
    extraer_elementos_diseno_validos,
    preparar_matriz_entrada_codificacion,
)
from core.coding_presentation import construir_presentacion_resultado_codificacion
from core.coding_traceability import (
    construir_filas_matriz_codificacion,
    resumir_trazabilidad_codificacion,
)
from core.graph import construir_grafo_codificacion
from core.traceability_export import exportar_filas_xlsx, importar_matriz_csv, importar_matriz_xlsx
from core.ui_components import (
    chip_html,
    contar,
    create_coding_step_panels,
    crear_subsecciones_entrada,
    entrada_fila_html,
    fila_matriz_resultados,
    filas_metricas_presentacion,
    kpi_strip_html,
    promedio_indices,
    render_alcance_entradas,
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
from core.document_style import FORMAL, REPORTE, nombre_archivo
from core.utils import (
    extraer_porcentaje,
    generar_documento_formal_codificacion_docx,
    generar_reporte_codificacion_pdf,
)
from database.repository import cargar_estado_etapa, guardar_estado_etapa, guardar_historial, leer_version_matriz
from integrations.code_repository_service import obtener_codigo_codificacion
from integrations.gitlab_adapter import etiquetas_son_analizables
from integrations.issue_service import (
    actualizar_etiqueta_resultado_tecnico,
    crear_o_actualizar_issue_matriz_trazabilidad_codificacion,
    obtener_issue_matriz_trazabilidad_diseno,
    obtener_issues_codificacion,
    publicar_aviso_referencias_invalidas_codificacion,
    publicar_comentario_codificacion,
)
from agents.coding_repository_discovery import (
    nodo_coding_repository_discovery,
    nodo_coding_detect_technologies,
    nodo_coding_select_tools,
    nodo_coding_validate_and_contextualize,
)

SPRINT_CONTEXT_CODIFICACION = "Codificación"


# ---------------------------------------------------------
# Preparación de datos (puras, sin Streamlit, testeables)
# ---------------------------------------------------------

def preparar_prevalidacion_codificacion(matriz_entrada: list, contextos_por_cod_id: dict) -> dict:
    """Agrega, sin recalcular, las validaciones ya producidas por validar_entrada_codificacion para cada Issue."""
    codigos_validos = []
    codigos_bloqueados = []

    for codificacion_id, validacion in contextos_por_cod_id.items():
        if validacion["entrada_valida"]:
            codigos_validos.append(codificacion_id)
        else:
            codigos_bloqueados.append(codificacion_id)

    return {
        "elementos_diseno_vigentes": len(extraer_elementos_diseno_validos(matriz_entrada)),
        "issues_validos": sorted(codigos_validos),
        "issues_bloqueados": sorted(codigos_bloqueados),
    }


def preparar_estado_entrada_codificacion(issues_codificacion: list, elementos_diseno_validos: set) -> dict:
    """Estado de entrada por Issue COD, calculado una sola vez con validar_entrada_codificacion."""
    filas = []
    validaciones = {}
    for issue in issues_codificacion:
        codificacion_id = issue.get("codificacion_id") or f"issue-{issue.get('issue_iid')}"
        validacion = validar_entrada_codificacion(issue, elementos_diseno_validos)
        validaciones[codificacion_id] = validacion
        filas.append({
            "codificacion_id": codificacion_id,
            "issue_iid": issue.get("issue_iid"),
            "titulo": issue.get("titulo", ""),
            "entrada_valida": validacion["entrada_valida"],
            "estado_entrada": validacion["estado"],
            "campos_faltantes": validacion["campos_faltantes"],
            "referencias_invalidas": validacion["referencias_invalidas"],
        })
    return {"filas": filas, "validaciones": validaciones}


def _estado_herramientas_texto(evidencia_herramientas: dict) -> str:
    etiquetas = {"OK": "✓", "NO_APLICA": "—", "ERROR": "✗"}
    partes = []
    for nombre in ("radon", "semgrep", "pip_audit", "gitleaks"):
        estado = (evidencia_herramientas.get(nombre) or {}).get("estado", "?")
        partes.append(f"{nombre} {etiquetas.get(estado, '?')}")
    return " · ".join(partes)


def _render_evidencia_tecnica(evidencia_herramientas: dict) -> None:
    import streamlit as st

    def _icono_estado(estado: str) -> str:
        if estado == "OK":
            return "OK"
        if estado == "NO_APLICA":
            return "NO_APLICA"
        return "ERROR"

    evidencia_por_metrica = obtener_evidencia_por_metrica(evidencia_herramientas)
    mc05 = evidencia_por_metrica["MC-05"] or {}
    ms05 = evidencia_por_metrica["MS-05"] or {}
    ms06 = evidencia_por_metrica["MS-06"] or {}
    ms07 = evidencia_por_metrica["MS-07"] or {}

    mc05_funciones = len((mc05.get("datos") or {}).get("funciones", []))
    ms05_hallazgos = (ms05.get("datos") or {}).get("hallazgos", [])
    ms05_criticos = sum(1 for hallazgo in ms05_hallazgos if hallazgo.get("critico"))
    ms06_dependencias = (ms06.get("datos") or {}).get("dependencias", [])
    ms06_vulnerables = sum(1 for dependencia in ms06_dependencias if dependencia.get("segura") is False)
    ms07_archivos_con_secretos = ms07.get("total_archivos_con_secretos", 0)
    ms07_secretos = ms07.get("secretos_detectados", 0)

    with st.expander("Evidencia técnica utilizada", expanded=False):
        md = (
            "| Métrica | Herramienta | Estado | Detalle |\n"
            "|---|---|---|---|\n"
            f"| MC-05 | {mc05.get('herramienta', '—')} | {_icono_estado(mc05.get('estado', '?'))} | {mc05_funciones} funciones analizadas |\n"
            f"| MS-05 | {ms05.get('herramienta', '—')} | {_icono_estado(ms05.get('estado', '?'))} | {len(ms05_hallazgos)} hallazgos · {ms05_criticos} críticos |\n"
            f"| MS-06 | {ms06.get('herramienta', '—')} | {_icono_estado(ms06.get('estado', '?'))} | {len(ms06_dependencias)} dependencias analizadas · {ms06_vulnerables} con vulnerabilidades |\n"
            f"| MS-07 | {ms07.get('herramienta', '—')} | {_icono_estado(ms07.get('estado', '?'))} | {ms07_archivos_con_secretos} archivos con secretos · {ms07_secretos} secretos detectados |\n"
        )
        st.markdown(md)


def _construir_presentacion(resultado_grafo: dict, filas_matriz: list) -> dict:
    """Delega a construir_presentacion_resultado_codificacion() sin recalcular."""
    return construir_presentacion_resultado_codificacion(
        contexto=resultado_grafo["coding_context"][0],
        central_result=resultado_grafo["coding_central_result"],
        quality_result=resultado_grafo["coding_quality_result"],
        security_result=resultado_grafo["coding_security_result"],
        evaluator_result=resultado_grafo["coding_evaluator_result"],
        coding_summary=resultado_grafo["coding_summary"],
        trazabilidad_filas=filas_matriz,
    )


def _explicar_estado_codificacion(p: dict) -> str:
    estado = p.get("estado_orientativo", "REVISIÓN HUMANA")
    q = extraer_porcentaje(p.get("indice_calidad"))
    s = extraer_porcentaje(p.get("indice_seguridad"))

    if estado == "CORREGIR":
        return (
            "El estado es CORREGIR porque al menos un índice evaluado no supera "
            f"el umbral del 80 % (Calidad {q}, Seguridad {s})."
        )
    if estado == "CONFORME CON MEJORAS":
        return (
            f"Los índices evaluados superan el umbral del 80 % (Calidad {q}, Seguridad {s}), "
            "pero existen hallazgos u oportunidades adicionales que "
            "pueden fortalecer la implementación."
        )
    if estado == "CONFORME":
        return (
            f"Los índices evaluados superan el umbral del 80 % (Calidad {q}, Seguridad {s}) "
            "y no se identificaron hallazgos adicionales."
        )
    return (
        "La evaluación requiere revisión humana debido a evidencia "
        "insuficiente o a condiciones que no pudieron resolverse automáticamente."
    )


# ---------------------------------------------------------
# Vista Streamlit
# ---------------------------------------------------------

def descubrir_y_perfilar_repositorio(adapter, state: dict) -> dict:
    """Ejecuta el pipeline de descubrimiento del repositorio.

    Encadena los nodos:
    1. Descubrimiento automático
    2. Detección de tecnologías
    3. Selección de herramientas
    4. Validación y contextualización

    Sin ejecutar herramientas aún.
    """
    state = nodo_coding_repository_discovery(adapter, state)
    state = nodo_coding_detect_technologies(adapter, state)
    state = nodo_coding_select_tools(state)
    state = nodo_coding_validate_and_contextualize(state)
    return state


def render_coding_repository_info(session, adapter) -> None:
    """Muestra información técnica del repositorio descubierto."""
    import streamlit as st

    st.markdown("### Información técnica del repositorio")

    ya_analizado = "coding_repository_profile" in session
    etiqueta_boton = "Actualizar repositorio" if ya_analizado else "Analizar repositorio"

    if st.button(etiqueta_boton, key="coding_analizar_repo"):
        with st.spinner("Descubriendo estructura y tecnologías del repositorio..."):
            initial_state = {
                "coding_issues": session.get("coding_issues_detectados", []),
                "coding_matrix_input": session.get("coding_matriz_carga", []),
            }
            result_state = descubrir_y_perfilar_repositorio(adapter, initial_state)
            session["coding_repository_profile"] = result_state.get("coding_repository_profile", {})
            session["coding_repository_tree"] = result_state.get("coding_repository_tree", [])
            session["coding_detected_technologies"] = result_state.get("coding_detected_technologies", {})
            session["coding_selected_tools"] = result_state.get("coding_selected_tools", {})
            session["coding_repository_context"] = result_state.get("coding_repository_context", {})
            session["coding_repository_discovery"] = result_state.get("coding_repository_discovery", {})
        st.rerun()

    if not ya_analizado:
        return

    descubrimiento = session.get("coding_repository_discovery", {})
    perfil = session.get("coding_repository_profile", {})
    tecnologias = session.get("coding_detected_technologies", {})
    herramientas = session.get("coding_selected_tools", {})
    contexto = session.get("coding_repository_context", {})

    if descubrimiento.get("estado") == "ERROR":
        st.error(f"Error al descubrir el repositorio: {descubrimiento.get('error', 'desconocido')}")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rama analizada", perfil.get("rama", "N/A"))
    col2.metric("Archivos detectados", descubrimiento.get("total_archivos", 0))
    col3.metric("Archivos de código", descubrimiento.get("total_archivos") and len(descubrimiento.get("archivos_codigo", [])) or 0)
    col4.metric("Directorios", descubrimiento.get("total_directorios", 0))

    with st.expander("🔤 Lenguajes detectados", expanded=True):
        if perfil.get("lenguajes"):
            df_lenguajes = []
            for lang in perfil.get("lenguajes", []):
                df_lenguajes.append({
                    "Lenguaje": lang.get("nombre", ""),
                    "Porcentaje": f"{lang.get('porcentaje', 0):.1f}%"
                })
            if df_lenguajes:
                st.dataframe(df_lenguajes, use_container_width=True)
        else:
            st.info("No se detectaron lenguajes.")

    with st.expander("⚙️ Ecosistemas y gestores de dependencias", expanded=True):
        if perfil.get("ecosistemas"):
            for eco in perfil.get("ecosistemas", []):
                st.markdown(f"**{eco.get('nombre')}** — {eco.get('gestor_dependencias')}")
                st.caption(f"Evidencias: {', '.join(eco.get('evidencias', []))}")
        else:
            st.info("No se detectaron ecosistemas conocidos.")

    with st.expander("🛠️ Tecnologías y frameworks", expanded=True):
        if perfil.get("frameworks_tecnologias"):
            st.markdown("**Detectados:**")
            for tech in perfil.get("frameworks_tecnologias", []):
                st.markdown(f"• {tech}")
        else:
            st.info("No se detectaron frameworks o tecnologías principales.")

    with st.expander("📦 Manifiestos y lockfiles", expanded=False):
        if perfil.get("manifiestos") or perfil.get("lockfiles"):
            if perfil.get("manifiestos"):
                st.markdown("**Manifiestos:**")
                for m in perfil.get("manifiestos", []):
                    st.markdown(f"• {m}")
            if perfil.get("lockfiles"):
                st.markdown("**Lockfiles:**")
                for lf in perfil.get("lockfiles", []):
                    st.markdown(f"• {lf}")
        else:
            st.info("No se detectaron manifiestos o lockfiles.")

    with st.expander("⚙️ Archivos de configuración", expanded=False):
        if perfil.get("archivos_configuracion"):
            for cf in perfil.get("archivos_configuracion", []):
                st.markdown(f"• {cf}")
        else:
            st.info("No se detectaron archivos de configuración.")

    with st.expander("📂 Estructura del repositorio", expanded=False):
        tree = session.get("coding_repository_tree", [])
        if tree:
            archivos_str = "\n".join([f.get("ruta") for f in tree if f.get("tipo") == "archivo"][:20])
            st.code(archivos_str if archivos_str else "Sin archivos", language="")
            if len(tree) > 20:
                st.caption(f"... y {len(tree) - 20} elementos más")
        else:
            st.info("Árbol del repositorio no disponible.")

    st.divider()
    st.markdown("#### Análisis técnico planificado")

    if contexto.get("estado_global") == "BLOQUEADO":
        st.error("⚠️ Estado: BLOQUEADO")
        st.markdown("**Problemas encontrados:**")
        for problema in contexto.get("problemas", []):
            st.markdown(f"• **{problema['issue']}**: {problema['tipo']}")
            for detalle in problema.get("detalle", []):
                st.markdown(f"  - {detalle}")
        return

    if contexto.get("problemas"):
        st.warning("⚠️ Estado: CON ADVERTENCIAS")
        st.markdown("**Problemas encontrados:**")
        for problema in contexto.get("problemas", []):
            st.markdown(f"• **{problema['issue']}**: {problema['tipo']}")

    df_herramientas = []
    for metrica_id, tools_info in herramientas.items():
        for tool_info in tools_info:
            df_herramientas.append({
                "Métrica": metrica_id,
                "Tipo": tool_info.get("tipo", ""),
                "Herramienta": tool_info.get("herramienta", ""),
                "Aplica a": ", ".join(tool_info.get("aplica_a", [])) if tool_info.get("aplica_a") else "Repositorio",
                "Estado": "🟡 PENDIENTE"
            })

    if df_herramientas:
        st.dataframe(df_herramientas, use_container_width=True)
    else:
        st.info("No se seleccionaron herramientas.")

    st.info(
        "✅ Descubrimiento completado. Las herramientas se ejecutarán "
        "en la siguiente fase cuando confirmes e inicies el análisis."
    )


def render_coding_stage(project_name: str, project_config: dict, adapter) -> None:
    import streamlit as st

    session = st.session_state
    if "codificacion_resultados" not in session:
        persisted = cargar_estado_etapa("codificacion")
        session["codificacion_resultados"] = (persisted or {}).get("codificacion_resultados", {})
        if persisted:
            session["coding_matriz_snapshot"] = persisted.get("coding_matriz_snapshot")
            session["coding_matriz_snapshot_metadata"] = persisted.get("coding_matriz_snapshot_metadata")
            session["coding_repository_snapshot"] = persisted.get("coding_repository_snapshot")
            session["coding_issue_snapshot"] = persisted.get("coding_issue_snapshot")
    elif (
        session["codificacion_resultados"] and session.get("coding_matriz_snapshot")
        and cargar_estado_etapa("codificacion") is None
    ):
        # Resultados ya en memoria de una ejecución anterior a esta persistencia: respaldarlos ahora.
        guardar_estado_etapa("codificacion", {
            "codificacion_resultados": session["codificacion_resultados"],
            "coding_matriz_snapshot": session["coding_matriz_snapshot"],
            "coding_matriz_snapshot_metadata": session.get("coding_matriz_snapshot_metadata"),
            "coding_repository_snapshot": session.get("coding_repository_snapshot"),
            "coding_issue_snapshot": session.get("coding_issue_snapshot"),
        })
    session.setdefault("coding_matriz_confirmada", False)

    paso_entrada, paso_repositorio, paso_analisis, paso_resultados, step_key = create_coding_step_panels(
        "codificacion",
        bool(session["codificacion_resultados"]),
    )

    # ============================================================
    # A. Entradas: matriz de Diseño (TRZ-002) + Issues de Codificación
    # ============================================================
    # La fase se ordena en un resumen de estado y dos subsecciones (pestañas).
    # Los contenedores se crean por adelantado y se rellenan cuando hay datos; la
    # lógica de carga, validación y sincronización es la misma de siempre.

    sub = crear_subsecciones_entrada(paso_entrada, "Issues de Codificación")

    sub.acciones.markdown(rotulo_bloque_html("Acciones sobre la matriz"), unsafe_allow_html=True)
    col_actualizar, col_gitlab, col_excel = sub.acciones.columns(3)
    actualizar_gitlab = col_actualizar.button(
        "Actualizar desde GitLab", icon=":material/refresh:", key="coding_actualizar_trz002", width="stretch",
    )
    if "coding_matriz_carga" not in session or actualizar_gitlab:
        with sub.avisos.spinner("Consultando TRZ-002 en GitLab..."):
            issue_trz002, matriz_trz002 = obtener_issue_matriz_trazabilidad_diseno(adapter.project_id)
        if matriz_trz002 is not None:
            session["coding_matriz_carga"] = matriz_trz002
            session["coding_issue_trz002"] = issue_trz002
            if "coding_matriz_original" not in session:
                matriz_final_diseno = session.get("diseno_filas_matriz_final") or matriz_trz002
                session["coding_matriz_original"] = copy.deepcopy(matriz_final_diseno)
            session["coding_matriz_fuente"] = "GitLab — TRZ-002"
            session["coding_matriz_confirmada"] = False

    if "coding_matriz_carga" not in session:
        sub.avisos.info(
            "TRZ-002 no está disponible en GitLab. Ejecute primero la etapa de Diseño "
            "o cargue la matriz de trazabilidad exportada desde Diseño."
        )
        sub.resumen_matriz.markdown(
            tarjeta_estado_entrada_html("Matriz de trazabilidad · Diseño", [chip_html("No disponible", "bad")]),
            unsafe_allow_html=True,
        )
        sub.resumen_issues.markdown(
            tarjeta_estado_entrada_html("Issues de Codificación", [chip_html("Requiere la matriz", "muted")]),
            unsafe_allow_html=True,
        )
        archivo_matriz = sub.acciones.file_uploader(
            "Cargar matriz de Diseño (Excel)", type=["xlsx", "csv"], key="coding_matriz_upload_inicial",
        )
        if archivo_matriz is None:
            return
        matriz_cargada = (
            importar_matriz_xlsx(archivo_matriz) if archivo_matriz.name.lower().endswith(".xlsx")
            else importar_matriz_csv(archivo_matriz)
        )
        session["coding_matriz_carga"] = matriz_cargada
        session["coding_matriz_original"] = copy.deepcopy(matriz_cargada)
        session["coding_matriz_fuente"] = "EXCEL"
        st.rerun()

    matriz_entrada = session["coding_matriz_carga"]
    preparacion_matriz = preparar_matriz_entrada_codificacion(
        session["coding_matriz_original"], matriz_entrada, session.get("coding_matriz_fuente", "Diseño"),
    )

    # Resumen de la matriz de entrada (mismos datos en todas las etapas:
    # Fuente vigente · Versión · Estado · Validación · Filas de la matriz).
    estado_matriz = preparacion_matriz["coding_matrix_status"]
    matriz_invalida_ui = estado_matriz == ESTADO_MATRIZ_INVALIDA
    tono_estado = {"ORIGINAL": "ok", "EDITADA": "warn", ESTADO_MATRIZ_INVALIDA: "bad"}.get(estado_matriz, "muted")
    version_matriz = leer_version_matriz("diseno") or preparacion_matriz.get("coding_matrix_version") or "No informada"
    sub.resumen_matriz.markdown(
        tarjeta_estado_entrada_html(
            "Matriz de trazabilidad · Diseño",
            [
                chip_html(estado_matriz, tono_estado),
                chip_html("INVÁLIDA" if matriz_invalida_ui else "VÁLIDA", "bad" if matriz_invalida_ui else "ok"),
                chip_html(contar(len(matriz_entrada), "fila", "filas"), "info"),
            ],
            meta=f"{preparacion_matriz['coding_matrix_source']} · Versión {version_matriz}",
        ),
        unsafe_allow_html=True,
    )

    if preparacion_matriz["coding_matrix_status"] == ESTADO_MATRIZ_INVALIDA:
        sub.avisos.error("Estado: INVÁLIDA. Se encontraron errores estructurales:")
        for error in preparacion_matriz["coding_matrix_changes"]["errores_estructura"]:
            sub.avisos.markdown(f"• {error}")
    elif preparacion_matriz["coding_matrix_changes"]["hay_cambios"]:
        cambios = preparacion_matriz["coding_matrix_changes"]
        sub.avisos.caption(
            f"Cambios respecto a la carga inicial: "
            f"+{len(cambios['agregados'])} agregados · "
            f"~{len(cambios['modificados'])} modificados · "
            f"-{len(cambios['retirados'])} retirados"
        )
    else:
        sub.avisos.caption("Estado: Original. No se detectaron modificaciones respecto a la carga inicial de esta sesión.")

    sub.tabla.dataframe(matriz_entrada, width="stretch")

    issue_trz002 = session.get("coding_issue_trz002")
    if issue_trz002 is not None:
        col_gitlab.link_button("Editar en GitLab", issue_trz002.web_url, icon=":material/open_in_new:", width="stretch")
    else:
        col_gitlab.caption("TRZ-002 no está disponible en GitLab.")

    xlsx_entrada_path = "output/xlsx/matriz_entrada_codificacion.xlsx"
    exportar_filas_xlsx(
        matriz_entrada, xlsx_entrada_path, nombre_hoja="Trazabilidad Diseño",
    )
    with open(xlsx_entrada_path, "rb") as handle:
        col_excel.download_button(
            "Editar con Excel", handle.read(), file_name="matriz_entrada_codificacion.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="coding_descargar_excel", icon=":material/download:", width="stretch",
        )

    archivo_modificado = sub.acciones.file_uploader(
        "Cargar matriz de Diseño modificada", type=["xlsx", "csv"], key="coding_matriz_upload",
    )
    if archivo_modificado is not None and session.get("coding_matriz_upload_nombre") != archivo_modificado.name:
        with sub.acciones.spinner("Validando la matriz cargada..."):
            matriz_excel = (
                importar_matriz_xlsx(archivo_modificado) if archivo_modificado.name.lower().endswith(".xlsx")
                else importar_matriz_csv(archivo_modificado)
            )
            session["coding_matriz_carga"] = matriz_excel
            session["coding_matriz_fuente"] = "EXCEL"
            session["coding_matriz_upload_nombre"] = archivo_modificado.name
            session["coding_matriz_confirmada"] = False
        st.rerun()

    matriz_valida = preparacion_matriz["coding_matrix_status"] != ESTADO_MATRIZ_INVALIDA
    elementos_diseno_validos = set(preparacion_matriz["elementos_diseno_validos"])

    # ============================================================
    # Issues de Codificación detectados
    # ============================================================

    if "coding_issues_detectados" not in session:
        with sub.tab_issues.spinner("Consultando Issues de Codificación en GitLab..."):
            session["coding_issues_detectados"] = obtener_issues_codificacion(
                adapter.project_id, milestone_title="Codificación",
            )
    issues_codificacion = session["coding_issues_detectados"]

    estado_entrada = preparar_estado_entrada_codificacion(issues_codificacion, elementos_diseno_validos)
    # Se listan todos los issues del milestone; solo se analizan (y se validan para el
    # análisis) los Pendiente o Requiere modificación.
    analizable_por_cod_id = {
        (issue.get("codificacion_id") or f"issue-{issue.get('issue_iid')}"): etiquetas_son_analizables(issue.get("labels"))
        for issue in issues_codificacion
    }
    prevalidacion = preparar_prevalidacion_codificacion(
        matriz_entrada, {
            fila["codificacion_id"]: estado_entrada["validaciones"][fila["codificacion_id"]]
            for fila in estado_entrada["filas"] if analizable_por_cod_id.get(fila["codificacion_id"])
        },
    )

    # Los issues válidos y bloqueados ya se ven en el resumen de arriba: aquí solo
    # se indica contra cuántos elementos de Diseño se validan.
    sub.tab_issues.markdown(
        kpi_strip_html([(prevalidacion["elementos_diseno_vigentes"], "Elementos de Diseño vigentes")], compact=True),
        unsafe_allow_html=True,
    )

    sub.resumen_issues.markdown(
        tarjeta_estado_entrada_html("Issues de Codificación", [
            chip_html(contar(len(estado_entrada["filas"]), "detectado", "detectados"), "info"),
            chip_html(contar(sum(analizable_por_cod_id.values()), "a analizar", "a analizar"), "info"),
            chip_html(contar(len(prevalidacion["issues_validos"]), "válido", "válidos"), "ok"),
            chip_html(
                contar(len(prevalidacion["issues_bloqueados"]), "bloqueado", "bloqueados"),
                "bad" if prevalidacion["issues_bloqueados"] else "muted",
            ),
        ]),
        unsafe_allow_html=True,
    )

    if sub.tab_issues.button(
        "Actualizar issues", icon=":material/refresh:", key="coding_actualizar_issues", width="content",
    ):
        session.pop("coding_issues_detectados", None)
        st.rerun()

    if not estado_entrada["filas"]:
        sub.tab_issues.info("No se encontraron Issues de Codificación en el milestone.")
        return

    # Cada entrada se muestra con su estado de revisión en GitLab y si se analiza o
    # queda solo como referencia, junto a la validez de su entrada.
    labels_por_iid = {issue.get("issue_iid"): issue.get("labels") for issue in issues_codificacion}
    render_alcance_entradas(sub.tab_issues, list(labels_por_iid.values()))
    for fila in estado_entrada["filas"]:
        icono = "🟢" if fila["entrada_valida"] else "🔴"
        sub.tab_issues.markdown(
            entrada_fila_html(
                f"{icono} {fila['codificacion_id']}", fila["estado_entrada"], labels_por_iid.get(fila["issue_iid"]),
            ),
            unsafe_allow_html=True,
        )
        if fila["campos_faltantes"]:
            sub.tab_issues.caption(f"Campos faltantes: {', '.join(fila['campos_faltantes'])}")
        if fila["referencias_invalidas"]:
            sub.tab_issues.caption(f"Elementos de Diseño inexistentes en la matriz heredada: {', '.join(fila['referencias_invalidas'])}")

    codificaciones_validas = [
        fila["codificacion_id"] for fila in estado_entrada["filas"]
        if fila["entrada_valida"] and analizable_por_cod_id.get(fila["codificacion_id"])
    ]

    render_next_phase_button(paso_entrada, step_key, 1)

    # ============================================================
    # B. Información técnica del repositorio (descubrimiento previo)
    # ============================================================

    with paso_repositorio:
        render_coding_repository_info(session, adapter)

    render_next_phase_button(paso_repositorio, step_key, 2)

    # ============================================================
    # C. Ejecución del análisis
    # ============================================================

    paso_analisis.markdown("### Ejecución del análisis")

    session["coding_matriz_confirmada"] = paso_analisis.checkbox(
        "Confirmo que la Matriz de Trazabilidad — Etapa Diseño mostrada corresponde a la versión vigente "
        "que debe considerarse en la etapa de Codificación.",
        value=session["coding_matriz_confirmada"], key="coding_matriz_confirmada_check", disabled=not matriz_valida,
    )

    # Verificar que el descubrimiento del repositorio se haya completado
    repo_profile = session.get("coding_repository_profile", {})
    descubrimiento_valido = bool(repo_profile and repo_profile.get("rama"))
    contexto_repo = session.get("coding_repository_context", {})
    sin_bloqueos = contexto_repo.get("estado_global") != "BLOQUEADO"

    puede_ejecutar = (
        matriz_valida and session["coding_matriz_confirmada"]
        and bool(codificaciones_validas)
        and descubrimiento_valido
        and sin_bloqueos
    )
    ejecutar = paso_analisis.button(
        "Iniciar análisis de Codificación", icon=":material/play_arrow:", type="primary",
        disabled=not puede_ejecutar, key="coding_ejecutar",
    )
    if ejecutar:
        matriz_snapshot = copy.deepcopy(matriz_entrada)
        session["coding_matriz_snapshot"] = matriz_snapshot
        session["coding_matriz_snapshot_metadata"] = {
            "coding_matrix_version": preparacion_matriz["coding_matrix_version"],
            "coding_matrix_source": preparacion_matriz["coding_matrix_source"],
            "coding_matrix_status": preparacion_matriz["coding_matrix_status"],
        }

        # Capturar snapshot de descubrimiento del repositorio
        session["coding_repository_snapshot"] = {
            "timestamp": datetime.now().isoformat(),
            "repository_profile": copy.deepcopy(repo_profile),
            "repository_discovery": copy.deepcopy(session.get("coding_repository_discovery", {})),
            "detected_technologies": copy.deepcopy(session.get("coding_detected_technologies", {})),
            "selected_tools": copy.deepcopy(session.get("coding_selected_tools", {})),
            "repository_context": copy.deepcopy(contexto_repo),
        }
        session["coding_issue_snapshot"] = copy.deepcopy(issues_codificacion)
        grafo = construir_grafo_codificacion()
        for codificacion_id in codificaciones_validas:
            with paso_analisis.spinner(f"Localizando código y ejecutando herramientas para {codificacion_id}..."):
                issue = next(
                    i for i in issues_codificacion
                    if (i.get("codificacion_id") or f"issue-{i.get('issue_iid')}") == codificacion_id
                )
                codigo_localizado = obtener_codigo_codificacion(
                    adapter, codificacion_id, issue.get("archivos_declarados", []),
                )
                initial_state = {
                    "project_name": project_name,
                    "sprint_context": SPRINT_CONTEXT_CODIFICACION,
                    "coding_issues": [issue],
                    "coding_matrix_input": matriz_snapshot,
                    "coding_codigo_localizado": codigo_localizado,
                    "coding_selected_tools": session["coding_repository_snapshot"]["selected_tools"],
                    "coding_repository_profile": session["coding_repository_snapshot"]["repository_profile"],
                    **session["coding_matriz_snapshot_metadata"],
                }
                session["codificacion_resultados"][codificacion_id] = grafo.invoke(initial_state)
        # Issues bloqueados por elementos de Diseño inexistentes: no se analizan, pero
        # se deja constancia en GitLab (comentario + etiqueta 'Requiere modificación').
        avisos_publicados = session.setdefault("coding_avisos_referencias_publicados", set())
        for fila in estado_entrada["filas"]:
            if (
                not fila["referencias_invalidas"] or fila["codificacion_id"] in avisos_publicados
                or not analizable_por_cod_id.get(fila["codificacion_id"])
            ):
                continue
            try:
                publicar_aviso_referencias_invalidas_codificacion(
                    adapter.project_id, fila["issue_iid"], fila["codificacion_id"],
                    fila["referencias_invalidas"], adapter=adapter,
                )
                avisos_publicados.add(fila["codificacion_id"])
                paso_analisis.info(
                    f"{fila['codificacion_id']}: no analizado por elementos de Diseño "
                    f"inexistentes ({', '.join(fila['referencias_invalidas'])}). "
                    f"Aviso publicado en GitLab."
                )
            except Exception as exc:
                paso_analisis.warning(
                    f"No se pudo publicar el aviso de elementos inexistentes para "
                    f"{fila['codificacion_id']} en GitLab: {exc}"
                )
        guardar_estado_etapa("codificacion", {
            "codificacion_resultados": session["codificacion_resultados"],
            "coding_matriz_snapshot": session["coding_matriz_snapshot"],
            "coding_matriz_snapshot_metadata": session["coding_matriz_snapshot_metadata"],
            "coding_repository_snapshot": session["coding_repository_snapshot"],
            "coding_issue_snapshot": session["coding_issue_snapshot"],
        })
        paso_analisis.success(f"Análisis completado para: {', '.join(codificaciones_validas)}.")

    render_next_phase_button(paso_analisis, step_key, 3)

    # ============================================================
    # ============================================================
    # D. Resultados y artefactos
    # ============================================================

    resultados = session["codificacion_resultados"]
    if not resultados:
        paso_resultados.info("Ejecuta el análisis para ver resultados.")
        return

    paso_resultados.divider()
    resultados_central = [
        {"issue_iid": res["coding_context"][0]["issue_iid"], "codificacion_id": codificacion_id, **res["coding_central_result"]}
        for codificacion_id, res in resultados.items()
    ]
    evaluacion_por_cod = {
        codificacion_id: res["coding_summary"]["estado_orientativo"] for codificacion_id, res in resultados.items()
    }
    matriz_para_trazabilidad = session.get("coding_matriz_snapshot", matriz_entrada)
    filas_matriz = construir_filas_matriz_codificacion(matriz_para_trazabilidad, resultados_central, evaluacion_por_cod)
    resumen_trazabilidad = resumir_trazabilidad_codificacion(filas_matriz)

    hubo_error_global = any(
        resultado.get("coding_summary", {}).get("estado_orientativo") == "ERROR"
        for resultado in resultados.values()
    )
    if ejecutar and filas_matriz and not hubo_error_global:
        crear_o_actualizar_issue_matriz_trazabilidad_codificacion(
            project_id=adapter.project_id,
            filas_matriz=filas_matriz,
            metadata=session.get("coding_matriz_snapshot_metadata"),
        )

    presentaciones = {
        codificacion_id: _construir_presentacion(resultado_grafo, filas_matriz)
        for codificacion_id, resultado_grafo in resultados.items()
    }

    # Tras el análisis, actualizar automáticamente la etiqueta de flujo de cada
    # Issue de Codificación evaluado (Revisada / Requiere modificación). Los
    # estados ERROR no modifican la etiqueta. El comentario de retroalimentación
    # también se publica automáticamente en GitLab (sin botón).
    if ejecutar:
        for codificacion_id, p in presentaciones.items():
            if p["estado_orientativo"] == "ERROR":
                continue
            actualizar_etiqueta_resultado_tecnico(
                adapter.project_id, p["issue_iid"], p["estado_orientativo"], adapter=adapter,
            )
            # Historial para el seguimiento de calidad y seguridad del panel del proyecto.
            # (solo los issues analizados en esta ejecución, no los de ejecuciones previas de la sesión)
            if codificacion_id in codificaciones_validas:
                guardar_historial(
                    p["issue_iid"], p["indice_calidad"], p["indice_seguridad"],
                    p["estado_orientativo"], None, p.get("conclusion_calidad") or "", stage="codificacion",
                )
            try:
                publicar_comentario_codificacion(
                    adapter.project_id, p["issue_iid"], resultados[codificacion_id]["coding_summary"],
                    adapter=adapter,
                )
                session[f"coding_publicado_{codificacion_id}"] = True
            except Exception as exc:
                session[f"coding_publicado_{codificacion_id}"] = False
                st.warning(f"{codificacion_id}: no se pudo publicar la retroalimentación en GitLab ({exc}).")

    resumen_general, detalle_resultados, artefactos = paso_resultados.tabs(
        ["Resumen general", "Detalle por codificación", "Matriz y documentos"]
    )
    render_stage_summary(
        resumen_general,
        etiqueta_items="Codificaciones evaluadas",
        total_items=len(presentaciones),
        requieren_correccion=sum(
            p.get("estado_orientativo") == "CORREGIR" for p in presentaciones.values()
        ),
        con_error=sum(
            p.get("estado_orientativo") == "ERROR" for p in presentaciones.values()
        ),
        calidad_promedio=promedio_indices(p.get("indice_calidad") for p in presentaciones.values()),
        seguridad_promedio=promedio_indices(p.get("indice_seguridad") for p in presentaciones.values()),
        aviso=(
            "Los resultados constituyen apoyo al control y seguimiento de la codificación. "
            "La aceptación final requiere revisión humana."
        ),
        filas_matriz=[
            fila_matriz_resultados(
                identificador, p["titulo"], p["estado_orientativo"],
                calidad=extraer_porcentaje(p["indice_calidad"]),
                seguridad=extraer_porcentaje(p["indice_seguridad"]),
                correcciones=len(p["correcciones_necesarias"]),
                precisiones=len(p["precisiones_necesarias"]),
                mejoras=len(p["oportunidades_mejora"]),
                metricas=filas_metricas_presentacion(p["metricas"]),
            )
            for identificador, p in presentaciones.items()
        ],
        etiqueta_detalle="Detalle por codificación",
    )

    elegido = selector_resultados(
        detalle_resultados, "codificacion",
        [(identificador, pres["estado_orientativo"]) for identificador, pres in presentaciones.items()],
    )
    for codificacion_id, p in presentaciones.items():
        if codificacion_id != elegido:
            continue
        resultado_grafo = resultados[codificacion_id]
        expander_title = titulo_item(p['codificacion_id'], p['titulo'], p['estado_orientativo'])

        # Un resultado a la vez (selector de arriba): evita una página larga en vertical.
        with detalle_resultados.container(border=True):
            st.markdown(f"### {expander_title}")
            render_evaluation_header(
                titulo="Resultado de evaluación asistida",
                estado=p["estado_orientativo"],
                indice_calidad=extraer_porcentaje(p["indice_calidad"]),
                indice_seguridad=extraer_porcentaje(p["indice_seguridad"]),
                explicacion_estado=_explicar_estado_codificacion(p),
            )

            evidencia_herramientas = resultado_grafo.get("coding_tool_results", {})
            _render_evidencia_tecnica(evidencia_herramientas)

            mc05 = p["metricas"]["MC-05"]
            ms05 = p["metricas"]["MS-05"]
            ms06 = p["metricas"]["MS-06"]
            ms07 = p["metricas"]["MS-07"]
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
                    render_gitlab_feedback(bool(session.get(f"coding_publicado_{codificacion_id}")))

            with tab_calidad:
                with st.expander(f"MC-05 — {mc05['nombre']} · {extraer_porcentaje(mc05['valor'])}", expanded=False):
                    st.metric(f"Resultado {mc05['codigo']}", extraer_porcentaje(mc05["valor"]))
                    st.caption(f"Herramienta: {mc05.get('herramienta', 'Analizador técnico')}")
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{mc05["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Funciones con complejidad no aceptable:**")
                    for funcion in mc05.get("funciones_criticas", []):
                        st.markdown(
                            f'<div class="finding-block finding-correction">'
                            f'<strong>{funcion.get("archivo", "")} — {funcion.get("nombre", "")}</strong> '
                            f'(CC={funcion.get("complejidad", "")})<br>'
                            f'{funcion.get("problema", "")}<br>'
                            f'<em>Recomendación:</em> {funcion.get("recomendacion", "")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f'<div class="result-intro"><strong>Resultado:</strong> {mc05["resultado"]}</div>',
                        unsafe_allow_html=True,
                    )
                    if mc05.get("conclusion"):
                        st.markdown(f'<div class="result-intro">{mc05["conclusion"]}</div>', unsafe_allow_html=True)

            with tab_seguridad:
                with st.expander(f"MS-05 — {ms05['nombre']} · {ms05.get('numero_criticas', 'No evaluable')} críticas", expanded=False):
                    st.metric(f"Resultado {ms05['codigo']}", ms05.get("numero_criticas", "No evaluable"))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{ms05["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    for vulnerabilidad in ms05.get("vulnerabilidades_criticas", []):
                        st.markdown(
                            f'<div class="finding-block finding-correction">'
                            f'<strong>{vulnerabilidad.get("archivo", "")}</strong> — {vulnerabilidad.get("regla", "")}<br>'
                            f'{vulnerabilidad.get("mensaje", "")}<br>{vulnerabilidad.get("explicacion", "")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    if ms05.get("conclusion"):
                        st.markdown(f'<div class="result-intro">{ms05["conclusion"]}</div>', unsafe_allow_html=True)

                with st.expander(f"MS-06 — {ms06['nombre']} · {extraer_porcentaje(ms06['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms06['codigo']}", extraer_porcentaje(ms06["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{ms06["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    for dependencia in ms06.get("dependencias_inseguras", []):
                        st.markdown(
                            f'<div class="finding-block finding-correction">'
                            f'<strong>{dependencia.get("nombre", "")} {dependencia.get("version", "")}</strong><br>'
                            f'{dependencia.get("explicacion", "")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f'<div class="result-intro"><strong>Resultado:</strong> {ms06["resultado"]}</div>',
                        unsafe_allow_html=True,
                    )
                    if ms06.get("conclusion"):
                        st.markdown(f'<div class="result-intro">{ms06["conclusion"]}</div>', unsafe_allow_html=True)

                with st.expander(f"MS-07 — {ms07['nombre']} · {extraer_porcentaje(ms07['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms07['codigo']}", extraer_porcentaje(ms07["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{ms07["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    for archivo_secreto in ms07.get("archivos_con_secretos", []):
                        st.markdown(
                            f'<div class="finding-block finding-correction">'
                            f'<strong>{archivo_secreto.get("archivo", "")}</strong> — {archivo_secreto.get("regla", "")}<br>'
                            f'{archivo_secreto.get("explicacion", "")}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f'<div class="result-intro"><strong>Resultado:</strong> {ms07["resultado"]}</div>',
                        unsafe_allow_html=True,
                    )
                    if ms07.get("conclusion"):
                        st.markdown(f'<div class="result-intro">{ms07["conclusion"]}</div>', unsafe_allow_html=True)

            with tab_formalizacion:
                propuesta = p.get("propuesta_para_maximo", [])
                if propuesta:
                    st.markdown("#### Propuesta para alcanzar el máximo")
                    for item in propuesta:
                        st.markdown(
                            f'<div class="finding-block finding-precision">{item}</div>',
                            unsafe_allow_html=True,
                        )

                trz = p.get("trazabilidad", {})
                implementados = trz.get("implementados", [])
                no_confirmados = trz.get("no_confirmados", [])
                st.markdown("#### Trazabilidad de esta Codificación")
                st.markdown(f"**Implementados:** {', '.join(implementados) if implementados else 'Ninguno.'}")
                st.markdown(f"**Declarados sin confirmar:** {', '.join(no_confirmados) if no_confirmados else 'Ninguno.'}")

    # ---- Matriz de Trazabilidad de la etapa ----
    with artefactos.expander("Matriz de Trazabilidad de la etapa", expanded=False):
        import pandas as pd
        columnas_trz = [
            "HU origen", "Código requisito", "Tipo", "Nombre del requisito",
            "Descripción", "Diseño", "Elementos de Diseño",
            "Estado de trazabilidad", "Estado de Diseño",
            "Codificación", "Estado de implementación", "Ubicación de implementación",
            "Estado de Codificación", "Observación de Codificación",
        ]
        df = pd.DataFrame(filas_matriz)
        columnas_disponibles = [col for col in columnas_trz if col in df.columns]
        st.dataframe(df[columnas_disponibles] if columnas_disponibles else df, width="stretch", hide_index=True)

        fecha = datetime.now().strftime("%Y%m%d")
        exportar_filas_xlsx(
            filas_matriz, f"output/xlsx/matriz_codificacion_{fecha}.xlsx",
            nombre_hoja="Trazabilidad Codificación", resumen=resumen_trazabilidad,
        )
        with open(f"output/xlsx/matriz_codificacion_{fecha}.xlsx", "rb") as handle:
            st.download_button(
                "Descargar matriz (Excel)", handle.read(),
                file_name="matriz_codificacion.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    # ---- Documentos consolidados ----
    artefactos.subheader("Documentos consolidados")
    # Copia para no mutar el metadata de la sesión (usado también al publicar).
    # Versión propia = matriz de Codificación (TRZ-003); versión de entrada =
    # matriz de Diseño heredada (TRZ-002). Ambas provienen del registro de versiones.
    matriz_metadata_documentos = dict(session.get("coding_matriz_snapshot_metadata", {}) or {})
    matriz_metadata_documentos["matriz_trazabilidad_version"] = leer_version_matriz("codificacion") or "No informada"
    matriz_metadata_documentos["coding_matrix_version"] = (
        leer_version_matriz("diseno")
        or matriz_metadata_documentos.get("coding_matrix_version")
        or "No informada"
    )
    lista_presentaciones = list(presentaciones.values())

    pdf_bytes = generar_reporte_codificacion_pdf(
        project_name, "Codificación", lista_presentaciones, resumen_trazabilidad, matriz_metadata_documentos,
    )
    docx_bytes = generar_documento_formal_codificacion_docx(
        project_name, "Codificación", lista_presentaciones, matriz_metadata_documentos,
        filas_trazabilidad=filas_matriz,
    )

    col_pdf, col_docx = artefactos.columns(2)

    with col_pdf:
        st.markdown("### Reporte Ejecutivo")
        st.caption(
            "Presenta métricas, evidencias, hallazgos, brechas, "
            "precisiones y oportunidades de la evaluación de la Codificación."
        )
        st.download_button(
            "Descargar Reporte Ejecutivo", pdf_bytes.getvalue(),
            file_name=nombre_archivo(REPORTE, "Codificacion", "pdf"), mime="application/pdf",
            width="stretch",
        )

    with col_docx:
        st.markdown("### Documento Formal")
        st.caption(
            "Consolida implementaciones, elementos de diseño implementados, "
            "archivos, dependencias, seguridad, trazabilidad y aspectos "
            "pendientes de revisión."
        )
        st.download_button(
            "Descargar Documento Formal", docx_bytes.getvalue(),
            file_name=nombre_archivo(FORMAL, "Codificacion", "docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
