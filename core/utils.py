import io
import csv
import hashlib
import os
import shutil
from datetime import datetime
from copy import deepcopy
import json
import logging
from pathlib import Path
import unicodedata
import re
from difflib import SequenceMatcher
from core.batch_contract import (
    normalizar_tipo_requerimiento,
    renumerar_requerimientos,
)

logger = logging.getLogger(__name__)

RESTRICTION_TEXT_FIELDS = (
    "restriccion", "descripcion", "texto", "mensaje", "regla", "condicion",
    "detalle", "contenido",
)
DOCUMENT_TEXT_FIELDS = (
    "recomendacion", "descripcion", "mensaje", "accion", "detalle", "texto",
)


class DocumentModelValidationError(ValueError):
    category = "DOCUMENT_MODEL_VALIDATION_ERROR"

    def __init__(self, errors):
        super().__init__("El modelo documental contiene campos no representables.")
        self.errors = list(errors)
        first = self.errors[0] if self.errors else {}
        self.issue_iid = first.get("issue_iid")
        self.field = first.get("field")
        self.artifact_stage = "document_model_validation"


class ArtifactGenerationError(RuntimeError):
    category = "ARTIFACT_GENERATION_ERROR"

    def __init__(self, message, *, execution_id, artifact_type, artifact_stage,
                 failed_function, exception_type, field=None, issue_iid=None,
                 partial_files_created=0, partial_files_removed=False,
                 summary_persisted=False):
        super().__init__(message)
        self.execution_id = execution_id
        self.artifact_type = artifact_type
        self.artifact_stage = artifact_stage
        self.failed_function = failed_function
        self.exception_type = exception_type
        self.field = field
        self.issue_iid = issue_iid
        self.partial_files_created = partial_files_created
        self.partial_files_removed = partial_files_removed
        self.documents_generated = False
        self.summary_persisted = summary_persisted


def _hash_elemento_documental(value) -> str:
    descriptor = f"{type(value).__name__}:"
    if isinstance(value, dict):
        descriptor += ",".join(sorted(str(key) for key in value))
    elif isinstance(value, (list, tuple)):
        descriptor += str(len(value))
    return hashlib.sha256(descriptor.encode("utf-8")).hexdigest()[:12]


def deduplicar_textos_estables(textos):
    unique, seen = [], set()
    for value in textos:
        if not isinstance(value, str):
            continue
        clean = " ".join(value.split()).strip()
        key = clean.casefold()
        if clean and key not in seen:
            unique.append(clean)
            seen.add(key)
    return unique


def normalizar_restricciones_documentales(valor, contexto=None, auditoria=None):
    """Extrae solo texto semántico conocido; nunca serializa objetos completos."""
    context = dict(contexto or {})
    audit = auditoria if isinstance(auditoria, list) else []
    output = []

    def record(item, strategy, success):
        audit.append({
            "issue_iid": context.get("issue_iid"),
            "historia_id": context.get("historia_id"),
            "campo": "central.restricciones",
            "item_type": type(item).__name__,
            "object_keys": sorted(str(key) for key in item) if isinstance(item, dict) else [],
            "extraction_strategy": strategy,
            "extraction_success": bool(success),
            "element_hash": _hash_elemento_documental(item),
            "artifact_stage": context.get("artifact_stage", "document_model_preparation"),
            "artifact_type": context.get("artifact_type", "shared"),
        })

    def extract(item):
        if item is None:
            return
        if isinstance(item, str):
            clean = " ".join(item.split()).strip()
            if clean:
                output.append(clean)
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                extract(nested)
            return
        if isinstance(item, dict):
            before = len(output)
            if "restricciones" in item:
                extract(item.get("restricciones"))
                record(item, "collection:restricciones", len(output) > before)
                return
            for field in RESTRICTION_TEXT_FIELDS:
                value = item.get(field)
                if isinstance(value, str) and value.strip():
                    output.append(" ".join(value.split()).strip())
                    record(item, f"field:{field}", True)
                    return
                if isinstance(value, (list, tuple, dict)):
                    extract(value)
                    if len(output) > before:
                        record(item, f"field:{field}:recursive", True)
                        return
            record(item, "unrecognized", False)
            return
        record(item, "unsupported_type", False)

    extract(valor)
    return deduplicar_textos_estables(output)


def _normalizar_lista_textual_documental(value, fields=DOCUMENT_TEXT_FIELDS):
    output = []

    def extract(item):
        if item is None:
            return
        if isinstance(item, str):
            clean = " ".join(item.split()).strip()
            if clean:
                output.append(clean)
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                extract(nested)
            return
        if isinstance(item, dict):
            for field in fields:
                nested = item.get(field)
                if isinstance(nested, (str, list, tuple, dict)):
                    before = len(output)
                    extract(nested)
                    if len(output) > before:
                        return

    extract(value)
    return deduplicar_textos_estables(output)


def preparar_modelo_documental(batch_result: dict) -> dict:
    """Construye una copia compartida y representable para PDF, DOCX y CSV."""
    model = deepcopy(batch_result)
    audit = {
        "document_model_validation": "pending",
        "document_model_error_count": 0,
        "restrictions_items_before": 0,
        "restrictions_items_after": 0,
        "structured_restrictions_normalized": 0,
        "malformed_restrictions_removed": 0,
        "by_issue": [],
    }
    diagnostics = []
    for result in model.get("issues", []):
        if not isinstance(result, dict):
            continue
        central = result.get("central") if isinstance(result.get("central"), dict) else {}
        raw = central.get("restricciones")
        before_items = len(raw) if isinstance(raw, (list, tuple)) else (0 if raw in (None, "", {}) else 1)
        structured = sum(isinstance(item, dict) for item in raw) if isinstance(raw, (list, tuple)) else int(isinstance(raw, dict))
        local_diagnostics = []
        normalized = normalizar_restricciones_documentales(raw, {
            "issue_iid": result.get("issue_iid"),
            "historia_id": central.get("historia_id"),
        }, local_diagnostics)
        central["restricciones"] = normalized
        result["correcciones_necesarias"] = (
            _normalizar_lista_textual_documental(
                result.get("correcciones_necesarias")
            )
        )
        result["mejoras_sugeridas"] = (
            _normalizar_lista_textual_documental(
                result.get("mejoras_sugeridas")
            )
        )
        brechas = (
            result.get("para_alcanzar_100")
            if isinstance(
                result.get("para_alcanzar_100"),
                dict,
            )
            else {}
        )
        result["para_alcanzar_100"] = {
            "calidad": _normalizar_lista_textual_documental(
                brechas.get("calidad")
            ),
            "seguridad": _normalizar_lista_textual_documental(
                brechas.get("seguridad")
            ),
        }
        estado_orientativo = str(
            result.get("estado_orientativo") or ""
        ).strip()
        if estado_orientativo:
            result["estado_orientativo"] = estado_orientativo
        result["recommendations"] = _normalizar_lista_textual_documental(result.get("recommendations"))
        evaluation = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        evaluation["riesgos_criticos"] = _normalizar_lista_textual_documental(
            evaluation.get("riesgos_criticos"),
            ("riesgo", "descripcion", "mensaje", "detalle", "texto"),
        )
        audit["restrictions_items_before"] += before_items
        audit["restrictions_items_after"] += len(normalized)
        audit["structured_restrictions_normalized"] += sum(
            entry["extraction_success"] and entry["item_type"] == "dict"
            for entry in local_diagnostics
        )
        malformed = sum(not entry["extraction_success"] for entry in local_diagnostics)
        audit["malformed_restrictions_removed"] += malformed
        audit["by_issue"].append({
            "issue_iid": result.get("issue_iid"),
            "restriction_count_before": before_items,
            "restriction_count_after": len(normalized),
            "structured_item_count": structured,
            "unrecognized_item_count": malformed,
        })
        diagnostics.extend(local_diagnostics)
    model["recommendations"] = _normalizar_lista_textual_documental(model.get("recommendations"))
    model["documentary_audit"] = audit
    model["documentary_diagnostics"] = diagnostics
    model["_document_model_prepared"] = True
    return model


