"""
Vista de la etapa de Diseño para app.py.

Regla de esta capa: orquestar y mostrar. No recalcula métricas, no
reconstruye trazabilidad, no llama manualmente a Central/Quality/Security.
Todo el cómputo real ya vive en core/graph.py (construir_grafo_diseno),
core/design_traceability.py, core/design_matrix_input.py, core/design_metrics.py
y core/utils.py — este módulo solo los invoca y organiza sus resultados para
Streamlit.
"""

import copy
from datetime import datetime

from core.design_context import construir_contexto_diseno
from core.design_matrix_input import ESTADO_MATRIZ_INVALIDA, preparar_matriz_entrada_diseno
from core.design_presentation import construir_presentacion_resultado_diseno
from core.design_traceability import (
    construir_filas_matriz_diseno,
    evolucionar_matriz_a_diseno,
    resumir_trazabilidad_diseno,
)
from core.graph import construir_grafo_diseno
from core.traceability_export import (
    exportar_filas_xlsx,
    importar_matriz_csv,
    importar_matriz_xlsx,
)
from core.ui_components import (
    create_stage_step_panels,
    render_evaluation_header,
    render_findings_section,
    render_gitlab_feedback,
    render_human_decision_notice,
    render_next_phase_button,
)
from core.utils import extraer_porcentaje, generar_documento_formal_diseno_docx, generar_reporte_diseno_pdf
from database.repository import cargar_estado_etapa, guardar_estado_etapa, leer_version_matriz
from integrations.issue_service import (
    actualizar_etiqueta_resultado_tecnico,
    crear_o_actualizar_issue_matriz_trazabilidad_diseno,
    construir_matriz_requerimientos_original,
    obtener_issue_matriz_trazabilidad,
    obtener_issues_diseno,
    publicar_aviso_referencias_invalidas_diseno,
    publicar_comentario_diseno,
)

SPRINT_CONTEXT_DISENO = "Diseño"
COLUMNAS_MATRIZ_ENTRADA_UI = ("Código", "Tipo", "Nombre", "Descripción", "Historia de origen", "Estado de revisión")

DISENO_AVISO = (
    "El modelo multiagente apoya el control, seguimiento y trazabilidad del diseño. "
    "Las métricas y recomendaciones son orientativas y requieren revisión del "
    "responsable del proyecto."
)


# ---------------------------------------------------------
# Preparación de datos (puras, sin Streamlit, testeables)
# ---------------------------------------------------------

def preparar_prevalidacion_diseno(matriz_normalizada: list, contextos_por_diseno_id: dict) -> dict:
    """Agrega, sin recalcular, las validaciones ya producidas por construir_contexto_diseno para cada Issue."""
    referencias_validas = 0
    referencias_invalidas = 0
    issues_validos = []
    issues_bloqueados = []

    for diseno_id, contexto in contextos_por_diseno_id.items():
        validacion = contexto.get("validacion_trazabilidad", {})
        referencias_validas += len(validacion.get("referencias_validas", []))
        referencias_invalidas += len(validacion.get("referencias_invalidas", []))
        if validacion.get("referencias_invalidas"):
            issues_bloqueados.append(diseno_id)
        else:
            issues_validos.append(diseno_id)

    return {
        "requisitos_totales": len(matriz_normalizada),
        "referencias_validas": referencias_validas,
        "referencias_invalidas": referencias_invalidas,
        "issues_validos": sorted(issues_validos),
        "issues_bloqueados": sorted(issues_bloqueados),
    }


def preparar_estado_entrada_diseno(contextos_por_diseno_id: dict) -> list:
    """Estado de entrada por Issue de Diseño, a partir de validacion_trazabilidad ya calculada (sin recalcular)."""
    filas = []
    for diseno_id in sorted(contextos_por_diseno_id):
        contexto = contextos_por_diseno_id[diseno_id]
        invalidas = contexto.get("validacion_trazabilidad", {}).get("referencias_invalidas", [])
        filas.append({
            "diseno_id": diseno_id,
            "issue_iid": contexto.get("issue_iid"),
            "titulo": contexto.get("titulo", ""),
            "entrada_valida": not invalidas,
            "estado_entrada": "Entrada válida" if not invalidas else "Trazabilidad incompleta",
            "referencias_invalidas": invalidas,
        })
    return filas


def preparar_filas_trazabilidad_diseno_ui(diseno_id: str, filas_matriz: list) -> list:
    """Proyecta (sin recalcular) las filas ya construidas por construir_filas_matriz_diseno a las 5 columnas de la vista."""
    return [
        {
            "Requisito": fila["Código requisito"],
            "Diseño": fila["Diseño"],
            "Elementos": fila["Elementos de Diseño"],
            "Estado de trazabilidad": fila["Estado de trazabilidad"],
            "Observación": fila["Observación"],
        }
        for fila in filas_matriz
        if fila["Diseño"] == diseno_id
    ]


