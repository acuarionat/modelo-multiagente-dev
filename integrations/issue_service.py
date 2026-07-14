import json
import logging
import time

from core.graph import build_graph
from core.utils import extract_percentage
from database.repository import compute_issue_hash, save_cache, save_history, upsert_issue
from integrations.gitlab_adapter import GitLabAdapter
from integrations.issue_mapper import map_issue_to_json

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "v3-batch-contract"


def _metric_lines(metrics: dict) -> str:
    lines = []
    for name, detail in metrics.items():
        if not isinstance(detail, dict):
            continue
        label = name.replace("_", " ").capitalize()
        value = extract_percentage(detail.get("valor"))
        explanation = detail.get("justificacion", "")
        lines.append(f"- **{label}:** {value}. {explanation}")
    return "\n".join(lines)


def build_issue_comment(result: dict) -> str:
    central = result["central"]
    quality = result["quality"]
    security = result["security"]
    evaluation = result["evaluation"]
    requirements = "\n".join(
        f"- **{r['id']} — {r.get('nombre', '')}:** {r.get('descripcion', '')}"
        for r in central["requerimientos"]
    )
    recommendations = list(dict.fromkeys(
        quality.get("recomendaciones", [])
        + security.get("recomendaciones", [])
        + evaluation.get("correcciones_obligatorias", [])
    ))
    recommendation_text = "\n".join(f"- {x}" for x in recommendations) or "- Sin correcciones obligatorias."
    next_action = (
        "Actualizar la Historia con las correcciones obligatorias y marcarla como **En revisión**."
        if evaluation["veredicto"] in {"CORREGIR", "ALERTA"}
        else "Mantener la Historia como **Analizada** y continuar con la siguiente etapa."
    )
    return f"""## Resultado del análisis multiagente

**Veredicto:** {evaluation['veredicto']}  
**Calidad:** {extract_percentage(quality['indice'])}  
**Seguridad:** {extract_percentage(security['indice'])}  
**Nivel de confianza:** {security.get('lot_recomendado', 'No informado')}

### Evaluación de calidad
{_metric_lines(quality.get('metricas', {}))}

### Evaluación de seguridad
{_metric_lines(security.get('metricas', {}))}

### Requerimientos formalizados sugeridos
{requirements}

### Correcciones y recomendaciones
{recommendation_text}

### Próxima acción
{next_action}
"""


def process_batch_workflow(issues: list, project_name: str, sprint_context: str = "") -> list:
    adapter = GitLabAdapter()
    issues_data = [map_issue_to_json(issue) for issue in issues]
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
    }
    logger.info("Iniciando ejecución del grafo multiagente para %s historias.", len(issues))
    started = time.time()
    final_state = {}
    for output in build_graph().stream(initial_state):
        for value in output.values():
            final_state.update(value)
    execution_time = time.time() - started
    final = json.loads(final_state["final_report"])
    issue_data_by_iid = {int(item["id"]): item for item in issues_data}

    for result in final["resultados"]:
        iid = result["issue_iid"]
        result["issue_data"] = issue_data_by_iid[iid]
        result["comment_published"] = False
        if result["status"] != "ok":
            logger.error("Issue #%s incompleto: %s", iid, "; ".join(result["errors"]))
            continue

        central, quality = result["central"], result["quality"]
        security, evaluation = result["security"], result["evaluation"]
        content_hash = compute_issue_hash(result["issue_data"])
        comment = build_issue_comment(result)
        try:
            adapter.add_comment(iid, comment)
            old_labels = issues_by_iid[iid].labels
            removed = {"Pendiente", "En revisión", "Analizado", "Error de análisis"}
            labels = [x for x in old_labels if x not in removed and not x.startswith(("Calidad:", "Seguridad:", "Veredicto:"))]
            labels.extend([
                "Analizada", f"Calidad:{extract_percentage(quality['indice'])}",
                f"Seguridad:{extract_percentage(security['indice'])}",
                f"Veredicto:{evaluation['veredicto']}",
            ])
            adapter.update_labels(iid, list(dict.fromkeys(labels)))
            result["comment_published"] = True
        except Exception as exc:
            result["gitlab_error"] = str(exc)
            logger.exception("No se pudo actualizar GitLab para Issue #%s", iid)

        upsert_issue(iid, content_hash, "Analizada")
        save_history(iid, quality["indice"], security["indice"], evaluation["veredicto"], execution_time / len(issues), evaluation.get("conclusion", ""))
        save_cache(content_hash, SCHEMA_VERSION, central, quality, security, evaluation)

    logger.info("Flujo de lote terminado en %.2fs.", execution_time)
    return final["resultados"]