def validar_modelo_documental(model: dict, *, expected_issue_ids=None,
                              expected_rf=None, expected_rnf=None):
    errors = []
    issues = model.get("issues") if isinstance(model, dict) else None
    if not isinstance(issues, list):
        errors.append({"field": "issues", "category": "invalid_type"})
        issues = []
    traceable, codes, rf_count, rnf_count = [], [], 0, 0
    for result in issues:
        if not isinstance(result, dict):
            errors.append({"field": "issues[]", "category": "invalid_type"})
            continue
        iid = result.get("issue_iid")
        traceable.append(iid)
        central = result.get("central") if isinstance(result.get("central"), dict) else {}
        for field in ("actor", "objetivo"):
            if not isinstance(central.get(field, ""), str):
                errors.append({"issue_iid": iid, "field": f"central.{field}", "category": "invalid_type"})
        for field, value in (
            ("central.restricciones", central.get("restricciones", [])),
            ("recommendations", result.get("recommendations", [])),
            ("evaluation.riesgos_criticos", (result.get("evaluation") or {}).get("riesgos_criticos", [])),
            (
                "correcciones_necesarias",
                result.get(
                    "correcciones_necesarias",
                    [],
                ),
            ),
            (
                "mejoras_sugeridas",
                result.get(
                    "mejoras_sugeridas",
                    [],
                ),
            ),
        ):
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors.append({"issue_iid": iid, "field": field, "category": "non_textual_item"})
        brechas = result.get(
            "para_alcanzar_100",
            {},
        )
        if not isinstance(brechas, dict):
            errors.append({
                "issue_iid": iid,
                "field": "para_alcanzar_100",
                "category": "invalid_type",
            })
        else:
            for campo in ("calidad", "seguridad"):
                values = brechas.get(campo, [])
                if (
                    not isinstance(values, list)
                    or any(
                        not isinstance(item, str)
                        for item in values
                    )
                ):
                    errors.append({
                        "issue_iid": iid,
                        "field": (
                            f"para_alcanzar_100.{campo}"
                        ),
                        "category": "non_textual_item",
                    })
        requirements = central.get("requerimientos", [])
        if not isinstance(requirements, list):
            errors.append({"issue_iid": iid, "field": "central.requerimientos", "category": "invalid_type"})
            requirements = []
        for requirement in requirements:
            if not isinstance(requirement, dict):
                errors.append({"issue_iid": iid, "field": "central.requerimientos[]", "category": "invalid_type"})
                continue
            code = requirement.get("id")
            kind = normalizar_tipo_requerimiento(requirement)
            description = requirement.get("descripcion_formal") or requirement.get("descripcion")
            if not isinstance(code, str) or not code.strip():
                errors.append({"issue_iid": iid, "field": "requerimiento.id", "category": "empty_code"})
            else:
                codes.append(code)
            if kind not in {"RF", "RNF"}:
                errors.append({"issue_iid": iid, "field": "requerimiento.tipo", "category": "invalid_type"})
            elif kind == "RF":
                rf_count += 1
            else:
                rnf_count += 1
            if not isinstance(description, str) or not description.strip():
                errors.append({"issue_iid": iid, "field": "requerimiento.descripcion", "category": "invalid_text"})
        for report_name in ("quality", "security"):
            report = result.get(report_name)
            if not isinstance(report, dict):
                continue
            index = report.get("indice")
            if index is not None and not isinstance(index, (int, float)):
                errors.append({"issue_iid": iid, "field": f"{report_name}.indice", "category": "invalid_metric"})
    if expected_issue_ids is not None and list(traceable) != list(expected_issue_ids):
        errors.append({"field": "issues.issue_iid", "category": "identity_mismatch"})
    if len(codes) != len(set(codes)):
        errors.append({"field": "requerimiento.id", "category": "duplicate_code"})
    if expected_rf is not None and rf_count != expected_rf:
        errors.append({"field": "requirements.RF", "category": "unexpected_count", "actual": rf_count})
    if expected_rnf is not None and rnf_count != expected_rnf:
        errors.append({"field": "requirements.RNF", "category": "unexpected_count", "actual": rnf_count})
    if errors:
        model.get("documentary_audit", {})["document_model_validation"] = "error"
        model.get("documentary_audit", {})["document_model_error_count"] = len(errors)
        raise DocumentModelValidationError(errors)
    model.get("documentary_audit", {})["document_model_validation"] = "success"
    return {"issue_ids": traceable, "rf": rf_count, "rnf": rnf_count, "codes": codes}

TRACEABILITY_COLUMNS = (
    "Código", "Nombre", "Descripción", "Tipo", "Historia de origen",
    "Fecha de generación", "Estado de cumplimiento",
)
COMPLIANCE_STATES = {
    "Cumple", "Cumple parcialmente", "No cumple",
    "Pendiente de revisión", "No evaluado",
}

DECISION_SUPPORT_NOTICE = (
    "El modelo multiagente apoya el control, seguimiento y trazabilidad del desarrollo. "
    "Sus métricas, evidencias y recomendaciones son orientativas, no constituyen certificación automática "
    "ni sustituyen la revisión y decisión del responsable del proyecto."
)

def limpiar_texto_para_pdf(text: str) -> str:
    """Limpia el texto para evitar problemas con la fuente base de FPDF."""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return text.replace('\r', '')

def extraer_porcentaje(val) -> str:
    if isinstance(val, (int, float)):
        return f"{round(val * 100)} %"
    return "No evaluado" if val is None else str(val)


def _iterar_textos(value, context: str):
    if value in (None, "", []):
        return
    if isinstance(value, str):
        clean = value.strip()
        if clean:
            yield clean
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                yield item.strip()
            elif item not in (None, "", []):
                logger.warning("%s contiene un valor no textual de tipo %s.", context, type(item).__name__)
        return
    logger.warning("%s tiene una estructura inesperada de tipo %s.", context, type(value).__name__)


def _iterar_metricas(report, context: str):
    if not isinstance(report, dict):
        logger.warning("%s no es un diccionario; se omite el bloque.", context)
        return
    metrics = report.get("metricas")
    if metrics in (None, "", []):
        return
    if not isinstance(metrics, dict):
        logger.warning("%s.metricas tiene tipo %s; se omite.", context, type(metrics).__name__)
        return
    for name, metric in metrics.items():
        if isinstance(metric, dict):
            yield str(name), metric
        elif name in {"observaciones", "recomendaciones"}:
            continue
        elif metric not in (None, "", []):
            logger.warning(
                "%s.metricas.%s tiene tipo %s y no se procesa como métrica.",
                context, name, type(metric).__name__,
            )


