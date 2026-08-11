import json
import logging
import time
from datetime import datetime
from types import SimpleNamespace

from core.graph import construir_grafo
from core.config import ALLOW_INCOMPLETE_STORIES, OLLAMA_MODEL
from core.batch_contract import construir_etiquetas_resultado
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.utils import construir_filas_trazabilidad, construir_resultado_lote, extraer_porcentaje
from database.repository import calcular_hash_issue, guardar_cache, guardar_historial, insertar_o_actualizar_issue
from integrations.gitlab_adapter import GitLabAdapter, es_issue_pendiente
from integrations.issue_mapper import mapear_issue_a_json, separar_entradas_para_analisis
from integrations.design_issue_mapper import mapear_issue_diseno
from integrations.coding_issue_mapper import mapear_issue_codificacion
from integrations.traceability_issue_mapper import construir_markdown_matriz_trazabilidad, mapear_matriz_trazabilidad
from integrations.design_traceability_issue_mapper import (
    DESIGN_TRACEABILITY_COLUMNS,
    construir_markdown_matriz_trazabilidad_diseno,
    mapear_matriz_trazabilidad_diseno,
)
from integrations.coding_traceability_issue_mapper import (
    CODING_TRACEABILITY_COLUMNS,
    construir_markdown_matriz_trazabilidad_codificacion,
    mapear_matriz_trazabilidad_codificacion,
)

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "v4-assisted-evaluation"
DECISION_SUPPORT_NOTICE = (
    "Este resultado constituye una evaluación asistida para apoyar el control, seguimiento y trazabilidad. "
    "La decisión de aceptación corresponde al responsable del proyecto y requiere revisión humana."
)
TRZ_001_TITULO = "TRZ-001 - Matriz de Trazabilidad"
TRZ_002_TITULO = "TRZ-002 - Matriz de Trazabilidad - Etapa Diseño"
TRZ_003_TITULO = "TRZ-003 - Matriz de Trazabilidad - Etapa Codificación"


def _lineas_metricas(metrics: dict) -> str:
    lines = []
    for name, detail in metrics.items():
        if not isinstance(detail, dict):
            continue
        labels = {
            "cobertura_funcional": "Cobertura funcional estimada",
            "adecuacion_funcional": "Adecuación funcional estimada",
            "controles_seguridad": "Cobertura documental estimada de controles",
            "lot_asignado": "Asignación justificada del nivel de aseguramiento — LoT",
        }
        label = labels.get(name, name.replace("_", " ").capitalize())
        value = extraer_porcentaje(detail.get("valor"))
        explanation = detail.get("justificacion", "")
        state = detail.get("estado_medicion", "evaluable")
        lines.append(f"- **{label}:** {value} ({state}). {explanation}")
    return "\n".join(lines)