def _construir_presentacion(resultado_grafo: dict, filas_matriz: list) -> dict:
    """Delega a construir_presentacion_resultado_diseno() sin recalcular."""
    return construir_presentacion_resultado_diseno(
        contexto=resultado_grafo["design_context"][0],
        central_result=resultado_grafo["design_central_result"],
        quality_result=resultado_grafo["design_quality_result"],
        security_result=resultado_grafo["design_security_result"],
        evaluator_result=resultado_grafo["design_evaluator_result"],
        design_summary=resultado_grafo["design_summary"],
        trazabilidad_filas=filas_matriz,
    )


def preparar_tabla_cambios_pre_diseno(comparacion: dict) -> dict:
    """Proyecta (sin recalcular) comparar_matrices_requerimientos() a las tablas planas de la sección 10."""
    filas_resumen = []
    for codigo in comparacion["agregados"]:
        filas_resumen.append({"Código": codigo, "Tipo de cambio": "Agregado", "Detalle": "Nuevo requerimiento"})
    for item in comparacion["modificados"]:
        campos = ", ".join(cambio["campo"] for cambio in item["cambios"])
        filas_resumen.append({
            "Código": item["codigo"], "Tipo de cambio": "Modificado",
            "Detalle": f"Campos modificados: {campos}",
        })
    for codigo in comparacion["retirados"]:
        filas_resumen.append({"Código": codigo, "Tipo de cambio": "Retirado", "Detalle": "No se encuentra en la matriz vigente"})

    filas_modificaciones = [
        {
            "Código": item["codigo"], "Campo": cambio["campo"],
            "Valor anterior": cambio["valor_anterior"], "Valor vigente": cambio["valor_vigente"],
        }
        for item in comparacion["modificados"]
        for cambio in item["cambios"]
    ]

    return {"resumen": filas_resumen, "modificaciones": filas_modificaciones}


def _filas_matriz_para_tabla_ui(matriz_normalizada: list) -> list:
    """Proyecta la matriz normalizada a las 6 columnas visibles antes de ejecutar Diseño (sección 3)."""
    return [
        {
            "Código": fila.get("codigo", ""),
            "Tipo": fila.get("tipo", ""),
            "Nombre": fila.get("nombre", ""),
            "Descripción": fila.get("descripcion", ""),
            "Historia de origen": fila.get("historia_origen", ""),
            "Estado de revisión": fila.get("estado", ""),
        }
        for fila in matriz_normalizada
    ]


def _explicar_estado_diseno_from_p(p: dict) -> str:
    return _explicar_estado_diseno({
        "estado_orientativo": p.get("estado_orientativo"),
        "correcciones_necesarias": p.get("correcciones_necesarias"),
        "indice_calidad_diseno": p.get("indice_calidad"),
        "indice_seguridad_diseno": p.get("indice_seguridad"),
    })


def _explicar_estado_diseno(resumen: dict) -> str:
    estado = resumen.get("estado_orientativo", "REVISIÓN HUMANA")
    correcciones = resumen.get("correcciones_necesarias") or []
    q = extraer_porcentaje(resumen.get("indice_calidad_diseno"))
    s = extraer_porcentaje(resumen.get("indice_seguridad_diseno"))

    if estado == "CORREGIR":
        if correcciones:
            return (
                f"El estado es CORREGIR porque se identificaron "
                f"{len(correcciones)} correcciones necesarias. "
                f"La evaluación actual registra Calidad {q} y Seguridad {s}."
            )
        return (
            "El estado es CORREGIR porque al menos una de las "
            "métricas evaluadas presenta brechas que requieren revisión."
        )
    if estado == "CONFORME CON MEJORAS":
        return (
            "Las métricas evaluadas cumplen los criterios establecidos, "
            "pero existen precisiones u oportunidades adicionales que "
            "pueden fortalecer el diseño."
        )
    if estado == "CONFORME":
        return (
            "Las métricas evaluadas cumplen los criterios establecidos "
            "y no se identificaron correcciones necesarias."
        )
    return (
        "La evaluación requiere revisión humana debido a evidencia "
        "insuficiente o a condiciones que no pudieron resolverse automáticamente."
    )