def _fecha_visible(value) -> str:
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        logger.warning("Fecha de generación inesperada %r; se conserva como texto.", value)
        return text


def _normalizar_requerimientos_visibles(batch_results: list, generation_date: str) -> None:
    centrals = [
        result.get("central", {}) for result in batch_results
        if isinstance(result, dict) and result.get("status") == "ok"
        and isinstance(result.get("central"), dict)
    ]
    for central in centrals:
        requirements = central.get("requerimientos")
        if not isinstance(requirements, list):
            logger.warning("'requerimientos' no es una lista para %r.", central.get("historia_id"))
            central["requerimientos"] = []
            continue
        for requirement in requirements:
            if isinstance(requirement, dict):
                requirement.setdefault("fecha_generacion", generation_date)
            else:
                logger.warning("Requerimiento inesperado de tipo %s ignorado.", type(requirement).__name__)
    renumerar_requerimientos(centrals)


def construir_filas_trazabilidad(batch_results: list, generation_date: str | None = None) -> list:
    generation_date = generation_date or datetime.now().date().isoformat()
    _normalizar_requerimientos_visibles(batch_results, generation_date)
    rows = []
    for result in batch_results:
        if not isinstance(result, dict) or result.get("status") != "ok":
            continue
        central = result.get("central", {})
        if not isinstance(central, dict):
            logger.warning("Bloque central inesperado para Issue %r.", result.get("issue_iid"))
            continue
        iid = result.get("issue_iid", 0)
        history_id = central.get("historia_id") or (f"HU-{iid:03d}" if isinstance(iid, int) else "HU")
        history = f"{history_id} – {central.get('titulo', 'Sin título')}"
        for requirement in central.get("requerimientos", []):
            if not isinstance(requirement, dict):
                continue
            kind = normalizar_tipo_requerimiento(requirement)
            state = requirement.get("estado_cumplimiento")
            if state not in COMPLIANCE_STATES:
                state = "Pendiente de revisión"
            rows.append({
                "Código": requirement.get("id", ""),
                "Nombre": requirement.get("nombre", ""),
                "Descripción": requirement.get("descripcion_formal") or requirement.get("descripcion", ""),
                "Tipo": "Funcional" if kind == "RF" else "No funcional",
                "Historia de origen": history,
                "Fecha de generación": _fecha_visible(requirement.get("fecha_generacion")),
                "Estado de cumplimiento": state,
            })
    if not rows:
        raise ValueError("No fue posible construir la matriz porque el Agente Central no devolvió requerimientos formalizados.")
    return rows


def calcular_resumen_lote(batch_results: list) -> dict:
    traceable = [
        x for x in batch_results if isinstance(x, dict)
        and x.get("issue_iid") is not None and isinstance(x.get("central"), dict)
    ]
    valid = [x for x in traceable if x.get("status") == "ok"]
    quality = [
        x["quality"]["indice"] for x in valid
        if isinstance(x.get("quality"), dict)
        and isinstance(x["quality"].get("indice"), (int, float))
    ]
    security = [
        x["security"]["indice"] for x in valid
        if isinstance(x.get("security"), dict)
        and isinstance(x["security"].get("indice"), (int, float))
    ]
    verdicts = {}
    for item in valid:
        evaluation = item.get("evaluation") if isinstance(item.get("evaluation"), dict) else {}
        verdict = evaluation.get("veredicto", "NO_EVALUADO")
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    insufficient = [
        x for x in batch_results if isinstance(x, dict)
        and x.get("estado_procesamiento") == "informacion_insuficiente"
    ]
    critical_risks = sum(
        len(list(_iterar_textos(
            x.get("evaluation", {}).get("riesgos_criticos")
            if isinstance(x.get("evaluation"), dict) else None,
            "evaluador.riesgos_criticos",
        )))
        for x in valid
    )
    below_target = sum(
        (
            isinstance(x.get("quality"), dict)
            and isinstance(x["quality"].get("indice"), (int, float))
            and x["quality"]["indice"] < 0.95
        )
        or (
            isinstance(x.get("security"), dict)
            and isinstance(x["security"].get("indice"), (int, float))
            and x["security"]["indice"] < 0.85
        )
        for x in valid
    )
    estados_orientativos = {}
    for item in valid:
        estado = str(
            item.get(
                "estado_orientativo",
                "REVISIÓN HUMANA",
            )
        ).strip()
        estados_orientativos[estado] = (
            estados_orientativos.get(
                estado,
                0,
            )
            + 1
        )
    return {
        "total": len(batch_results),
        "procesadas": len(traceable),
        "evaluables_calidad": len(quality),
        "evaluables_seguridad": len(security),
        "no_evaluables_calidad": len(traceable) - len(quality),
        "no_evaluables_seguridad": len(traceable) - len(security),
        "errores": sum(x.get("status") == "error" for x in batch_results if isinstance(x, dict)),
        "veredictos": verdicts,
        "calidad_promedio": sum(quality) / len(quality) if quality else None,
        "seguridad_promedio": sum(security) / len(security) if security else None,
        "requerimientos": sum(
            len(x["central"].get("requerimientos", []))
            for x in valid if isinstance(x.get("central"), dict)
            and isinstance(x["central"].get("requerimientos", []), list)
        ),
        "aprobadas": verdicts.get("APROBADO", 0),
        "requieren_correccion": verdicts.get("CORREGIR", 0),
        "alertas": verdicts.get("ALERTA", 0),
        "informacion_insuficiente": len(insufficient),
        "calidad_minima": min(quality) if quality else None,
        "seguridad_minima": min(security) if security else None,
        "historias_bajo_meta": below_target,
        "riesgos_criticos": critical_risks,
        "estados_orientativos": estados_orientativos,
        "conformes": estados_orientativos.get(
            "CONFORME",
            0,
        ),
        "conformes_con_mejoras": estados_orientativos.get(
            "CONFORME CON MEJORAS",
            0,
        ),
        "revision_humana": estados_orientativos.get(
            "REVISIÓN HUMANA",
            0,
        ),
    }


def _eliminar_recomendaciones_duplicadas(values: list) -> list:
    unique = []
    normalized = []
    for value in values:
        clean = " ".join(str(value).split()).strip()
        key = re.sub(r"[^a-z0-9áéíóúñ ]", "", clean.casefold())
        if not clean or any(SequenceMatcher(None, key, previous).ratio() >= 0.88 for previous in normalized):
            continue
        unique.append(clean)
        normalized.append(key)
    return unique


def construir_resultado_lote(project_name: str, milestone: str, issues: list) -> dict:
    generated_at = datetime.now().isoformat(timespec="seconds")
    valid = [item for item in issues if item.get("status") == "ok"]
    requirements = [
        requirement for item in valid
        for requirement in item["central"].get("requerimientos", [])
    ]
    correcciones_necesarias = deduplicar_textos_estables(
        correction
        for item in valid
        for correction in item.get(
            "correcciones_necesarias",
            [],
        )
    )
    mejoras_sugeridas = deduplicar_textos_estables(
        improvement
        for item in valid
        for improvement in item.get(
            "mejoras_sugeridas",
            [],
        )
    )
    # Se conserva únicamente por compatibilidad con consumidores legacy.
    recommendations = deduplicar_textos_estables(
        correcciones_necesarias
        + mejoras_sugeridas
    )
    try:
        traceability_rows = construir_filas_trazabilidad(issues, generated_at)
    except ValueError:
        traceability_rows = []
    return {
        "project": {"name": project_name},
        "milestone": {"name": milestone},
        "summary": calcular_resumen_lote(issues),
        "issues": issues,
        "requirements": requirements,
        "correcciones_necesarias": correcciones_necesarias,
        "mejoras_sugeridas": mejoras_sugeridas,
        "recommendations": recommendations,
        "traceability_rows": traceability_rows,
        "generated_at": generated_at,
        "descripcion_resultado": DECISION_SUPPORT_NOTICE,
        "revision_humana_requerida": True,
    }