def construir_comentario_issue(result: dict) -> str:
    quality = result.get("quality") or {}
    security = result.get("security") or {}
    evaluation = result.get("evaluation") or {}
    estado = (
        result.get("estado_orientativo")
        or evaluation.get("veredicto")
        or "REVISIÓN HUMANA"
    )

    quality_metrics = quality.get("metricas") if isinstance(quality.get("metricas"), dict) else {}
    mc01 = quality_metrics.get("cobertura_funcional") if isinstance(quality_metrics.get("cobertura_funcional"), dict) else {}
    mc02 = quality_metrics.get("adecuacion_funcional") if isinstance(quality_metrics.get("adecuacion_funcional"), dict) else {}

    gaps = quality.get("gaps_funcionales")
    gaps = [gap for gap in gaps if isinstance(gap, dict)] if isinstance(gaps, list) else []

    precisiones = result.get("precisiones_necesarias")
    precisiones = precisiones if isinstance(precisiones, list) else []

    mejoras = result.get("mejoras_sugeridas")
    mejoras = mejoras if isinstance(mejoras, list) else []

    secciones = [
        "## Resultado del análisis multiagente",
        "",
        f"**Estado orientativo:** {estado}",
        "",
        "### Calidad de la evidencia original",
        f"**MC-01 Cobertura Funcional:** {extraer_porcentaje(mc01.get('valor'))}",
        f"**MC-02 Adecuación Funcional:** {extraer_porcentaje(mc02.get('valor'))}",
        "",
        "### Seguridad",
        f"**Índice de Seguridad en Requerimientos:** {extraer_porcentaje(security.get('indice'))}",
    ]

    if gaps:
        secciones += [
            "",
            "### Gap funcional identificado",
            *[f"- {gap.get('funcion', '')}" for gap in gaps],
            "",
            "### Por qué afecta MC-01",
            str(mc01.get("justificacion_final") or mc01.get("justificacion") or ""),
            "",
            "### Sugerencia para alcanzar el 100 % en MC-01",
            *[f"- Formalizar {gap.get('funcion', '')}." for gap in gaps],
        ]

    if precisiones:
        secciones += [
            "",
            "### Precisiones recomendadas",
            *[
                f"- {text}"
                for precision in precisiones
                if isinstance(precision, dict)
                and (text := str(precision.get("precision") or "").strip())
            ],
        ]

    if mejoras:
        secciones += [
            "",
            "### Oportunidades adicionales",
            *[
                f"- {text}"
                for mejora in mejoras
                if isinstance(mejora, dict)
                and (text := str(mejora.get("recomendacion") or "").strip())
            ],
        ]

    secciones += ["", "### Próxima acción"]
    if gaps or precisiones:
        secciones.append(
            "Revisar las propuestas, actualizar la HU cuando corresponda "
            "y volver a marcarla como **Pendiente** para una nueva evaluación."
        )
    elif estado in {"CORREGIR", "ALERTA", "REVISIÓN HUMANA", "REVISAR"}:
        secciones.append(
            "Actualizar la Historia con las correcciones necesarias y "
            "volver a marcarla como **Pendiente**."
        )
    else:
        secciones.append(
            "La Historia queda marcada como **Revisada** y puede "
            "continuar con la siguiente etapa."
        )

    secciones += ["", f"> {DECISION_SUPPORT_NOTICE}"]

    return "\n".join(secciones) + "\n"


def construir_comentario_diseno(resumen_diseno: dict) -> str:
    """
    Construye el comentario compacto de retroalimentación operativa para un
    Issue de Diseño a partir de state["design_summary"]. No repite las
    métricas completas MC-03/MC-04/MS-03/MS-04: solo los índices, el estado
    orientativo y los hallazgos ya clasificados por el Evaluador de Diseño.
    """
    diseno_id = resumen_diseno.get("diseno_id", "")
    estado = resumen_diseno.get("estado_orientativo", "")
    indice_calidad = extraer_porcentaje(resumen_diseno.get("indice_calidad_diseno"))
    indice_seguridad = extraer_porcentaje(resumen_diseno.get("indice_seguridad_diseno"))

    def _textos(campo):
        valores = resumen_diseno.get(campo)
        if not isinstance(valores, list):
            return []
        return [texto.strip() for texto in valores if isinstance(texto, str) and texto.strip()]

    correcciones = _textos("correcciones_necesarias")
    precisiones = _textos("precisiones_necesarias")
    oportunidades = _textos("oportunidades_mejora")

    lineas = [
        f"Resultado del análisis de Diseño — {diseno_id}",
        "",
        f"Estado orientativo: {estado}",
        f"Índice de Calidad de Diseño: {indice_calidad}",
        f"Índice de Seguridad de Diseño: {indice_seguridad}",
        "",
        "Correcciones necesarias:",
        *([f"- {item}" for item in correcciones] if correcciones else ["- Ninguna."]),
        "",
        "Precisiones:",
        *([f"- {item}" for item in precisiones] if precisiones else ["- Ninguna."]),
        "",
        "Oportunidades de mejora:",
        *([f"- {item}" for item in oportunidades] if oportunidades else ["- Ninguna."]),
        "",
        "Próxima acción:",
        (
            "Actualizar el Issue de Diseño con las correcciones necesarias y volver a marcarlo como Pendiente."
            if correcciones else
            "El Issue de Diseño queda marcado como Revisado y puede continuar con la siguiente etapa."
        ),
        "",
        "Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.",
    ]

    return "\n".join(lineas) + "\n"