def _describir_fuente(matriz_fuente: str, issue_trz001, nombre_archivo: str = None) -> str:
    if matriz_fuente == "GitLab" and issue_trz001 is not None:
        return f"Fuente vigente: GitLab — Issue TRZ-001 (#{issue_trz001.iid})"
    if matriz_fuente == "EXCEL":
        return f"Fuente vigente: Archivo Excel — {nombre_archivo or 'archivo cargado'}"
    return "Fuente vigente: Matriz original de Requerimientos"


def _todos_los_resultados_cache() -> list:
    """
    Recupera todos los resultados formalizados en cache_results, para uso
    exclusivo de la comparación de la UI de Diseño (no del cierre real de
    Requerimientos, que ya no depende de cache_results: ver
    integrations/issue_service.py::procesar_flujo_lote).
    """
    import sqlite3
    import json

    from database.repository import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT central_json FROM cache_results")
        filas_cache = cursor.fetchall()
    finally:
        conn.close()

    resultados = []
    vistos = set()
    for (raw_central,) in filas_cache:
        central = json.loads(raw_central)
        iid = central.get("issue_iid")
        if iid is None or iid in vistos:
            continue
        vistos.add(iid)
        resultados.append({"status": "ok", "issue_iid": iid, "central": central})
    return resultados


def _cargar_entrada_desde_gitlab(adapter) -> dict:
    """Recupera TRZ-001 desde GitLab y la compara con la matriz original. Si TRZ-001 no existe, usa la matriz original como entrada."""
    matriz_original = construir_matriz_requerimientos_original(_todos_los_resultados_cache())
    issue_trz001, matriz_trz001 = obtener_issue_matriz_trazabilidad(adapter.project_id)
    matriz_entrada = matriz_trz001 if issue_trz001 is not None else matriz_original
    resultado = preparar_matriz_entrada_diseno(matriz_original, matriz_entrada, "GitLab")
    resultado["matriz_requerimientos_original"] = matriz_original
    resultado["issue_trz001"] = issue_trz001
    resultado["archivo_excel_nombre"] = None
    resultado["matriz_version"] = getattr(issue_trz001, "updated_at", None) or "1.0"
    return resultado


# ---------------------------------------------------------
# Vista Streamlit
# ---------------------------------------------------------