def generar_reporte_lote_pdf(batch_result: dict) -> io.BytesIO:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    if not batch_result.get("_document_model_prepared"):
        batch_result = preparar_modelo_documental(batch_result)
    project_name = batch_result["project"]["name"]
    milestone = batch_result["milestone"]["name"]
    batch_results = batch_result["issues"]
    valid = [x for x in batch_results if x.get("status") == "ok"]
    if not valid:
        raise ValueError("No existen historias completas para generar el PDF.")
    rows = construir_filas_trazabilidad(
        batch_results, batch_result.get("generated_at") or datetime.now().date().isoformat()
    )
    batch_result["traceability_rows"] = rows
    summary = calcular_resumen_lote(batch_results)
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    kwargs = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    def encabezado(text, size=14):
        pdf.set_font("Helvetica", style="B", size=size)
        pdf.multi_cell(0, 7, limpiar_texto_para_pdf(text), **kwargs)
    def linea(text):
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, limpiar_texto_para_pdf(text), **kwargs)
    encabezado("Reporte Ejecutivo Consolidado", 16)
    linea(DECISION_SUPPORT_NOTICE)
    linea(f"Proyecto: {project_name}")
    linea(f"Milestone: {milestone}")
    linea(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    pdf.ln(4)
    encabezado("Resumen global", 13)
    linea(f"Historias procesadas: {summary['procesadas']} | Con error: {summary['errores']}")
    linea(f"Índice de Calidad de Requerimientos promedio: {extraer_porcentaje(summary['calidad_promedio'])}")
    linea(f"Índice de Seguridad en Requerimientos promedio: {extraer_porcentaje(summary['seguridad_promedio'])}")
    linea(f"Requerimientos sugeridos: {summary['requerimientos']}")
    for result in valid:
        c = result.get("central") if isinstance(result.get("central"), dict) else {}
        q = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        s = result.get("security") if isinstance(result.get("security"), dict) else {}
        e = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        pdf.add_page()
        fallback_id = f"HU-{result.get('issue_iid', '???')}"
        encabezado(f"{c.get('historia_id', fallback_id)} — {c.get('titulo', 'Sin título')}", 13)
        estado_visible = (
            result.get("estado_orientativo")
            or e.get("veredicto")
            or "REVISIÓN HUMANA"
        )
        linea(
            f"Estado orientativo: {estado_visible} | "
            f"Índice de Calidad de Requerimientos: "
            f"{extraer_porcentaje(q.get('indice'))} | "
            f"Índice de Seguridad en Requerimientos: "
            f"{extraer_porcentaje(s.get('indice'))} | "
            f"Nivel de aseguramiento recomendado - LoT: "
            f"{s.get('lot_recomendado', 'No informado')}"
        )
        linea(f"Actor: {c.get('actor', '')}")
        linea(f"Objetivo: {c.get('objetivo', '')}")
        encabezado("Métricas de calidad", 11)
        for name, metric in _iterar_metricas(q, "calidad"):
            linea(f"{metric.get('codigo', name)} — {metric.get('nombre', name)}: {extraer_porcentaje(metric.get('valor'))} ({metric.get('estado_calculo', 'No evaluado')}). {metric.get('justificacion', '')}")
            if metric.get("recomendacion"):
                linea(f"Recomendación: {metric['recomendacion']}")
        for label in ("observaciones", "recomendaciones"):
            for text_value in _iterar_textos(q.get(label), f"calidad.{label}"):
                linea(f"{label.capitalize()}: {text_value}")
        encabezado("Métricas de seguridad", 11)
        for name, metric in _iterar_metricas(s, "seguridad"):
            linea(f"{metric.get('codigo', name)} — {metric.get('nombre', name)}: {extraer_porcentaje(metric.get('valor'))} ({metric.get('estado_calculo', 'No evaluado')}). {metric.get('justificacion', '')}")
            if metric.get("recomendacion"):
                linea(f"Recomendación: {metric['recomendacion']}")
        for label in ("observaciones", "recomendaciones"):
            for text_value in _iterar_textos(s.get(label), f"seguridad.{label}"):
                linea(f"{label.capitalize()}: {text_value}")
        encabezado(
            "Correcciones necesarias",
            11,
        )
        correcciones = result.get(
            "correcciones_necesarias",
            [],
        )
        if correcciones:
            for correction in correcciones:
                linea(f"- {correction}")
        else:
            linea(
                "No se identificaron correcciones "
                "necesarias para las métricas evaluadas."
            )
        encabezado(
            "Para alcanzar el máximo de las métricas",
            11,
        )
        brechas = (
            result.get("para_alcanzar_100")
            if isinstance(
                result.get("para_alcanzar_100"),
                dict,
            )
            else {}
        )
        calidad_brechas = brechas.get(
            "calidad",
            [],
        )
        seguridad_brechas = brechas.get(
            "seguridad",
            [],
        )
        linea("Calidad:")
        if calidad_brechas:
            for gap in calidad_brechas:
                linea(f"- {gap}")
        else:
            linea(
                "Las métricas de Calidad evaluadas "
                "ya alcanzan el 100 %."
            )
        linea("Seguridad:")
        if seguridad_brechas:
            for gap in seguridad_brechas:
                linea(f"- {gap}")
        else:
            linea(
                "Las métricas de Seguridad evaluadas "
                "ya alcanzan el 100 %."
            )
        mejoras = result.get(
            "mejoras_sugeridas",
            [],
        )
        if mejoras:
            encabezado(
                "Oportunidades de mejora",
                11,
            )
            for improvement in mejoras:
                linea(f"- {improvement}")
        encabezado(
            "Formalización propuesta",
            11,
        )
        for requirement in c.get("requerimientos", []):
            if not isinstance(requirement, dict):
                logger.warning("Requerimiento no válido omitido del PDF: %r.", requirement)
                continue
            linea(f"{requirement.get('id', 'Sin código')} — {requirement.get('nombre', '')}")
            linea(requirement.get("descripcion_formal", ""))
            linea(f"Procedencia: {requirement.get('procedencia', 'inferida')}")
    pdf.add_page(orientation="L")
    encabezado("Matriz de trazabilidad", 13)
    pdf.set_font("Helvetica", size=6)
    table_rows = [list(TRACEABILITY_COLUMNS)] + [
        [limpiar_texto_para_pdf(row.get(column, "")) for column in TRACEABILITY_COLUMNS]
        for row in rows
    ]
    with pdf.table(
        rows=table_rows, col_widths=(18, 28, 58, 22, 48, 26, 32),
        line_height=4, text_align=("CENTER", "LEFT", "LEFT", "CENTER", "LEFT", "CENTER", "CENTER"),
    ):
        pass
    return io.BytesIO(bytes(pdf.output()))


def agregar_requerimiento_docx(
    doc,
    requirement: dict,
    origin: str,
) -> None:
    code = str(
        requirement.get("id") or ""
    ).strip()

    name = str(
        requirement.get("nombre") or ""
    ).strip()

    doc.add_heading(
        f"{code} — {name}",
        3,
    )

    doc.add_paragraph(
        str(
            requirement.get(
                "descripcion_formal",
                "",
            )
        )
    )

    kind = normalizar_tipo_requerimiento(
        requirement
    )

    doc.add_paragraph(
        "Tipo: "
        + (
            "Funcional"
            if kind == "RF"
            else "No funcional"
        )
    )

    doc.add_paragraph(
        "Prioridad: "
        + str(
            requirement.get(
                "prioridad",
                "Desconocida",
            )
        )
    )

    doc.add_paragraph(
        f"Origen: {origin}"
    )

    justification = str(
        requirement.get(
            "justificacion",
            "",
        )
    ).strip()

    if justification:
        doc.add_paragraph(
            f"Justificación: {justification}"
        )

    doc.add_paragraph(
        "Procedencia: "
        + str(
            requirement.get(
                "procedencia",
                "inferida",
            )
        )
    )

    doc.add_paragraph(
        "Revisión humana: Pendiente"
    )

    pending = (
        requirement.get(
            "pendientes_definicion"
        )
        or requirement.get(
            "observaciones_revision"
        )
        or []
    )

    pending = (
        _normalizar_lista_textual_documental(
            pending
        )
    )

    if pending:
        doc.add_paragraph(
            "Aspectos pendientes de definición:"
        )

        for value in pending:
            doc.add_paragraph(
                value,
                style="List Bullet",
            )


def generar_documento_formal_lote_docx(batch_result: dict) -> io.BytesIO:
    from docx import Document
    if not batch_result.get("_document_model_prepared"):
        batch_result = preparar_modelo_documental(batch_result)
    project_name = batch_result["project"]["name"]
    milestone = batch_result["milestone"]["name"]
    batch_results = batch_result["issues"]
    valid = [x for x in batch_results if x.get("status") == "ok"]
    if not valid:
        raise ValueError("No existen historias completas para generar el DOCX.")
    rows = construir_filas_trazabilidad(
        batch_results, batch_result.get("generated_at") or datetime.now().date().isoformat()
    )
    batch_result["traceability_rows"] = rows
    doc = Document()
    doc.add_heading("Documento Formal Consolidado de Requerimientos", 0)
    doc.add_paragraph(DECISION_SUPPORT_NOTICE)
    doc.add_heading("Información general", 1)
    doc.add_paragraph(f"Proyecto: {project_name}")
    doc.add_paragraph(f"Milestone: {milestone}")
    doc.add_paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    doc.add_paragraph("Versión: 1.0")
    doc.add_paragraph(f"Historias analizadas: {len(valid)}")
    doc.add_page_break()
    doc.add_heading("1. Introducción", 1)
    doc.add_paragraph(
        (
            "El presente documento constituye el "
            "artefacto formal consolidado de la etapa "
            "de Recepción de Requerimientos. Integra "
            "los requerimientos funcionales y no "
            "funcionales identificados, las restricciones, "
            "las consideraciones de seguridad y los "
            "aspectos pendientes de definición derivados "
            "de las Historias de Usuario analizadas."
        )
    )
    doc.add_heading("2. Alcance", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective:
            doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading("3. Actores identificados", 1)
    for actor in dict.fromkeys(x["central"].get("actor", "") for x in valid):
        if actor:
            doc.add_paragraph(actor, style="List Bullet")
    doc.add_heading("4. Objetivos identificados", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective:
            doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading(
        "5. Requerimientos funcionales formalizados",
        1,
    )
    rf_encontrados = False
    for result in valid:
        central = result["central"]
        fallback_id = (
            f"HU-{result.get('issue_iid', '???')}"
        )
        origin = (
            f"{central.get('historia_id', fallback_id)} "
            f"— {central.get('titulo', 'Sin título')}"
        )
        for requirement in central.get(
            "requerimientos",
            [],
        ):
            if not isinstance(
                requirement,
                dict,
            ):
                continue
            if normalizar_tipo_requerimiento(
                requirement
            ) != "RF":
                continue
            rf_encontrados = True
            agregar_requerimiento_docx(
                doc,
                requirement,
                origin,
            )
    if not rf_encontrados:
        doc.add_paragraph(
            "No se identificaron requerimientos "
            "funcionales formalizados."
        )
    doc.add_heading(
        "6. Requerimientos no funcionales formalizados",
        1,
    )
    rnf_encontrados = False
    for result in valid:
        central = result["central"]
        fallback_id = (
            f"HU-{result.get('issue_iid', '???')}"
        )
        origin = (
            f"{central.get('historia_id', fallback_id)} "
            f"— {central.get('titulo', 'Sin título')}"
        )
        for requirement in central.get(
            "requerimientos",
            [],
        ):
            if not isinstance(
                requirement,
                dict,
            ):
                continue
            if normalizar_tipo_requerimiento(
                requirement
            ) != "RNF":
                continue
            rnf_encontrados = True
            agregar_requerimiento_docx(
                doc,
                requirement,
                origin,
            )
    if not rnf_encontrados:
        doc.add_paragraph(
            "No se identificaron requerimientos "
            "no funcionales formalizados."
        )
    doc.add_heading(
        "7. Restricciones consolidadas",
        1,
    )
    restrictions = deduplicar_textos_estables(
        restriction
        for result in valid
        for restriction in result["central"].get("restricciones", [])
    )
    if restrictions:
        for restriction in restrictions:
            doc.add_paragraph(restriction, style="List Bullet")
    else:
        doc.add_paragraph(
            "No se identificaron restricciones consolidadas."
        )
    doc.add_heading(
        "8. Consideraciones de seguridad identificadas",
        1,
    )
    for result in valid:
        central = (
            result.get("central", {})
            if isinstance(
                result.get("central"),
                dict,
            )
            else {}
        )
        security = (
            result.get("security", {})
            if isinstance(
                result.get("security"),
                dict,
            )
            else {}
        )
        history_id = (
            central.get("historia_id")
            or f"HU-{result.get('issue_iid', '???')}"
        )
        title = central.get(
            "titulo",
            "Sin título",
        )
        doc.add_heading(
            f"{history_id} — {title}",
            3,
        )
        metrics = (
            security.get("metricas", {})
            if isinstance(
                security.get("metricas"),
                dict,
            )
            else {}
        )
        ms01 = (
            metrics.get(
                "cobertura_seguridad",
                {},
            )
            if isinstance(
                metrics.get(
                    "cobertura_seguridad",
                    {},
                ),
                dict,
            )
            else {}
        )
        ms02 = (
            metrics.get(
                "clasificacion_datos",
                {},
            )
            if isinstance(
                metrics.get(
                    "clasificacion_datos",
                    {},
                ),
                dict,
            )
            else {}
        )
        documentados = (
            _normalizar_lista_textual_documental(
                ms01.get(
                    "aspectos_documentados",
                    [],
                )
            )
        )
        faltantes = (
            _normalizar_lista_textual_documental(
                ms01.get(
                    "aspectos_faltantes",
                    [],
                )
            )
        )
        datos = (
            _normalizar_lista_textual_documental(
                ms02.get(
                    "datos_identificados",
                    [],
                )
            )
        )
        clasificados = (
            _normalizar_lista_textual_documental(
                ms02.get(
                    "datos_clasificados",
                    [],
                )
            )
        )
        sin_clasificacion = (
            _normalizar_lista_textual_documental(
                ms02.get(
                    "datos_sin_clasificacion",
                    [],
                )
            )
        )
        if datos:
            doc.add_paragraph(
                "Datos identificados:"
            )
            for value in datos:
                doc.add_paragraph(
                    value,
                    style="List Bullet",
                )
        if documentados:
            doc.add_paragraph(
                "Aspectos de seguridad documentados:"
            )
            for value in documentados:
                doc.add_paragraph(
                    value,
                    style="List Bullet",
                )
        if faltantes:
            doc.add_paragraph(
                "Aspectos de seguridad pendientes de definición:"
            )
            for value in faltantes:
                doc.add_paragraph(
                    value,
                    style="List Bullet",
                )
        if clasificados:
            doc.add_paragraph(
                "Datos con clasificación explícita:"
            )
            for value in clasificados:
                doc.add_paragraph(
                    value,
                    style="List Bullet",
                )
        if sin_clasificacion:
            doc.add_paragraph(
                "Datos pendientes de clasificación:"
            )
            for value in sin_clasificacion:
                doc.add_paragraph(
                    value,
                    style="List Bullet",
                )
    doc.add_heading(
        "9. Aspectos pendientes de definición y revisión",
        1,
    )
    hay_pendientes = False
    for result in valid:
        corrections = (
            result.get(
                "correcciones_necesarias",
                [],
            )
        )
        improvements = (
            result.get(
                "mejoras_sugeridas",
                [],
            )
        )
        pending = deduplicar_textos_estables(
            list(corrections)
            + list(improvements)
        )
        if not pending:
            continue
        hay_pendientes = True
        central = result.get(
            "central",
            {},
        )
        history_id = (
            central.get("historia_id")
            or f"HU-{result.get('issue_iid', '???')}"
        )
        title = central.get(
            "titulo",
            "Sin título",
        )
        doc.add_heading(
            f"{history_id} — {title}",
            3,
        )
        for value in pending:
            doc.add_paragraph(
                value,
                style="List Bullet",
            )
    if not hay_pendientes:
        doc.add_paragraph(
            "No se identificaron aspectos "
            "pendientes de definición o revisión."
        )
    doc.add_heading(
        "10. Matriz de trazabilidad",
        1,
    )
    matrix_keys = list(TRACEABILITY_COLUMNS)
    table = doc.add_table(rows=1, cols=len(matrix_keys))
    table.style = "Table Grid"
    headers = matrix_keys
    for cell, value in zip(table.rows[0].cells, headers): cell.text = value
    for row in rows:
        for cell, key in zip(table.add_row().cells, matrix_keys):
            cell.text = str(row.get(key, ""))
    doc.add_heading(
        "11. Control de revisión",
        1,
    )
    doc.add_paragraph(
        "Versión del documento: 1.0"
    )
    doc.add_paragraph(
        (
            "Fecha de generación: "
            f"{datetime.now().strftime('%Y-%m-%d')}"
        )
    )
    doc.add_paragraph(
        "Estado del documento: Pendiente de revisión"
    )
    doc.add_paragraph(
        (
            "Los requerimientos contenidos en este "
            "documento corresponden a una formalización "
            "asistida de la evidencia recibida durante "
            "la etapa de Recepción de Requerimientos. "
            "Los elementos señalados como pendientes "
            "requieren revisión y decisión del "
            "responsable del proyecto."
        )
    )
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output


def generar_artefactos_atomicos(
    batch_result: dict, output_dir, execution_id: str, summary_base: dict,
    *, expected_issue_ids=None, expected_rf=None, expected_rnf=None,
    pdf_generator=None, docx_generator=None, csv_rows_builder=None,
):
    """Valida, construye y publica PDF/DOCX/CSV como una sola unidad."""
    from core.execution_summary import persist_sanitized_execution_summary

    output_dir = Path(output_dir)
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    building = parent / f".building-{execution_id}"
    summary = deepcopy(summary_base)
    summary.update({
        "execution_id": execution_id,
        "status": "running",
        "documents_generated": False,
        "artefactos": {},
        "auditoria_documental": {
            "artifact_build_started": True,
            "artifact_build_completed": False,
            "artifact_build_failed": False,
            "artifact_failed_type": None,
            "temporary_artifacts_created": 0,
            "temporary_artifacts_removed": False,
            "final_artifacts_published": False,
            "summary_persisted": False,
        },
    })
    summary_path = persist_sanitized_execution_summary(summary, parent)
    summary["auditoria_documental"]["summary_persisted"] = True
    persist_sanitized_execution_summary(summary, parent)
    current_type = "document_model"
    created = 0
    try:
        if building.exists():
            shutil.rmtree(building)
        building.mkdir()
        model = preparar_modelo_documental(batch_result)
        validation = validar_modelo_documental(
            model, expected_issue_ids=expected_issue_ids,
            expected_rf=expected_rf, expected_rnf=expected_rnf,
        )
        summary["auditoria_documental"].update(model["documentary_audit"])
        summary["validacion_documental"] = validation
        generators = {
            "pdf": pdf_generator or generar_reporte_lote_pdf,
            "docx": docx_generator or generar_documento_formal_lote_docx,
        }
        for current_type, filename in (("pdf", "reporte.pdf"), ("docx", "requerimientos.docx")):
            payload = generators[current_type](model)
            data = payload.getvalue() if hasattr(payload, "getvalue") else bytes(payload)
            if not data:
                raise ValueError(f"{current_type} vacío")
            (building / filename).write_bytes(data)
            created += 1
        current_type = "csv"
        rows = (csv_rows_builder or construir_filas_trazabilidad)(
            model["issues"], model.get("generated_at")
        )
        csv_path = building / "matriz_trazabilidad.csv"
        with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=TRACEABILITY_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        created += 1
        if len(rows) != len(validation["codes"]):
            raise ValueError("La matriz no conserva todos los requerimientos validados.")
        for filename in ("reporte.pdf", "requerimientos.docx", "matriz_trazabilidad.csv"):
            if not (building / filename).is_file() or (building / filename).stat().st_size == 0:
                raise ValueError(f"Artefacto incompleto: {filename}")
        current_type = "publish"
        if output_dir.exists():
            raise FileExistsError(f"La carpeta final ya existe: {output_dir.name}")
        os.replace(building, output_dir)
        paths = {
            "pdf": str(output_dir / "reporte.pdf"),
            "docx": str(output_dir / "requerimientos.docx"),
            "csv": str(output_dir / "matriz_trazabilidad.csv"),
        }
        summary.update({"status": "success", "documents_generated": True, "artefactos": paths})
        summary["auditoria_documental"].update({
            "artifact_build_completed": True,
            "temporary_artifacts_created": created,
            "final_artifacts_published": True,
        })
        summary_path = persist_sanitized_execution_summary(summary, parent)
        return model, paths, summary_path
    except Exception as exc:
        removed = False
        if building.exists():
            shutil.rmtree(building)
            removed = True
        error = exc if isinstance(exc, ArtifactGenerationError) else ArtifactGenerationError(
            "Falló la generación atómica de artefactos.",
            execution_id=execution_id,
            artifact_type=current_type,
            artifact_stage="build" if current_type != "publish" else "atomic_publish",
            failed_function=(
                "validar_modelo_documental" if current_type == "document_model"
                else "generar_artefactos_atomicos"
            ),
            exception_type=type(exc).__name__,
            field=getattr(exc, "field", None),
            issue_iid=getattr(exc, "issue_iid", None),
            partial_files_created=created,
            partial_files_removed=removed,
            summary_persisted=True,
        )
        summary.update({
            "status": "error", "documents_generated": False, "artefactos": {},
            "error": {
                "category": error.category,
                "artifact_type": error.artifact_type,
                "artifact_stage": error.artifact_stage,
                "failed_function": error.failed_function,
                "exception_type": error.exception_type,
                "field": error.field,
                "issue_iid": error.issue_iid,
            },
        })
        summary["auditoria_documental"].update({
            "artifact_build_failed": True,
            "artifact_failed_type": current_type,
            "temporary_artifacts_created": created,
            "temporary_artifacts_removed": removed,
            "final_artifacts_published": False,
            "summary_persisted": True,
        })
        persist_sanitized_execution_summary(summary, parent)
        raise error from exc

def generar_documento_formal_docx(project_name: str, issue_iid: int, central_init: dict, quality_json: dict, security_json: dict, eval_json: dict, parsed_cf: dict) -> io.BytesIO:
    """Genera el Documento Formal de Requerimientos en Word."""
    from docx import Document
    doc = Document()
    req_id = f"REQ-{datetime.now().year}-{issue_iid:03d}"
    
    doc.add_heading('Documento Formal de Requerimientos', 0)
    doc.add_paragraph(f'ID del Documento: {req_id}')
    doc.add_paragraph(f'Proyecto: {project_name}')
    doc.add_paragraph(f'Fecha: {datetime.now().strftime("%Y-%m-%d")}')
    doc.add_page_break()
    
    doc.add_heading('1. Introducción', level=1)
    intro = f"El presente documento formaliza los requerimientos extraídos para el proyecto '{project_name}' correspondientes a la Historia de Usuario #{issue_iid}."
    doc.add_paragraph(intro)
    
    doc.add_heading('2. Alcance', level=1)
    actores = central_init.get("actores", [])
    if actores:
        doc.add_paragraph("Actores identificados:")
        for actor in actores:
            doc.add_paragraph(f"- {actor}")
            
    doc.add_heading('3. Objetivos', level=1)
    objetivos = central_init.get("objetivos_identificados", [])
    if objetivos:
        for obj in objetivos:
            doc.add_paragraph(f"- {obj}")
    else:
        doc.add_paragraph("No se identificaron objetivos específicos.")
        
    doc.add_heading('4. Requerimientos Funcionales', level=1)
    for req in central_init.get("requerimientos_funcionales", []):
        doc.add_paragraph(f"ID: {req.get('id', 'N/A')} - {req.get('nombre', 'N/A')}", style='Heading 3')
        doc.add_paragraph(f"Descripción: {req.get('descripcion_formal', 'N/A')}")
        doc.add_paragraph(f"Actor: {req.get('actor_principal', 'N/A')}")
        doc.add_paragraph(f"Prioridad: {req.get('prioridad', 'N/A')}")
        criterios = req.get("criterios_aceptacion", [])
        if criterios:
            doc.add_paragraph("Criterios de Aceptación:")
            for c in criterios:
                doc.add_paragraph(f"- {c}")
                
    doc.add_heading('5. Requerimientos No Funcionales', level=1)
    for req in central_init.get("requerimientos_no_funcionales", []):
        doc.add_paragraph(f"ID: {req.get('id', 'N/A')} - {req.get('nombre', 'N/A')}", style='Heading 3')
        doc.add_paragraph(f"Descripción: {req.get('descripcion_formal', 'N/A')}")
        
    restricciones = central_init.get("restricciones", [])
    if restricciones:
        doc.add_heading('6. Restricciones', level=1)
        for r in restricciones:
            doc.add_paragraph(f"- {r}")
            
    doc.add_heading('7. Conclusiones y Recomendaciones', level=1)
    doc.add_paragraph(parsed_cf.get("conclusiones_finales", ""))
    for rec in parsed_cf.get("recomendaciones_globales", []):
        doc.add_paragraph(f"- {rec}")
            
    doc.add_page_break()
    doc.add_heading('Matriz de Trazabilidad', level=1)
    
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    headers = ['Historia de Usuario', 'Requerimiento Formal', 'Tipo', 'Justificación']
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        
    reqs_func = central_init.get("requerimientos_funcionales", [])
    reqs_no_func = central_init.get("requerimientos_no_funcionales", [])
    requerimientos = reqs_func + reqs_no_func
    
    for r in requerimientos:
        row_cells = table.add_row().cells
        origen = str(r.get("texto_original_asociado", f"HU #{issue_iid}"))
        r_nombre = f"{r.get('id', 'N/A')} - {r.get('nombre', r.get('descripcion_formal', 'N/A'))}"
        r_tipo = "RF" if "RF-" in str(r.get("id", "")) else "RNF"
        r_justif = str(r.get("justificacion", "Generado a partir de la historia."))
        
        row_cells[0].text = origen
        row_cells[1].text = r_nombre
        row_cells[2].text = r_tipo
        row_cells[3].text = r_justif
            
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io

def generar_reporte_evaluacion_pdf(project_name: str, issue_iid: int, quality_json: dict, security_json: dict, eval_json: dict, central_init: dict, parsed_cf: dict) -> io.BytesIO:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    """Genera el Reporte Ejecutivo en PDF estructurado según el plan simplificado."""
    pdf = FPDF()
    pdf.set_margins(left=25, top=25, right=25)
    pdf.add_page()
    mc_kwargs = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}
    line_h = 6
    
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.multi_cell(0, line_h, txt=f"Reporte Ejecutivo de Requerimientos", align='C', **mc_kwargs)
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt=f"Proyecto: {limpiar_texto_para_pdf(project_name)} | HU #{issue_iid}", align='C', **mc_kwargs)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, line_h, txt=f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", align='C', **mc_kwargs)
    pdf.ln(5)
    
    # Resumen Ejecutivo
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="1. Resumen Ejecutivo", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, line_h, txt=f"Veredicto: {limpiar_texto_para_pdf(eval_json.get('veredicto', 'N/A'))}", **mc_kwargs)
    pdf.multi_cell(0, line_h, txt=limpiar_texto_para_pdf(parsed_cf.get('resumen_ejecutivo', '')), **mc_kwargs)
    pdf.ln(5)
    
    # Historia Analizada
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="2. Historia Analizada", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    objetivos = central_init.get("objetivos_identificados", [])
    if objetivos:
        for obj in objetivos:
            pdf.multi_cell(0, line_h, txt=f"- {limpiar_texto_para_pdf(obj)}", **mc_kwargs)
    pdf.ln(5)
    
    # Resultados Calidad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="3. Resultados Calidad", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    ind_cal = quality_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"Índice Global: {extraer_porcentaje(ind_cal)}", **mc_kwargs)
    just_cal = quality_json.get("justificaciones", {})
    for k, v in just_cal.items():
        if isinstance(v, dict):
            pdf.multi_cell(0, line_h, txt=f"- {k}: {v.get('resultado', 'N/A')} | {limpiar_texto_para_pdf(v.get('justificacion', ''))}", **mc_kwargs)
            if 'razon_valor' in v:
                pdf.multi_cell(0, line_h, txt=f"  Razón: {limpiar_texto_para_pdf(v['razon_valor'])}", **mc_kwargs)
    pdf.ln(5)
    
    # Resultados Seguridad
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="4. Resultados Seguridad", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    ind_seg = security_json.get("indice", 0.0)
    pdf.multi_cell(0, line_h, txt=f"Índice Global: {extraer_porcentaje(ind_seg)}", **mc_kwargs)
    just_seg = security_json.get("justificaciones", {})
    for k, v in just_seg.items():
        if isinstance(v, dict):
            pdf.multi_cell(0, line_h, txt=f"- {k}: {v.get('resultado', 'N/A')} | {limpiar_texto_para_pdf(v.get('justificacion', ''))}", **mc_kwargs)
            if 'razon_valor' in v:
                pdf.multi_cell(0, line_h, txt=f"  Razón: {limpiar_texto_para_pdf(v['razon_valor'])}", **mc_kwargs)
    pdf.ln(5)
    
    # Riesgos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="5. Riesgos Identificados", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    riesgos = eval_json.get("riesgos_criticos", [])
    if riesgos:
        for r in riesgos:
            pdf.multi_cell(0, line_h, txt=f"- {limpiar_texto_para_pdf(r)}", **mc_kwargs)
    else:
        pdf.multi_cell(0, line_h, txt="Ninguno crítico.", **mc_kwargs)
    pdf.ln(5)
    
    # Requerimientos Sugeridos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="6. Requerimientos Sugeridos", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    for req in central_init.get("requerimientos_funcionales", []) + central_init.get("requerimientos_no_funcionales", []):
        pdf.multi_cell(0, line_h, txt=f"- {req.get('id', 'N/A')} : {limpiar_texto_para_pdf(req.get('nombre', ''))}", **mc_kwargs)
    pdf.ln(5)
    
    # Conclusión
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="7. Conclusión", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, line_h, txt=limpiar_texto_para_pdf(parsed_cf.get("conclusiones_finales", eval_json.get('conclusion', ''))), **mc_kwargs)
    pdf.ln(5)
    
    # Próximos pasos
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.multi_cell(0, line_h, txt="8. Próximos Pasos", **mc_kwargs)
    pdf.set_font("Helvetica", size=11)
    correcciones = eval_json.get("correcciones_obligatorias", [])
    if correcciones:
        for c in correcciones:
            pdf.multi_cell(0, line_h, txt=f"- {limpiar_texto_para_pdf(c)}", **mc_kwargs)
    else:
        pdf.multi_cell(0, line_h, txt="- Avanzar a fase de diseño.", **mc_kwargs)
            
    pdf_bytes = pdf.output(dest='S')
    return io.BytesIO(pdf_bytes)

