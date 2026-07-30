import io
from datetime import datetime
import json
import logging
import unicodedata
import re
from difflib import SequenceMatcher
from core.batch_contract import (
    normalizar_tipo_requerimiento, recopilar_recomendaciones,
    renumerar_requerimientos,
)

logger = logging.getLogger(__name__)

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
    return "N/D" if val is None else str(val)


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
    valid = [x for x in batch_results if isinstance(x, dict) and x.get("status") == "ok"]
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
    return {
        "total": len(batch_results),
        "procesadas": len(valid),
        "errores": len(batch_results) - len(valid),
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
    recommendations = _eliminar_recomendaciones_duplicadas([
        recommendation for item in valid for recommendation in recopilar_recomendaciones(item)
    ])
    for item in valid:
        item["recommendations"] = recopilar_recomendaciones(item)
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
        "recommendations": recommendations,
        "traceability_rows": traceability_rows,
        "generated_at": generated_at,
        "descripcion_resultado": DECISION_SUPPORT_NOTICE,
        "revision_humana_requerida": True,
    }


def generar_reporte_lote_pdf(batch_result: dict) -> io.BytesIO:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
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
    linea(f"Índice parcial de calidad promedio: {extraer_porcentaje(summary['calidad_promedio'])}")
    linea(f"Cobertura documental de seguridad promedio: {extraer_porcentaje(summary['seguridad_promedio'])}")
    linea(f"Requerimientos sugeridos: {summary['requerimientos']}")
    for result in valid:
        c = result.get("central") if isinstance(result.get("central"), dict) else {}
        q = result.get("quality") if isinstance(result.get("quality"), dict) else {}
        s = result.get("security") if isinstance(result.get("security"), dict) else {}
        e = result.get("evaluation") if isinstance(result.get("evaluation"), dict) else {}
        pdf.add_page()
        encabezado(f"{c['historia_id']} — {c['titulo']}", 13)
        linea(f"Estado de evaluación: {e.get('veredicto', 'No evaluado')} | Índice parcial de calidad: {extraer_porcentaje(q.get('indice'))} | Cobertura documental de seguridad: {extraer_porcentaje(s.get('indice'))} | Nivel de aseguramiento recomendado - LoT: {s.get('lot_recomendado', 'No informado')}")
        linea(f"Actor: {c.get('actor', '')}")
        linea(f"Objetivo: {c.get('objetivo', '')}")
        encabezado("Métricas de calidad", 11)
        for name, metric in _iterar_metricas(q, "calidad"):
            linea(f"{name}: {extraer_porcentaje(metric.get('valor'))}. {metric.get('justificacion', '')}")
            if metric.get("recomendacion"):
                linea(f"Recomendación: {metric['recomendacion']}")
        for label in ("observaciones", "recomendaciones"):
            for text_value in _iterar_textos(q.get(label), f"calidad.{label}"):
                linea(f"{label.capitalize()}: {text_value}")
        encabezado("Métricas de seguridad", 11)
        for name, metric in _iterar_metricas(s, "seguridad"):
            linea(f"{name}: {extraer_porcentaje(metric.get('valor'))}. {metric.get('justificacion', '')}")
            if metric.get("recomendacion"):
                linea(f"Recomendación: {metric['recomendacion']}")
        for label in ("observaciones", "recomendaciones"):
            for text_value in _iterar_textos(s.get(label), f"seguridad.{label}"):
                linea(f"{label.capitalize()}: {text_value}")
        encabezado("Riesgos y recomendaciones", 11)
        evaluator_texts = list(_iterar_textos(e.get("riesgos_criticos"), "evaluador.riesgos_criticos"))
        evaluator_texts += list(_iterar_textos(e.get("correcciones_obligatorias"), "evaluador.correcciones_obligatorias"))
        for text_value in evaluator_texts:
            linea(f"- {text_value}")
        encabezado("Requerimientos sugeridos", 11)
        for requirement in c.get("requerimientos", []):
            if not isinstance(requirement, dict):
                logger.warning("Requerimiento no válido omitido del PDF: %r.", requirement)
                continue
            linea(f"{requirement.get('id', 'Sin código')} — {requirement.get('nombre', '')}")
            linea(requirement.get("descripcion_formal", ""))
            linea(f"Procedencia: {requirement.get('procedencia', 'inferido')}")
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


def generar_documento_formal_lote_docx(batch_result: dict) -> io.BytesIO:
    from docx import Document
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
    doc.add_paragraph(f"Proyecto: {project_name}")
    doc.add_paragraph(f"Milestone: {milestone}")
    doc.add_paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}")
    doc.add_paragraph("Versión: 1.0")
    doc.add_paragraph(f"Historias analizadas: {len(valid)}")
    doc.add_page_break()
    doc.add_heading("1. Introducción", 1)
    doc.add_paragraph("Este documento consolida los requerimientos formalizados del lote de Historias de Usuario analizado mediante el sistema multiagente.")
    doc.add_heading("2. Alcance", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective: doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading("3. Actores identificados", 1)
    for actor in dict.fromkeys(x["central"].get("actor", "") for x in valid):
        if actor: doc.add_paragraph(actor, style="List Bullet")
    doc.add_heading("4. Objetivos identificados", 1)
    for objective in dict.fromkeys(x["central"].get("objetivo", "") for x in valid):
        if objective: doc.add_paragraph(objective, style="List Bullet")
    doc.add_heading("5. Requerimientos formales consolidados", 1)
    for result in valid:
        origin = f"{result['central']['historia_id']} — {result['central']['titulo']}"
        for requirement in result["central"]["requerimientos"]:
            doc.add_heading(f"{requirement['id']} — {requirement.get('nombre', '')}", 3)
            doc.add_paragraph(requirement.get("descripcion_formal", ""))
            type_names = {"RF": "Funcional", "RNF": "No funcional"}
            doc.add_paragraph(f"Tipo: {type_names.get(requirement['tipo'], 'No funcional')}")
            doc.add_paragraph(f"Prioridad: {requirement.get('prioridad', '')}")
            doc.add_paragraph(f"Origen: {origin}")
            doc.add_paragraph(f"Justificación: {requirement.get('justificacion', '')}")
            doc.add_paragraph(f"Procedencia: {requirement.get('procedencia', 'inferido')}")
            doc.add_paragraph("Revisión humana: Pendiente")
    doc.add_heading("6. Restricciones consolidadas", 1)
    restrictions = dict.fromkeys(r for x in valid for r in x["central"].get("restricciones", []))
    for restriction in restrictions: doc.add_paragraph(restriction, style="List Bullet")
    doc.add_heading("7. Recomendaciones generales", 1)
    if batch_result["recommendations"]:
        for recommendation in batch_result["recommendations"]:
            doc.add_paragraph(recommendation, style="List Bullet")
    else:
        doc.add_paragraph("No se identificaron correcciones adicionales para el lote analizado.")
    doc.add_heading("8. Matriz de trazabilidad", 1)
    matrix_keys = list(TRACEABILITY_COLUMNS)
    table = doc.add_table(rows=1, cols=len(matrix_keys))
    table.style = "Table Grid"
    headers = matrix_keys
    for cell, value in zip(table.rows[0].cells, headers): cell.text = value
    for row in rows:
        for cell, key in zip(table.add_row().cells, matrix_keys):
            cell.text = str(row.get(key, ""))
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output

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
