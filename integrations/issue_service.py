import json
import logging
import time

from core.graph import construir_grafo
from core.config import ALLOW_INCOMPLETE_STORIES
from core.batch_contract import construir_etiquetas_resultado
from core.utils import construir_resultado_lote, extraer_porcentaje
from database.repository import calcular_hash_issue, guardar_cache, guardar_historial, insertar_o_actualizar_issue
from integrations.gitlab_adapter import GitLabAdapter
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
    central = result["central"]
    quality = result["quality"]
    security = result["security"]
    evaluation = result["evaluation"]
    requirements = "\n".join(
        f"- **{r['id']} — {r.get('nombre', '')}:** {r.get('descripcion', '')}"
        for r in central["requerimientos"]
    )
    recommendations = result.get("recommendations", [])
    recommendation_text = "\n".join(f"- {x}" for x in recommendations) or "- Sin correcciones obligatorias."
    next_action = (
        "Actualizar la Historia con las correcciones obligatorias y marcarla como **En revisión**."
        if evaluation["veredicto"] in {"CORREGIR", "ALERTA"}
        else "Mantener la Historia como **Analizada** y continuar con la siguiente etapa."
    )
    return f"""## Resultado del análisis multiagente

**Estado de evaluación asistida:** {evaluation['veredicto']}<br>
**Índice parcial de apoyo para calidad funcional:** {extraer_porcentaje(quality['indice'])}<br>
**Índice de cobertura documental de seguridad:** {extraer_porcentaje(security['indice'])}<br>
**Nivel de aseguramiento recomendado — LoT:** {security.get('lot_recomendado', 'No informado')}

> El LoT no representa la confianza del modelo, sino el nivel de aseguramiento recomendado según las condiciones identificadas.

### Evaluación de calidad
{_lineas_metricas(quality.get('metricas', {}))}

### Evaluación de seguridad
{_lineas_metricas(security.get('metricas', {}))}

### Requerimientos formalizados sugeridos
{requirements}

### Correcciones y recomendaciones
{recommendation_text}

### Próxima acción
{next_action}

### Alcance del resultado
{DECISION_SUPPORT_NOTICE}

Los documentos consolidados (PDF, DOCX y matriz CSV) pueden generarse desde la aplicación de recepción de requerimientos.
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


def procesar_flujo_lote(issues: list, project_name: str, sprint_context: str = "") -> dict:
    adapter = GitLabAdapter()
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

Complete la historia y manténgala en revisión para ejecutar nuevamente la evaluación.

{DECISION_SUPPORT_NOTICE}
"""
            try:
                adapter.agregar_comentario(iid, comment)
                labels = construir_etiquetas_resultado(issues_by_iid[iid].labels, "NO_EVALUADO")
                adapter.actualizar_etiquetas(iid, labels)
                result["comment_published"] = True
            except Exception as exc:
                result["gitlab_error"] = str(exc)
                logger.exception("No se pudo registrar la entrada insuficiente en GitLab para Issue #%s", iid)
            content_hash = calcular_hash_issue(result["issue_data"])
            insertar_o_actualizar_issue(iid, content_hash, "Información insuficiente")
            continue
        if result["status"] != "ok":
            logger.error("Issue #%s incompleto: %s", iid, "; ".join(result["errors"]))
            continue

        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        content_hash = calcular_hash_issue(result["issue_data"])
        comment = construir_comentario_issue(result)
        try:
            adapter.agregar_comentario(iid, comment)
            labels = construir_etiquetas_resultado(
                issues_by_iid[iid].labels, result["estado_evaluacion"], quality.get("indice"), security.get("indice")
            )
            adapter.actualizar_etiquetas(iid, labels)
            result["comment_published"] = True
        except Exception as exc:
            result["gitlab_error"] = str(exc)
            logger.exception("No se pudo actualizar GitLab para Issue #%s", iid)

        tracking_state = "Analizada" if result["estado_evaluacion"] == "APROBADO" else "En revisión"
        insertar_o_actualizar_issue(iid, content_hash, tracking_state)
        guardar_historial(iid, quality.get("indice"), security.get("indice"), evaluation["veredicto"], execution_time / max(len(processable_issues), 1), evaluation.get("conclusion", ""))
        guardar_cache(content_hash, SCHEMA_VERSION, central, quality, security, evaluation)

    logger.info("Flujo de lote terminado en %.2fs.", execution_time)
    return batch_result