def generar_matriz_trazabilidad_md(central_init_json: dict) -> str:
    """Genera la Matriz de Trazabilidad en Markdown simplificada."""
    md = "### Matriz de Trazabilidad Automática\n\n"
    md += "| ID | Historia de Usuario | Requerimiento Formal | Tipo | Justificación | Prioridad | Seguimiento |\n"
    md += "|----|---------------------|----------------------|------|---------------|-----------|-------------|\n"
    
    reqs_func = central_init_json.get("requerimientos_funcionales", [])
    reqs_no_func = central_init_json.get("requerimientos_no_funcionales", [])
    requerimientos = reqs_func + reqs_no_func
    
    if not requerimientos:
        md += "| N/A | N/A | No se encontraron requerimientos | N/A | N/A | N/A | N/A |\n"
        return md
        
    for req in requerimientos:
        while isinstance(req, list) and len(req) > 0:
            req = req[0]
        if not isinstance(req, dict):
            continue
            
        req_id = req.get("id", "N/A")
        # El origen de la HU ya no viene del LLM para cada req en el nuevo prompt (ya que todo el issue es la fuente)
        # Pondremos el título del proyecto o simplemente referiremos a la HU actual.
        hu = central_init_json.get("proyecto", "HU")
        nombre = req.get("nombre", "N/A").replace("|", "-").replace("\n", " ")
        tipo = "RF" if "RF-" in str(req_id) else "RNF"
        justif = req.get("justificacion", "Derivado de la HU.").replace("|", "-").replace("\n", " ")
        prioridad = req.get("prioridad", "Media")
        
        md += f"| {req_id} | {hu} | {nombre} | {tipo} | {justif} | {prioridad} | Pendiente |\n"
        
    return md

