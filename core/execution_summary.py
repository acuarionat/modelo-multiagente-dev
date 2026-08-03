"""Persistencia temporal de resúmenes técnicos sin contenido sensible."""

import json
import tempfile
from pathlib import Path
from typing import Any


def sanitized_error(error: Exception | None) -> dict[str, Any]:
    if error is None:
        return {}
    return {
        key: value for key, value in {
            "error_category": getattr(error, "category", type(error).__name__),
            "http_status": getattr(error, "http_status", None),
            "retry_after_seconds": getattr(error, "retry_after_seconds", None),
            "agent": getattr(error, "agent", None),
            "sub_batch": getattr(error, "sub_batch", None),
            "issue_ids": getattr(error, "issue_ids", None),
            "finish_reason": getattr(error, "finish_reason", None),
            "execution_id": getattr(error, "execution_id", None),
            "artifact_type": getattr(error, "artifact_type", None),
            "artifact_stage": getattr(error, "artifact_stage", None),
            "failed_function": getattr(error, "failed_function", None),
            "exception_type": getattr(error, "exception_type", None),
            "field": getattr(error, "field", None),
            "issue_iid": getattr(error, "issue_iid", None),
            "partial_files_created": getattr(error, "partial_files_created", None),
            "partial_files_removed": getattr(error, "partial_files_removed", None),
            "documents_generated": getattr(error, "documents_generated", None),
            "summary_persisted": getattr(error, "summary_persisted", None),
        }.items() if value is not None
    }


def build_sanitized_execution_summary(
    *, execution_id: str, estado: str, etapa_alcanzada: str, auditoria: dict[str, Any],
    historias_esperadas: list[int], historias_completas: list[int], error: Exception | None = None,
    artefactos: dict[str, str] | None = None, gitlab_usado: bool = False,
) -> dict[str, Any]:
    complete = list(dict.fromkeys(int(value) for value in historias_completas))
    expected = [int(value) for value in historias_esperadas]
    error_data = sanitized_error(error)
    remote_partial = auditoria.get("resumen_parcial_remoto", {})
    return {
        "execution_id": execution_id,
        "estado_tecnico": estado,
        "etapa_alcanzada": etapa_alcanzada,
        "agente_activo": error_data.get("agent") or remote_partial.get("active_agent"),
        "sub_batch_activo": error_data.get("sub_batch") or remote_partial.get("active_sub_batch"),
        "historias_esperadas": expected,
        "historias_completas": complete,
        "historias_pendientes": [iid for iid in expected if iid not in complete],
        "llamadas_ollama": auditoria.get("llamadas_ollama", 0),
        "llamadas_remotas": auditoria.get("llamadas_remotas", 0),
        "reintentos": auditoria.get("reintentos", 0),
        "reparaciones": auditoria.get("motivos_reparacion", {}),
        "fallbacks": auditoria.get("fallbacks_locales", 0),
        "duraciones": auditoria.get("duraciones_por_agente", {}),
        "eventos_remotos": auditoria.get("eventos_sublotes_remotos", []),
        "quality_input_prepared": auditoria.get("quality_input_prepared", {}),
        **error_data,
        "artefactos": dict(artefactos or {}),
        "gitlab_usado": bool(gitlab_usado),
    }


def persist_sanitized_execution_summary(
    summary: dict[str, Any], directory: str | Path | None = None,
) -> Path:
    root = Path(directory) if directory else Path(tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{summary['execution_id']}-summary.json"
    persisted = dict(summary)
    persisted["resumen_json_temporal"] = str(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(persisted, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