def publicar_comentario_diseno(project_id, issue_iid, resumen_diseno: dict):
    """Publica en GitLab el comentario de retroalimentación operativa de Diseño (reutiliza GitLabAdapter.agregar_comentario, sin duplicar llamadas HTTP)."""
    if not resumen_diseno:
        raise ValueError("No existe resumen de Diseño para publicar.")

    if resumen_diseno.get("estado_orientativo") == "ERROR":
        raise ValueError(
            "No se publica comentario de evaluación cuando existe error técnico."
        )

    comentario = construir_comentario_diseno(resumen_diseno)

    adapter = GitLabAdapter(project_id=project_id)
    return adapter.agregar_comentario(issue_iid, comentario)


def construir_comentario_codificacion(resumen_codificacion: dict) -> str:
    """
    Construye el comentario compacto de retroalimentación operativa para un
    Issue de Codificación a partir de state["coding_summary"]. No repite las
    métricas completas MC-05/MS-05/MS-06/MS-07: solo los índices, el estado
    orientativo y los hallazgos ya clasificados por el Evaluador de Codificación.
    """
    codificacion_id = resumen_codificacion.get("codificacion_id", "")
    estado = resumen_codificacion.get("estado_orientativo", "")
    indice_calidad = extraer_porcentaje(resumen_codificacion.get("indice_calidad_codigo"))
    indice_seguridad = extraer_porcentaje(resumen_codificacion.get("indice_seguridad_codigo"))

    def _textos(campo):
        valores = resumen_codificacion.get(campo)
        if not isinstance(valores, list):
            return []
        return [texto.strip() for texto in valores if isinstance(texto, str) and texto.strip()]

    correcciones = _textos("correcciones_necesarias")
    precisiones = _textos("precisiones_necesarias")
    oportunidades = _textos("oportunidades_mejora")

    lineas = [
        f"Resultado del análisis de Codificación — {codificacion_id}",
        "",
        f"Estado orientativo: {estado}",
        f"Índice de Calidad del Código: {indice_calidad}",
        f"Índice de Seguridad del Código: {indice_seguridad}",
        "",
        "Correcciones necesarias:",
        *([f"- {item}" for item in correcciones] if correcciones else ["- Ninguna."]),
        "",
        "Precisiones:",
        *([f"- {item}" for item in precisiones] if precisiones else ["- Ninguna."]),
        "",
        "Oportunidades de mejora:",
        *([f"- {item}" for item in oportunidades] if oportunidades else ["- Ninguna."]),
        "",
        "Próxima acción:",
        (
            "Actualizar el Issue de Codificación con las correcciones necesarias y volver a marcarlo como Pendiente."
            if correcciones else
            "El Issue de Codificación queda marcado como Revisado y puede continuar con la siguiente etapa."
        ),
        "",
        "Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.",
    ]

    return "\n".join(lineas) + "\n"


def publicar_comentario_codificacion(project_id, issue_iid, resumen_codificacion: dict):
    """Publica en GitLab el comentario de retroalimentación operativa de Codificación (reutiliza GitLabAdapter.agregar_comentario, sin duplicar llamadas HTTP)."""
    if not resumen_codificacion:
        raise ValueError("No existe resumen de Codificación para publicar.")

    if resumen_codificacion.get("estado_orientativo") == "ERROR":
        raise ValueError(
            "No se publica comentario de evaluación cuando existe error técnico."
        )

    comentario = construir_comentario_codificacion(resumen_codificacion)

    adapter = GitLabAdapter(project_id=project_id)
    return adapter.agregar_comentario(issue_iid, comentario)


def obtener_issues_codificacion(project_id, milestone_title="Codificación"):
    """Obtiene los Issues COD-xxx de GitLab y los estructura con coding_issue_mapper."""
    adapter = GitLabAdapter(project_id=project_id)
    issues = adapter.listar_issues_abiertos(milestone_title=milestone_title)
    return [mapear_issue_codificacion(issue) for issue in issues]