def calcular_metricas_calidad(q_json: dict) -> dict:
    """Calcula las métricas de calidad FCp-1-G y FAp-1-G en base a los datos extraídos por el agente."""
    funciones_esperadas = q_json.get("funciones_esperadas", 1)
    if funciones_esperadas <= 0:
        funciones_esperadas = 1
    funciones_ausentes = q_json.get("funciones_ausentes_ambiguas", 0)
    
    fcp_1_g = 1.0 - (funciones_ausentes / funciones_esperadas)
    fcp_1_g = max(0.0, min(1.0, fcp_1_g))
    
    funciones = q_json.get("funciones", [])
    total_funciones = len(funciones)
    contribuyen = 0
    if total_funciones == 0:
        fap_1_g = 1.0
    else:
        contribuyen = sum(1 for f in funciones if f.get("contribuye_objetivo", False))
        fap_1_g = contribuyen / total_funciones
        
    indice = (fcp_1_g + fap_1_g) / 2.0
    
    q_json["indice"] = indice
    q_json["meta_cumplida"] = indice >= 0.95
    q_json["justificaciones"] = {
        "FCp-1-G": {
            "resultado": f"{int(fcp_1_g * 100)} %",
            "justificacion": f"{funciones_ausentes} funciones ausentes/ambiguas de {funciones_esperadas} esperadas."
        },
        "FAp-1-G": {
            "resultado": f"{int(fap_1_g * 100)} %",
            "justificacion": f"{contribuyen} de {total_funciones} funciones evaluadas contribuyen al objetivo."
        }
    }
    return q_json