def render_design_stage(project_name: str, project_config: dict, adapter) -> None:
    import streamlit as st

    st.warning(DISENO_AVISO)

    session = st.session_state
    if "diseno_resultados" not in session:
        persisted = cargar_estado_etapa("diseno")
        session["diseno_resultados"] = (persisted or {}).get("diseno_resultados", {})
        if persisted:
            session["matriz_snapshot"] = persisted.get("matriz_snapshot")
            session["matriz_snapshot_metadata"] = persisted.get("matriz_snapshot_metadata")
    elif session["diseno_resultados"] and session.get("matriz_snapshot") and cargar_estado_etapa("diseno") is None:
        # Resultados ya en memoria de una ejecución anterior a esta persistencia: respaldarlos ahora.
        guardar_estado_etapa("diseno", {
            "diseno_resultados": session["diseno_resultados"],
            "matriz_snapshot": session["matriz_snapshot"],
            "matriz_snapshot_metadata": session.get("matriz_snapshot_metadata"),
        })
    session.setdefault("matriz_confirmada", False)

    paso_entrada, paso_analisis, paso_resultados, step_key = create_stage_step_panels(
        "diseno",
        bool(session["diseno_resultados"]),
    )

    # ============================================================
    # A. Entrada de trazabilidad
    # ============================================================

    paso_entrada.markdown("### Entrada de trazabilidad")

    actualizar_gitlab = paso_entrada.button("Actualizar desde GitLab", key="diseno_actualizar_matriz")
    if "matriz_carga" not in session or actualizar_gitlab:
        with paso_entrada.spinner("Consultando TRZ-001 en GitLab y comparando con la matriz original..."):
            session["matriz_carga"] = _cargar_entrada_desde_gitlab(adapter)
        session["matriz_confirmada"] = False

    carga = session["matriz_carga"]

    # ---- Procedencia y estado (sección 4) ----
    paso_entrada.markdown("#### Matriz de trazabilidad")
    paso_entrada.write(_describir_fuente(carga["matriz_fuente"], carga["issue_trz001"], carga.get("archivo_excel_nombre")))
    paso_entrada.write(f"**Estado:** {carga['matriz_estado']}")
    paso_entrada.write(f"**Validación:** {'VÁLIDA' if carga['matriz_validacion']['valida'] else 'INVÁLIDA'}")
    paso_entrada.write(f"**Requisitos vigentes:** {carga['requisitos_vigentes']}")

    if carga["matriz_estado"] == "EDITADA":
        cambios = carga["matriz_cambios_pre_diseno"]
        paso_entrada.markdown(
            f"**Cambios respecto a Requerimientos:** "
            f"+{len(cambios['agregados'])} agregados · "
            f"~{len(cambios['modificados'])} modificados · "
            f"-{len(cambios['retirados'])} retirados"
        )
    elif carga["matriz_estado"] == "ORIGINAL":
        paso_entrada.info(
            "Estado: Original. No se detectaron modificaciones respecto a la matriz "
            "generada al finalizar Recepción de Requerimientos."
        )

    if carga["matriz_estado"] == ESTADO_MATRIZ_INVALIDA:
        paso_entrada.error("Estado: INVÁLIDA. Se encontraron errores:")
        for error in carga["matriz_validacion"]["errores"]:
            paso_entrada.markdown(f"• {error}")

    paso_entrada.caption(
        "Recomendación no bloqueante: revise la matriz antes de iniciar el análisis de Diseño. "
        "Puede realizar ajustes desde GitLab o mediante Excel si los requerimientos han cambiado."
    )

    # ---- Tabla completa (solo las 6 columnas permitidas antes de Diseño) ----
    paso_entrada.dataframe(_filas_matriz_para_tabla_ui(carga["matriz_entrada_diseno"]), width="stretch")

    # ---- Cambios detectados (sección 10) ----
    if carga["matriz_estado"] == "EDITADA":
        with paso_entrada.expander("Cambios detectados respecto a Requerimientos"):
            tablas_cambios = preparar_tabla_cambios_pre_diseno(carga["matriz_cambios_pre_diseno"])
            st.table(tablas_cambios["resumen"])
    # ---- Botones de edición ----
    col_gitlab, col_excel = paso_entrada.columns(2)
    if carga["issue_trz001"] is not None:
        col_gitlab.markdown(f"[Editar en GitLab]({carga['issue_trz001'].web_url})")
    else:
        col_gitlab.caption("TRZ-001 todavía no existe en GitLab (se publica al finalizar Requerimientos).")

    xlsx_entrada_path = "output/xlsx/matriz_entrada_diseno.xlsx"
    exportar_filas_xlsx(
        _filas_matriz_para_tabla_ui(carga["matriz_entrada_diseno"]), xlsx_entrada_path,
        nombre_hoja="Matriz de entrada",
    )
    with open(xlsx_entrada_path, "rb") as handle:
        col_excel.download_button(
            "Editar con Excel", handle.read(), file_name="matriz_entrada_diseno.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="diseno_descargar_excel",
        )

    # ---- Cargar matriz modificada (Excel/CSV) ----
    archivo_modificado = paso_entrada.file_uploader(
        "Cargar matriz modificada", type=["xlsx", "csv"], key="diseno_matriz_upload",
    )
    if archivo_modificado is not None and session.get("diseno_matriz_upload_nombre") != archivo_modificado.name:
        with paso_entrada.spinner("Validando la matriz cargada..."):
            if archivo_modificado.name.lower().endswith(".xlsx"):
                matriz_excel = importar_matriz_xlsx(archivo_modificado)
            else:
                matriz_excel = importar_matriz_csv(archivo_modificado)
            nueva_carga = preparar_matriz_entrada_diseno(
                carga["matriz_requerimientos_original"], matriz_excel, "EXCEL",
            )
            nueva_carga["matriz_requerimientos_original"] = carga["matriz_requerimientos_original"]
            nueva_carga["issue_trz001"] = carga["issue_trz001"]
            nueva_carga["archivo_excel_nombre"] = archivo_modificado.name
            nueva_carga["matriz_version"] = "1.0"
            session["matriz_carga"] = nueva_carga
            session["diseno_matriz_upload_nombre"] = archivo_modificado.name
            session["matriz_confirmada"] = False
        carga = session["matriz_carga"]
        st.rerun()

    # ---- Sincronización opcional Excel → GitLab (sección 9) ----
    if carga["matriz_fuente"] == "EXCEL":
        matriz_gitlab_actual = (
            obtener_issue_matriz_trazabilidad(adapter.project_id)[1]
            if carga["issue_trz001"] is not None else carga["matriz_requerimientos_original"]
        )
        from core.design_matrix_input import comparar_matrices_requerimientos
        diferencia_con_gitlab = comparar_matrices_requerimientos(
            matriz_gitlab_actual or [], carga["matriz_entrada_diseno"],
        )
        if diferencia_con_gitlab["hay_cambios"]:
            paso_entrada.info("La matriz cargada contiene cambios respecto a la versión de GitLab.")
            if paso_entrada.button("Actualizar matriz en GitLab", key="diseno_sync_gitlab"):
                from integrations.issue_service import crear_o_actualizar_issue_matriz_trazabilidad
                filas_capitalizadas = [
                    {
                        "Código": fila.get("codigo", ""),
                        "Nombre": fila.get("nombre", ""),
                        "Descripción": fila.get("descripcion", ""),
                        "Tipo": fila.get("tipo", ""),
                        "Historia de origen": fila.get("historia_origen", ""),
                        "Fecha de generación": datetime.now().strftime("%d/%m/%Y"),
                        "Estado de revisión": fila.get("estado", ""),
                    }
                    for fila in carga["matriz_entrada_diseno"]
                ]
                crear_o_actualizar_issue_matriz_trazabilidad(adapter.project_id, filas_capitalizadas)
                paso_entrada.success("TRZ-001 actualizado en GitLab con la matriz cargada.")

    # ============================================================
    # B. Issues de Diseño detectados (vista previa contra la matriz de entrada)
    # ============================================================

    paso_entrada.markdown("### Issues de Diseño detectados")
    if "diseno_issues_detectados" not in session:
        with paso_entrada.spinner("Consultando Issues de Diseño en GitLab..."):
            session["diseno_issues_detectados"] = obtener_issues_diseno(
                adapter.project_id, milestone_title="Diseño",
            )
    issues_diseno = session["diseno_issues_detectados"]
    contextos_por_diseno_id = {
        issue.get("diseno_id"): construir_contexto_diseno(issue, carga["matriz_entrada_diseno"])
        for issue in issues_diseno
    }

    prevalidacion = preparar_prevalidacion_diseno(carga["matriz_entrada_diseno"], contextos_por_diseno_id)
    c1, c2, c3, c4, c5 = paso_entrada.columns(5)
    c1.metric("Requisitos totales", prevalidacion["requisitos_totales"])
    c2.metric("Referencias válidas", prevalidacion["referencias_validas"])
    c3.metric("Referencias inválidas", prevalidacion["referencias_invalidas"])
    c4.metric("Issues de Diseño válidos", len(prevalidacion["issues_validos"]))
    c5.metric("Issues bloqueados", len(prevalidacion["issues_bloqueados"]))

    if paso_entrada.button("Actualizar issues", key="diseno_actualizar_issues"):
        session.pop("diseno_issues_detectados", None)
        st.rerun()

    estado_entrada = preparar_estado_entrada_diseno(contextos_por_diseno_id)
    if not estado_entrada:
        paso_entrada.info("No se encontraron Issues de Diseño en el milestone.")
        return

    for fila in estado_entrada:
        icono = "🟢" if fila["entrada_valida"] else "🔴"
        paso_entrada.markdown(f"{icono} **{fila['diseno_id']}** — {fila['estado_entrada']}")
        if not fila["entrada_valida"]:
            paso_entrada.caption(f"Referencias inválidas: {', '.join(fila['referencias_invalidas'])}")

    disenos_validos = [fila["diseno_id"] for fila in estado_entrada if fila["entrada_valida"]]

    render_next_phase_button(paso_entrada, step_key, 1)

    # ============================================================
    # Confirmación explícita (sección 13) + Ejecución (Bloque C)
    # ============================================================

    paso_analisis.markdown("### Ejecución del análisis")

    matriz_valida = carga["matriz_estado"] != ESTADO_MATRIZ_INVALIDA
    session["matriz_confirmada"] = paso_analisis.checkbox(
        "Confirmo que la matriz mostrada corresponde a los requerimientos vigentes "
        "que deben considerarse en la etapa de Diseño.",
        value=session["matriz_confirmada"], key="diseno_matriz_confirmada", disabled=not matriz_valida,
    )

    puede_ejecutar = matriz_valida and session["matriz_confirmada"] and bool(disenos_validos)
    ejecutar = paso_analisis.button(
        "Iniciar análisis de Diseño", type="primary", disabled=not puede_ejecutar, key="diseno_ejecutar",
    )
    if ejecutar:
        # Congelar la matriz de entrada: todo el análisis usa esta misma versión (snapshot).
        matriz_snapshot = copy.deepcopy(carga["matriz_entrada_diseno"])
        session["matriz_snapshot"] = matriz_snapshot
        session["matriz_snapshot_metadata"] = {
            "matriz_version": carga.get("matriz_version"),
            "matriz_fuente": carga["matriz_fuente"],
            "matriz_estado": carga["matriz_estado"],
            "requisitos_vigentes": carga["requisitos_vigentes"],
        }
        grafo = construir_grafo_diseno()
        for diseno_id in disenos_validos:
            with paso_analisis.spinner(f"Procesando {diseno_id}..."):
                issue = next(i for i in issues_diseno if i.get("diseno_id") == diseno_id)
                contexto_snapshot = construir_contexto_diseno(issue, matriz_snapshot)
                initial_state = {
                    "project_name": project_name,
                    "sprint_context": SPRINT_CONTEXT_DISENO,
                    "design_issues": [issue],
                    "design_context": [contexto_snapshot],
                    **session["matriz_snapshot_metadata"],
                }
                session["diseno_resultados"][diseno_id] = grafo.invoke(initial_state)
        # Issues bloqueados por referencias inexistentes: no se analizan, pero se
        # deja constancia en GitLab (comentario + etiqueta 'Requiere modificación').
        avisos_publicados = session.setdefault("diseno_avisos_referencias_publicados", set())
        for fila in estado_entrada:
            if fila["entrada_valida"] or fila["diseno_id"] in avisos_publicados:
                continue
            try:
                publicar_aviso_referencias_invalidas_diseno(
                    adapter.project_id, fila["issue_iid"], fila["diseno_id"],
                    fila["referencias_invalidas"],
                )
                avisos_publicados.add(fila["diseno_id"])
                paso_analisis.info(
                    f"{fila['diseno_id']}: no analizado por referencias inexistentes "
                    f"({', '.join(fila['referencias_invalidas'])}). Aviso publicado en GitLab."
                )
            except Exception as exc:
                paso_analisis.warning(
                    f"No se pudo publicar el aviso de referencias inexistentes para "
                    f"{fila['diseno_id']} en GitLab: {exc}"
                )
        guardar_estado_etapa("diseno", {
            "diseno_resultados": session["diseno_resultados"],
            "matriz_snapshot": session["matriz_snapshot"],
            "matriz_snapshot_metadata": session["matriz_snapshot_metadata"],
        })
        paso_analisis.success(f"Análisis completado para: {', '.join(disenos_validos)}.")

    render_next_phase_button(paso_analisis, step_key, 2)

    # ============================================================
    # D. Resultados y artefactos
    # ============================================================

    resultados = session["diseno_resultados"]
    if not resultados:
        paso_resultados.info("Ejecuta el análisis para ver resultados.")
        return

    paso_resultados.divider()
    matriz_snapshot = session.get("matriz_snapshot", carga["matriz_entrada_diseno"])
    resultados_central = [res["design_central_result"] for res in resultados.values()]
    evaluacion_por_diseno = {
        diseno_id: res["design_summary"]["estado_orientativo"] for diseno_id, res in resultados.items()
    }
    estructura_interna = evolucionar_matriz_a_diseno(matriz_snapshot, resultados_central)
    filas_matriz = construir_filas_matriz_diseno(estructura_interna, evaluacion_por_diseno)
    resumen_trazabilidad = resumir_trazabilidad_diseno(filas_matriz)
    session["diseno_filas_matriz_final"] = copy.deepcopy(filas_matriz)

    hubo_error_global = any(
        resultado.get("design_summary", {}).get("estado_orientativo") == "ERROR"
        for resultado in resultados.values()
    )
    if ejecutar and filas_matriz and not hubo_error_global:
        crear_o_actualizar_issue_matriz_trazabilidad_diseno(
            project_id=adapter.project_id,
            filas_matriz=filas_matriz,
            metadata=session.get("matriz_snapshot_metadata"),
        )

    presentaciones = {
        diseno_id: _construir_presentacion(resultado_grafo, filas_matriz)
        for diseno_id, resultado_grafo in resultados.items()
    }

    # Tras el análisis, actualizar automáticamente la etiqueta de flujo de cada
    # Issue de Diseño evaluado (Revisada / Requiere modificación). Los estados
    # ERROR no modifican la etiqueta. La publicación del comentario detallado
    # sigue disponible manualmente en cada ficha de resultado.
    if ejecutar:
        for diseno_id, p in presentaciones.items():
            if p["estado_orientativo"] == "ERROR":
                continue
            actualizar_etiqueta_resultado_tecnico(
                adapter.project_id, p["issue_iid"], p["estado_orientativo"], adapter=adapter,
            )

    resumen_general, detalle_resultados, artefactos = paso_resultados.tabs(
        ["Resumen general", "Detalle por diseño", "Matriz y documentos"]
    )

    resumen_general.subheader("Resumen general de resultados")
    rg1, rg2, rg3 = resumen_general.columns(3)
    rg1.metric("Diseños evaluados", len(presentaciones))
    rg2.metric(
        "Requieren corrección",
        sum(1 for p in presentaciones.values() if p.get("estado_orientativo") == "CORREGIR"),
    )
    rg3.metric(
        "Con error",
        sum(1 for p in presentaciones.values() if p.get("estado_orientativo") == "ERROR"),
    )

    with resumen_general:
        render_human_decision_notice(
            "Los resultados constituyen apoyo al control y seguimiento del diseño. "
            "La aceptación final requiere revisión humana."
        )

    # ---- Resultado por Issue de Diseño ----
    detalle_resultados.subheader("Resultado de evaluación asistida")

    for diseno_id, p in presentaciones.items():
        resultado_grafo = resultados[diseno_id]
        expander_title = f"{p['diseno_id']} — {p['titulo']} · {p['estado_orientativo']}"

        # Cada resultado se presenta como una ficha resumida y desplegable para
        # evitar una página excesivamente larga cuando existen varios diseños.
        with detalle_resultados.expander(expander_title, expanded=False):
            render_evaluation_header(
                titulo="Resultado de evaluación asistida",
                estado=p["estado_orientativo"],
                indice_calidad=extraer_porcentaje(p["indice_calidad"]),
                indice_seguridad=extraer_porcentaje(p["indice_seguridad"]),
                explicacion_estado=_explicar_estado_diseno_from_p(p),
            )

            mc03 = p["metricas"]["MC-03"]
            mc04 = p["metricas"]["MC-04"]
            ms03 = p["metricas"]["MS-03"]
            ms04 = p["metricas"]["MS-04"]
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
                estado_tecnico_error = p["estado_orientativo"] == "ERROR"
                gitlab_key = f"diseno_publicado_{diseno_id}"
                if st.button(
                    "Publicar retroalimentación en GitLab", key=f"diseno_publicar_{diseno_id}",
                    disabled=estado_tecnico_error,
                ):
                    publicar_comentario_diseno(
                        adapter.project_id, p["issue_iid"], resultado_grafo["design_summary"],
                    )
                    session[gitlab_key] = True

                if session.get(gitlab_key):
                    render_gitlab_feedback(True)

            with tab_calidad:
                with st.expander(f"MC-03 — {mc03['nombre']} · {extraer_porcentaje(mc03['valor'])}", expanded=False):
                    st.metric(f"Resultado {mc03['codigo']}", extraer_porcentaje(mc03["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{mc03["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Elementos evaluados:**")
                    for ed in mc03.get("elementos_evaluados", []):
                        st.markdown(
                            f'<div class="finding-block">'
                            f'<strong>{ed["id"]}</strong> — {ed["nombre"]} ({ed["tipo"]})<br>'
                            f'Responsabilidad: {ed["responsabilidad"]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    for ed in mc03.get("elementos_faltantes", []):
                        st.markdown(
                            f'<div class="finding-block finding-correction">'
                            f'<strong>{ed["id"]}</strong> — Faltante: {ed["nombre"]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f'<div class="result-intro"><strong>Resultado:</strong> {mc03["resultado"]}</div>',
                        unsafe_allow_html=True,
                    )

                with st.expander(f"MC-04 — {mc04['nombre']} · {extraer_porcentaje(mc04['valor'])}", expanded=False):
                    st.metric(f"Resultado {mc04['codigo']}", extraer_porcentaje(mc04["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{mc04["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Relaciones documentadas:**")
                    for rel in mc04.get("relaciones_documentadas", []):
                        st.markdown(
                            f'<div class="finding-block">'
                            f'<strong>{rel["origen"]}</strong> → <strong>{rel["destino"]}</strong> '
                            f'({rel["tipo"]})<br>{rel["descripcion"]}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        f'<div class="result-intro"><strong>Interpretación:</strong> {mc04["interpretacion"]}</div>',
                        unsafe_allow_html=True,
                    )

            with tab_seguridad:
                with st.expander(f"MS-03 — {ms03['nombre']} · {extraer_porcentaje(ms03['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms03['codigo']}", extraer_porcentaje(ms03["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{ms03["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Amenazas evaluadas:**")
                    for i, am in enumerate(ms03.get("amenazas", []), 1):
                        if am["tiene_tratamiento"]:
                            st.markdown(
                                f'<div class="finding-block">'
                                f'{i}. {am["amenaza"]}<br>'
                                f'→ <strong>Tiene tratamiento</strong>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f'<div class="finding-block finding-correction">'
                                f'{i}. {am["amenaza"]}<br>'
                                f'→ <strong>NO tiene tratamiento documentado</strong>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    st.markdown(
                        f'<div class="result-intro">'
                        f'<strong>Cálculo:</strong> {ms03["numerador"]} de {ms03["denominador"]} = {extraer_porcentaje(ms03["valor"])}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                with st.expander(f"MS-04 — {ms04['nombre']} · {extraer_porcentaje(ms04['valor'])}", expanded=False):
                    st.metric(f"Resultado {ms04['codigo']}", extraer_porcentaje(ms04["valor"]))
                    st.markdown(
                        f'<div class="metric-detail"><strong>Qué mide esta métrica:</strong><br>{ms04["que_mide"]}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Controles evaluados:**")
                    for ctrl in ms04.get("controles", []):
                        if ctrl["definido"]:
                            texto_responsables = ctrl.get("responsables", "")
                            st.markdown(
                                f'<div class="finding-block">'
                                f'<strong>{ctrl.get("aspecto", ctrl["control"])}</strong><br>'
                                f'→ Definido (responsables: {texto_responsables})'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f'<div class="finding-block finding-correction">'
                                f'<strong>{ctrl.get("aspecto", ctrl["control"])}</strong><br>'
                                f'→ NO definido'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    st.markdown(
                        f'<div class="result-intro">'
                        f'<strong>Cálculo:</strong> {ms04["numerador"]} de {ms04["denominador"]} = {extraer_porcentaje(ms04["valor"])}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

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
                cubiertos = trz.get("cubiertos", [])
                pendientes_trz = trz.get("pendientes_relacion", [])
                st.markdown("#### Trazabilidad de este diseño")
                st.markdown(f"**Cubiertos:** {', '.join(cubiertos) if cubiertos else 'Ninguno.'}")
                st.markdown(f"**Pendientes de relación:** {', '.join(pendientes_trz) if pendientes_trz else 'Ninguno.'}")

    # ---- Matriz de Trazabilidad Evolucionada ----
    with artefactos.expander("Matriz de Trazabilidad Evolucionada", expanded=False):
        import pandas as pd
        columnas_trz = [
            "HU origen", "Código requisito", "Tipo", "Nombre del requisito",
            "Descripción", "Diseño", "Elementos de Diseño",
            "Estado de trazabilidad", "Estado de Diseño", "Observación",
        ]
        df = pd.DataFrame(filas_matriz)
        columnas_disponibles = [col for col in columnas_trz if col in df.columns]
        st.dataframe(df[columnas_disponibles] if columnas_disponibles else df, width="stretch", hide_index=True)

        fecha = datetime.now().strftime("%Y%m%d")
        exportar_filas_xlsx(
            filas_matriz, f"output/xlsx/matriz_diseno_{fecha}.xlsx",
            nombre_hoja="Trazabilidad Diseño", resumen=resumen_trazabilidad,
        )
        with open(f"output/xlsx/matriz_diseno_{fecha}.xlsx", "rb") as handle:
            st.download_button(
                "Descargar matriz (Excel)", handle.read(),
                file_name="matriz_diseno.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    # ---- Documentos consolidados ----
    artefactos.subheader("Documentos consolidados")
    # Copia para no mutar el metadata de la sesión (usado también al publicar).
    # La versión propia (matriz de Diseño, TRZ-002) y la de entrada (matriz de
    # Requerimientos, TRZ-001) se leen del mismo registro que alimenta los Issues TRZ.
    matriz_metadata_documentos = dict(session.get("matriz_snapshot_metadata", {}) or {})
    matriz_metadata_documentos["matriz_trazabilidad_version"] = leer_version_matriz("diseno") or "No informada"
    matriz_metadata_documentos["matriz_version"] = (
        leer_version_matriz("requerimientos")
        or matriz_metadata_documentos.get("matriz_version")
        or "No informada"
    )
    lista_presentaciones = list(presentaciones.values())

    pdf_bytes = generar_reporte_diseno_pdf(
        project_name, "Diseño", lista_presentaciones, resumen_trazabilidad, matriz_metadata_documentos,
    )
    docx_bytes = generar_documento_formal_diseno_docx(
        project_name, "Diseño", lista_presentaciones, matriz_metadata_documentos,
        filas_trazabilidad=filas_matriz,
    )

    col_pdf, col_docx = artefactos.columns(2)

    with col_pdf:
        st.markdown("### Reporte Ejecutivo")
        st.caption(
            "Presenta métricas, evidencias, hallazgos, brechas, "
            "precisiones y oportunidades de la evaluación del Diseño."
        )
        st.download_button(
            "Descargar Reporte Ejecutivo", pdf_bytes.getvalue(),
            file_name="reporte_diseno.pdf", mime="application/pdf",
            width="stretch",
        )

    with col_docx:
        st.markdown("### Documento Formal")
        st.caption(
            "Consolida elementos de diseño, relaciones, restricciones, "
            "decisiones, seguridad, trazabilidad y aspectos pendientes de revisión."
        )
        st.download_button(
            "Descargar Documento Formal", docx_bytes.getvalue(),
            file_name="documento_formal_diseno.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