def _resultado_informacion_insuficiente(issue_data: dict) -> dict:
    validation = issue_data["validacion_entrada"]
    missing = validation["campos_faltantes"]
    return {
        "issue_iid": int(issue_data["id"]),
        "status": "error",
        "estado_procesamiento": "informacion_insuficiente",
        "estado_evaluacion": "NO_EVALUADO",
        "errors": [f"Información insuficiente. Campos faltantes: {', '.join(missing)}."],
        "validacion_entrada": validation,
        "central": None, "quality": None, "security": None, "evaluation": None,
        "revision_humana_requerida": True,
        "estado_revision_humana": "pendiente",
        "responsable_revision": None,
        "issue_data": issue_data,
        "comment_published": False,
    }


def _actualizar_estado_gitlab(adapter, result: dict, estado_evaluacion: str) -> None:
    """Aplica el ciclo de etiquetas sin convertir un fallo GitLab en fallo del análisis."""
    labels = construir_etiquetas_resultado(
        result.get("issue_data", {}).get("labels", []),
        estado_evaluacion,
    )
    try:
        adapter.actualizar_etiquetas(result["issue_iid"], labels)
        result["labels_updated"] = True
        result["labels_after"] = labels
    except Exception as exc:
        result["labels_updated"] = False
        result["gitlab_label_error"] = str(exc)
        logger.exception(
            "No se pudieron actualizar etiquetas de GitLab para Issue #%s.",
            result["issue_iid"],
        )