def calcular_metricas_seguridad(s_json: dict) -> dict:
    """Calcula las métricas de seguridad en base a los datos extraídos por el agente."""
    requerimientos_evaluados = s_json.get("total_requerimientos_evaluados", 1)
    if requerimientos_evaluados <= 0:
        requerimientos_evaluados = 1
        
    con_control = s_json.get("requerimientos_con_control_explicito", 0)
    con_lot = s_json.get("requerimientos_con_lot_asignado", 0)
    
    cobertura_controles = con_control / requerimientos_evaluados
    cobertura_controles = max(0.0, min(1.0, cobertura_controles))
    
    cobertura_lot = con_lot / requerimientos_evaluados
    cobertura_lot = max(0.0, min(1.0, cobertura_lot))
    
    indice = (cobertura_controles + cobertura_lot) / 2.0
    
    s_json["indice"] = indice
    s_json["meta_cumplida"] = indice >= 0.85
    s_json["justificaciones"] = {
        "controles_seguridad": {
            "resultado": f"{int(cobertura_controles * 100)} %",
            "justificacion": f"{con_control} de {requerimientos_evaluados} con controles explícitos."
        },
        "lot_asignado": {
            "resultado": f"{int(cobertura_lot * 100)} %",
            "justificacion": f"{con_lot} de {requerimientos_evaluados} con LoT asignado."
        }
    }
    return s_json
