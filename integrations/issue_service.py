import json
import logging
import time

from core.graph import construir_grafo
from core.utils import construir_resultado_lote, extraer_porcentaje
from database.repository import calcular_hash_issue, guardar_cache, guardar_historial, insertar_o_actualizar_issue
from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_mapper import mapear_issue_a_json

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "v3-batch-contract"


def _lineas_metricas(metrics: dict) -> str:
    lines = []
    for name, detail in metrics.items():
        if not isinstance(detail, dict):
            continue
        label = name.replace("_", " ").capitalize()
        value = extraer_porcentaje(detail.get("valor"))
        explanation = detail.get("justificacion", "")
        lines.append(f"- **{label}:** {value}. {explanation}")
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

**Veredicto:** {evaluation['veredicto']}  
**Calidad:** {extraer_porcentaje(quality['indice'])}  
**Seguridad:** {extraer_porcentaje(security['indice'])}  
**Nivel de confianza:** {security.get('lot_recomendado', 'No informado')}

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
"""


def procesar_flujo_lote(issues: list, project_name: str, sprint_context: str = "") -> dict:
    adapter = GitLabAdapter()
    issues_data = [mapear_issue_a_json(issue) for issue in issues]
    issues_by_iid = {int(issue.iid): issue for issue in issues}
    initial_state = {
        "project_name": project_name,
        "issues_data": issues_data,
        "sprint_context": sprint_context,
        "central_init": None,
        "quality_report": None,
        "security_report": None,
        "evaluation": None,
        "final_report": None,
        "validation_errors": [],
        "content_validation_errors": {},
    }
    logger.info("Iniciando ejecución del grafo multiagente para %s historias.", len(issues))
    started = time.time()
    final_state = {}
    for output in construir_grafo().stream(initial_state):
        for value in output.values():
            final_state.update(value)
    execution_time = time.time() - started
    final = json.loads(final_state["final_report"])
    issue_data_by_iid = {int(item["id"]): item for item in issues_data}

    milestone = next((line.split(":", 1)[1].strip() for line in sprint_context.splitlines() if line.startswith("Sprint:")), "Sin milestone")
    batch_result = construir_resultado_lote(project_name, milestone, final["resultados"])
    for result in batch_result["issues"]:
        iid = result["issue_iid"]
        result["issue_data"] = issue_data_by_iid[iid]
        result["comment_published"] = False
        if result["status"] != "ok":
            logger.error("Issue #%s incompleto: %s", iid, "; ".join(result["errors"]))
            continue

        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        content_hash = calcular_hash_issue(result["issue_data"])
        comment = construir_comentario_issue(result)
        try:
            adapter.agregar_comentario(iid, comment)
            old_labels = issues_by_iid[iid].labels
            removed = {"Pendiente", "En revisión", "Analizado", "Error de análisis"}
            labels = [x for x in old_labels if x not in removed and not x.startswith(("Calidad:", "Seguridad:", "Veredicto:"))]
            labels.extend([
                "Analizada", f"Calidad:{extraer_porcentaje(quality['indice'])}",
                f"Seguridad:{extraer_porcentaje(security['indice'])}",
                f"Veredicto:{evaluation['veredicto']}",
            ])
            adapter.actualizar_etiquetas(iid, list(dict.fromkeys(labels)))
            result["comment_published"] = True
        except Exception as exc:
            result["gitlab_error"] = str(exc)
            logger.exception("No se pudo actualizar GitLab para Issue #%s", iid)

        insertar_o_actualizar_issue(iid, content_hash, "Analizada")
        guardar_historial(iid, quality["indice"], security["indice"], evaluation["veredicto"], execution_time / len(issues), evaluation.get("conclusion", ""))
        guardar_cache(content_hash, SCHEMA_VERSION, central, quality, security, evaluation)

    logger.info("Flujo de lote terminado en %.2fs.", execution_time)
    return batch_result