def procesar_flujo_lote(issues: list, project_name: str, sprint_context: str = "", adapter=None) -> dict:
    reiniciar_contadores()
    logger.info("Modelo Ollama efectivo para la ejecución: %s", OLLAMA_MODEL)
    adapter = adapter or GitLabAdapter()
    received_count = len(issues)
    issues = [issue for issue in issues if es_issue_pendiente(issue)]
    if len(issues) != received_count:
        logger.info(
            "Filtro GitLab: recibidas=%s, pendientes_elegibles=%s, omitidas_por_estado=%s.",
            received_count, len(issues), received_count - len(issues),
        )
    issues_data = [mapear_issue_a_json(issue) for issue in issues]
    issues_by_iid = {int(issue.iid): issue for issue in issues}
    processable_data, incomplete_data = separar_entradas_para_analisis(issues_data, ALLOW_INCOMPLETE_STORIES)
    processable_ids = {int(item["id"]) for item in processable_data}
    processable_issues = [issue for issue in issues if int(issue.iid) in processable_ids]
    initial_state = {
        "project_name": project_name,
        "issues_data": processable_data,
        "sprint_context": sprint_context,
        "central_init": None,
        "quality_report": None,
        "security_report": None,
        "evaluation": None,
        "final_report": None,
        "validation_errors": [],
        "content_validation_errors": {},
    }
    logger.info("Iniciando ejecución del grafo multiagente para %s historias válidas.", len(processable_issues))
    started = time.time()
    execution_id = datetime.now().strftime("pipeline-%Y%m%d-%H%M%S-%f")
    final_state = {}
    if processable_issues:
        try:
            for output in construir_grafo().stream(initial_state):
                for value in output.values():
                    final_state.update(value)
        except Exception as exc:
            from core.execution_summary import (
                build_sanitized_execution_summary, persist_sanitized_execution_summary,
            )
            audit = obtener_contadores()
            completed = audit.get("resumen_parcial_remoto", {}).get("completed_issue_ids", [])
            if not completed:
                completed = audit.get("resumen_parcial_central", {}).get("received", [])
            summary = build_sanitized_execution_summary(
                execution_id=execution_id, estado="incompleto",
                etapa_alcanzada=getattr(exc, "agent", None) or "flujo",
                auditoria=audit, historias_esperadas=sorted(processable_ids),
                historias_completas=completed, error=exc, artefactos={},
                gitlab_usado=False,
            )
            path = persist_sanitized_execution_summary(summary)
            exc.summary_path = str(path)
            raise
    execution_time = time.time() - started
    final_results = json.loads(final_state["final_report"])["resultados"] if final_state else []
    # Las entradas insuficientes ya atravesaron el grafo y no deben duplicarse.
    final_results.sort(key=lambda item: item["issue_iid"])
    issue_data_by_iid = {int(item["id"]): item for item in issues_data}
    for result in final_results:
        result["issue_data"] = issue_data_by_iid[result["issue_iid"]]
        result["comment_published"] = False

    milestone = next((line.split(":", 1)[1].strip() for line in sprint_context.splitlines() if line.startswith("Sprint:")), "Sin milestone")
    batch_result = construir_resultado_lote(project_name, milestone, final_results)
    for result in batch_result["issues"]:
        iid = result["issue_iid"]
        if result["estado_procesamiento"] == "informacion_insuficiente":
            missing = result["validacion_entrada"]["campos_faltantes"]
            comment = f"""## Información insuficiente para el análisis multiagente

No se envió esta historia al modelo porque faltan campos esenciales: **{', '.join(missing)}**.

La historia quedará como **Requiere modificación**. Después de corregirla, vuelva a marcarla como **Pendiente** para ejecutar nuevamente la evaluación.

{DECISION_SUPPORT_NOTICE}
"""
            publication_started = time.perf_counter()
            try:
                adapter.agregar_comentario(iid, comment)
                result["comment_published"] = True
            except Exception as exc:
                result["gitlab_error"] = str(exc)
                logger.exception("No se pudo registrar la entrada insuficiente en GitLab para Issue #%s", iid)
            finally:
                logger.info("GitLab Issue #%s completado en %.2fs.", iid, time.perf_counter() - publication_started)
            _actualizar_estado_gitlab(adapter, result, "NO_PROCESABLE")
            content_hash = calcular_hash_issue(result["issue_data"])
            insertar_o_actualizar_issue(iid, content_hash, "Requiere modificación")
            continue
        if result["status"] != "ok":
            logger.error("Issue #%s incompleto: %s", iid, "; ".join(result["errors"]))
            continue

        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        content_hash = calcular_hash_issue(result["issue_data"])
        comment = construir_comentario_issue(result)
        publication_started = time.perf_counter()
        try:
            adapter.agregar_comentario(iid, comment)
            result["comment_published"] = True
        except Exception as exc:
            result["gitlab_error"] = str(exc)
            logger.exception("No se pudo actualizar GitLab para Issue #%s", iid)
        finally:
            logger.info("GitLab Issue #%s completado en %.2fs.", iid, time.perf_counter() - publication_started)

        _actualizar_estado_gitlab(adapter, result, result["estado_evaluacion"])
        tracking_state = "Revisada" if result["estado_evaluacion"] == "APROBADO" else "Requiere modificación"
        insertar_o_actualizar_issue(iid, content_hash, tracking_state)
        guardar_historial(iid, quality.get("indice"), security.get("indice"), evaluation["veredicto"], execution_time / max(len(processable_issues), 1), evaluation.get("conclusion", ""))
        guardar_cache(content_hash, SCHEMA_VERSION, central, quality, security, evaluation)

    published = sum(bool(item.get("comment_published")) for item in batch_result["issues"])
    failed = sum(item.get("status") != "ok" for item in batch_result["issues"])
    audit = obtener_contadores()
    logger.info(
        "Flujo de lote terminado en %.2fs: recibidas=%s, correctas=%s, con_error=%s, comentarios_publicados=%s, pendientes=%s.",
        execution_time, received_count, len(issues) - failed, failed, published, len(issues) - published,
    )
    logger.info(
        "Ollama lote: llamadas=%s, reintentos=%s, por_agente=%s.",
        audit["llamadas_ollama"], audit["reintentos"], audit["por_agente"],
    )

    try:
        generation_date = datetime.now().date().isoformat()
        filas_matriz_requerimientos_actual = construir_filas_trazabilidad(batch_result["issues"], generation_date)
        execution_id = datetime.now().strftime("requerimientos-%Y%m%d-%H%M%S")
        crear_o_actualizar_issue_matriz_trazabilidad(
            project_id=adapter.project_id,
            filas_matriz=filas_matriz_requerimientos_actual,
            metadata={
                "project_id": adapter.project_id,
                "milestone": milestone,
                "execution_id": execution_id,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
    except Exception:
        logger.exception("No se pudo publicar/actualizar TRZ-001 en GitLab.")

    return batch_result


def obtener_issues_diseno(project_id, milestone_title="Diseño"):
    """Obtiene los Issues de Diseño pendientes o que requieren modificación y los estructura."""
    adapter = GitLabAdapter(project_id=project_id)
    issues = adapter.listar_issues_pendientes(milestone_title=milestone_title)
    return [mapear_issue_diseno(issue) for issue in issues]


def construir_matriz_requerimientos_original(resultados_lote_actual: list) -> list:
    """
    Utilidad de recuperación/pruebas: normaliza un conjunto de resultados de
    lote YA DETERMINADO por quien la llama (nunca se auto-descubre desde
    cache_results). El flujo real de Requerimientos NO usa esta función: usa
    construir_filas_trazabilidad() directamente sobre los resultados en
    memoria de la ejecución que acaba de terminar.
    """
    from core.design_context import normalizar_fila_trazabilidad

    if not resultados_lote_actual:
        return []

    filas_crudas = construir_filas_trazabilidad(resultados_lote_actual)
    return [normalizar_fila_trazabilidad(fila) for fila in filas_crudas]


def obtener_issue_matriz_trazabilidad(project_id):
    """Recupera TRZ-001 desde GitLab y lo normaliza al contrato interno (codigo/nombre/descripcion/...). (None, None) si no existe todavía."""
    from core.design_context import normalizar_fila_trazabilidad

    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo("TRZ-001")
    if issue is None:
        return None, None
    filas = mapear_matriz_trazabilidad(issue)
    return issue, [normalizar_fila_trazabilidad(fila) for fila in filas]


def validar_consistencia_matriz_publicacion(filas_oficiales: list, filas_trz: list) -> None:
    """Verifica que el Markdown publicado en TRZ-001 no haya perdido, alterado ni renumerado ningún requisito oficial."""
    assert len(filas_oficiales) == len(filas_trz), (
        f"La matriz publicada tiene {len(filas_trz)} filas; se esperaban {len(filas_oficiales)}."
    )

    oficiales = {fila["Código"]: fila for fila in filas_oficiales}
    publicadas = {fila["Código"]: fila for fila in filas_trz}

    assert oficiales.keys() == publicadas.keys(), (
        f"Los códigos publicados no coinciden con los oficiales: "
        f"faltantes={sorted(oficiales.keys() - publicadas.keys())}, "
        f"inesperados={sorted(publicadas.keys() - oficiales.keys())}."
    )

    for codigo in oficiales:
        assert oficiales[codigo]["Nombre"] == publicadas[codigo]["Nombre"], f"{codigo}: Nombre no coincide tras publicar."
        assert oficiales[codigo]["Descripción"] == publicadas[codigo]["Descripción"], f"{codigo}: Descripción no coincide tras publicar."


def crear_o_actualizar_issue_matriz_trazabilidad(project_id, filas_matriz, metadata=None):
    """
    Publica (crea o actualiza) TRZ-001 con las filas YA CONSOLIDADAS de la
    ejecución actual (mismo contrato de construir_filas_matriz_requerimientos_final).
    Función pasiva: no lee cache_results, no reconstruye ni renumera nada.
    Reemplaza por completo la descripción anterior del Issue (GitLab ya
    conserva el historial de edición).
    """
    if not filas_matriz:
        logger.warning("No hay filas de matriz para publicar TRZ-001.")
        return None

    contenido = construir_markdown_matriz_trazabilidad(filas_matriz, metadata)

    filas_publicables = mapear_matriz_trazabilidad(SimpleNamespace(description=contenido))
    validar_consistencia_matriz_publicacion(filas_matriz, filas_publicables)

    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo("TRZ-001")
    if issue is None:
        return adapter.crear_issue(TRZ_001_TITULO, contenido)
    return adapter.actualizar_descripcion_issue(issue.iid, contenido)


def obtener_issue_matriz_trazabilidad_diseno(project_id):
    """Recupera TRZ-002 y sus filas con el contrato oficial de 10 columnas."""
    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_002_TITULO)
    if issue is None:
        return None, None
    return issue, mapear_matriz_trazabilidad_diseno(issue.description or "")


def crear_o_actualizar_issue_matriz_trazabilidad_diseno(project_id, filas_matriz, metadata=None):
    """Valida y persiste pasivamente en TRZ-002 las filas finales de Diseño."""
    if not filas_matriz:
        logger.warning("No hay filas de matriz de Diseño para publicar TRZ-002.")
        return None

    for indice, fila in enumerate(filas_matriz, start=1):
        if set(fila) != set(DESIGN_TRACEABILITY_COLUMNS):
            raise ValueError(f"La fila {indice} de TRZ-002 no respeta el contrato de 10 columnas.")

    contenido = construir_markdown_matriz_trazabilidad_diseno(filas_matriz)
    recuperadas = mapear_matriz_trazabilidad_diseno(contenido)

    if len(recuperadas) != len(filas_matriz):
        raise ValueError("El round-trip de TRZ-002 alteró la cantidad de filas.")
    for indice, (original, recuperada) in enumerate(zip(filas_matriz, recuperadas), start=1):
        for columna in DESIGN_TRACEABILITY_COLUMNS:
            if recuperada[columna] != original.get(columna, ""):
                raise ValueError(
                    f"El round-trip de TRZ-002 alteró la fila {indice}, columna {columna!r}."
                )

    if metadata:
        detalle = (
            f"_Ejecución: {metadata.get('execution_id', 'No informado')} — "
            f"Versión: {metadata.get('matriz_version', 'No informada')}._\n\n"
        )
        contenido = contenido.replace("## Matriz de trazabilidad", detalle + "## Matriz de trazabilidad", 1)

    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_002_TITULO)
    if issue is None:
        return adapter.crear_issue(TRZ_002_TITULO, contenido)
    return adapter.actualizar_descripcion_issue(issue.iid, contenido)


