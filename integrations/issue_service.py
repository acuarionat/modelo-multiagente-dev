import json
import logging
import time

from core.graph import construir_grafo
from core.config import ALLOW_INCOMPLETE_STORIES, OLLAMA_MODEL
from core.batch_contract import construir_etiquetas_resultado, normalizar_lista_textos
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.utils import construir_resultado_lote, extraer_porcentaje
from database.repository import calcular_hash_issue, guardar_cache, guardar_historial, insertar_o_actualizar_issue
from integrations.gitlab_adapter import GitLabAdapter, es_issue_pendiente
from integrations.issue_mapper import mapear_issue_a_json, separar_entradas_para_analisis

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "v4-assisted-evaluation"
DECISION_SUPPORT_NOTICE = (
    "Este resultado constituye una evaluación asistida para apoyar el control, seguimiento y trazabilidad. "
    "La decisión de aceptación corresponde al responsable del proyecto y requiere revisión humana."
)


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
    estado = result.get("estado_evaluacion") or evaluation.get("veredicto") or "REVISAR"
    recommendations = normalizar_lista_textos(result.get("recommendations"))
    if not recommendations:
        recommendations = normalizar_lista_textos(evaluation.get("correcciones_obligatorias"))
    if not recommendations:
        conclusions = normalizar_lista_textos(evaluation.get("conclusion"))
        recommendations = conclusions[:1]
    recommendation_text = "\n".join(f"- {text}" for text in recommendations[:3]) or "- Revisar el resultado consolidado."
    next_action = (
        "Actualizar la Historia con las correcciones obligatorias y volver a marcarla como **Pendiente**."
        if estado in {"CORREGIR", "ALERTA", "REVISAR"}
        else "La Historia queda marcada como **Revisada** y puede continuar con la siguiente etapa."
    )
    return f"""## Resultado del análisis multiagente

**Estado orientativo:** {estado}<br>
**Calidad funcional:** {extraer_porcentaje(quality.get('indice'))}<br>
**Cobertura documental de seguridad:** {extraer_porcentaje(security.get('indice'))}<br>
**Nivel de aseguramiento recomendado:** {security.get('lot_recomendado', 'No informado')}

### Hallazgos principales
{recommendation_text}

### Próxima acción
{next_action}

> Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.
"""


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
    final_state = {}
    if processable_issues:
        for output in construir_grafo().stream(initial_state):
            for value in output.values():
                final_state.update(value)
    execution_time = time.time() - started
    final_results = json.loads(final_state["final_report"])["resultados"] if final_state else []
    if not ALLOW_INCOMPLETE_STORIES:
        final_results.extend(_resultado_informacion_insuficiente(item) for item in incomplete_data)
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
    return batch_result