def obtener_issue_matriz_trazabilidad_codificacion(project_id):
    """Recupera TRZ-003 y sus filas con el contrato oficial de 15 columnas."""
    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_003_TITULO)
    if issue is None:
        return None, None
    return issue, mapear_matriz_trazabilidad_codificacion(issue.description or "")


def crear_o_actualizar_issue_matriz_trazabilidad_codificacion(project_id, filas_matriz, metadata=None):
    """Valida y persiste pasivamente en TRZ-003 las filas finales de Codificación."""
    if not filas_matriz:
        logger.warning("No hay filas de matriz de Codificación para publicar TRZ-003.")
        return None

    for indice, fila in enumerate(filas_matriz, start=1):
        columnas_fila = set(fila)
        columnas_esperadas = set(CODING_TRACEABILITY_COLUMNS)
        if not columnas_esperadas.issubset(columnas_fila):
            faltantes = columnas_esperadas - columnas_fila
            raise ValueError(f"La fila {indice} de TRZ-003 no tiene las columnas obligatorias: {faltantes}.")

    contenido = construir_markdown_matriz_trazabilidad_codificacion(filas_matriz)
    recuperadas = mapear_matriz_trazabilidad_codificacion(contenido)

    if len(recuperadas) != len(filas_matriz):
        raise ValueError("El round-trip de TRZ-003 alteró la cantidad de filas.")
    for indice, (original, recuperada) in enumerate(zip(filas_matriz, recuperadas), start=1):
        for columna in CODING_TRACEABILITY_COLUMNS:
            if recuperada[columna] != str(original.get(columna, "")):
                raise ValueError(
                    f"El round-trip de TRZ-003 alteró la fila {indice}, columna {columna!r}."
                )

    if metadata:
        detalle = (
            f"_Ejecución: {metadata.get('execution_id', 'No informado')} — "
            f"Versión: {metadata.get('coding_matrix_version', 'No informada')}._\n\n"
        )
        contenido = contenido.replace("## Matriz de trazabilidad", detalle + "## Matriz de trazabilidad", 1)

    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_003_TITULO)
    if issue is None:
        return adapter.crear_issue(TRZ_003_TITULO, contenido)
    return adapter.actualizar_descripcion_issue(issue.iid, contenido)
