import csv
import os
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from core.design_context import construir_contexto_diseno
from core.design_traceability import (
    construir_filas_matriz_diseno,
    evolucionar_matriz_a_diseno,
    normalizar_matriz_requerimientos,
    resumir_trazabilidad_diseno,
)
from core.utils import generar_documento_formal_diseno_docx, generar_reporte_diseno_pdf
from integrations.issue_service import obtener_issues_diseno
from tests.fixtures_diseno import (
    CONCLUSIONES_EVALUADOR_DISENO,
    DESIGN_SUMMARY_POR_DISENO,
    EVALUACION_POR_DISENO,
    RESULTADOS_CENTRAL_DISENO,
    RESULTADOS_SECURITY_DISENO,
)

PROJECT_NAME = "modelo-multiagente-dev"
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")
MILESTONE = "Diseño"

MATRIZ_PATH = Path(__file__).parent.parent / "output" / "csv" / "matriz_trazabilidad_5_HU.csv"
OUTPUT_PDF_DIR = Path(__file__).parent.parent / "output" / "pdf"
OUTPUT_DOCX_DIR = Path(__file__).parent.parent / "output" / "docx"

DIS_A_DOCUMENTAR = ["DIS-001", "DIS-002"]


# ---------------------------------------------------------
# GitLab → DesignMapper → DesignContext (real, sin LLM)
# ---------------------------------------------------------

with MATRIZ_PATH.open(encoding="utf-8-sig", newline="") as handle:
    matriz_original = list(csv.DictReader(handle))

issues_diseno = obtener_issues_diseno(PROJECT_ID, milestone_title="Diseño")
contextos_por_diseno_id = {
    issue.get("diseno_id"): construir_contexto_diseno(issue, matriz_original)
    for issue in issues_diseno
}

# DIS-003 sigue bloqueado: nunca se documenta
contexto_dis003 = contextos_por_diseno_id["DIS-003"]
assert contexto_dis003["validacion_trazabilidad"]["referencias_invalidas"]


# ---------------------------------------------------------
# Modelo documental por DIS (contexto real + fixtures con datos reales
# ya validados, ver tests/fixtures_diseno.py — sin invocar LLM)
# ---------------------------------------------------------

CENTRAL_POR_DISENO = {resultado["diseno_id"]: resultado for resultado in RESULTADOS_CENTRAL_DISENO}


def construir_modelo_dis(diseno_id: str) -> dict:
    contexto = contextos_por_diseno_id[diseno_id]
    central = CENTRAL_POR_DISENO[diseno_id]
    conclusiones = CONCLUSIONES_EVALUADOR_DISENO[diseno_id]
    controles_faltantes = RESULTADOS_SECURITY_DISENO[diseno_id]["cobertura_controles"]["controles_faltantes"]

    return {
        "diseno_id": diseno_id,
        "titulo": contexto.get("titulo", ""),
        "requerimientos_contextualizados": contexto.get("requerimientos_contextualizados", []),
        "elementos_diseno": contexto.get("elementos_diseno", []),
        "trazabilidad_diseno": central.get("trazabilidad_diseno", []),
        "requisitos_sin_relacion_evidente": central.get("requisitos_sin_relacion_evidente", []),
        "restricciones": contexto.get("restricciones", []),
        "decisiones_diseno": contexto.get("decisiones_diseno", []),
        "seguridad_documentada": contexto.get("seguridad", {}),
        "resumen": DESIGN_SUMMARY_POR_DISENO[diseno_id],
        "conclusion_calidad": conclusiones["conclusion_calidad"],
        "conclusion_seguridad": conclusiones["conclusion_seguridad"],
        "controles_faltantes": controles_faltantes,
    }


disenos = [construir_modelo_dis(diseno_id) for diseno_id in DIS_A_DOCUMENTAR]


# ---------------------------------------------------------
# Resumen global de trazabilidad (core/design_traceability.py, real)
# ---------------------------------------------------------

matriz_normalizada = normalizar_matriz_requerimientos(matriz_original)
estructura_interna = evolucionar_matriz_a_diseno(matriz_normalizada, RESULTADOS_CENTRAL_DISENO)
filas_trazabilidad = construir_filas_matriz_diseno(estructura_interna, EVALUACION_POR_DISENO)
resumen_trazabilidad = resumir_trazabilidad_diseno(filas_trazabilidad)


# ---------------------------------------------------------
# Generación de documentos
# ---------------------------------------------------------

OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DOCX_DIR.mkdir(parents=True, exist_ok=True)

pdf_path = OUTPUT_PDF_DIR / "reporte_diseno_prueba.pdf"
docx_path = OUTPUT_DOCX_DIR / "documento_formal_diseno_prueba.docx"

pdf_bytes = generar_reporte_diseno_pdf(PROJECT_NAME, MILESTONE, disenos, resumen_trazabilidad)
pdf_path.write_bytes(pdf_bytes.getvalue())

docx_bytes = generar_documento_formal_diseno_docx(PROJECT_NAME, MILESTONE, disenos)
docx_path.write_bytes(docx_bytes.getvalue())

print("\n" + "=" * 70)
print("DOCUMENTOS DE DISEÑO GENERADOS")
print("=" * 70)
print("PDF:", pdf_path)
print("DOCX:", docx_path)


# ==========================================================
# Validaciones
# ==========================================================

# ✓ PDF existe
assert pdf_path.is_file() and pdf_path.stat().st_size > 0

# ✓ DOCX existe
assert docx_path.is_file() and docx_path.stat().st_size > 0

reader = PdfReader(str(pdf_path))
pdf_texto = "\n".join(page.extract_text() or "" for page in reader.pages)

documento = Document(str(docx_path))
docx_texto = "\n".join(parrafo.text for parrafo in documento.paragraphs)

# ✓ DIS-001 y DIS-002 aparecen (en ambos documentos)
for diseno_id in DIS_A_DOCUMENTAR:
    assert diseno_id in pdf_texto
    assert diseno_id in docx_texto

# ✓ MC-03 / MS-03 aparecen solo en PDF
assert "MC-03" in pdf_texto
assert "MS-03" in pdf_texto
assert "MC-03" not in docx_texto
assert "MS-03" not in docx_texto
assert "MC-04" not in docx_texto
assert "MS-04" not in docx_texto

# ✓ DOCX no parece reporte de métricas (sin porcentajes ni códigos de métrica)
assert "%" not in docx_texto

# ✓ trazabilidad aparece en ambos de forma apropiada
assert "RF-001" in pdf_texto and "RF-001" in docx_texto
assert "ED-01" in pdf_texto and "ED-01" in docx_texto

# ✓ aspectos pendientes están marcados como pendientes
assert "Aspecto pendiente" in docx_texto
assert "Pendiente de revisión" in docx_texto

# ✓ DIS-003 no aparece como evaluado
assert "DIS-003" not in pdf_texto
assert "DIS-003" not in docx_texto

print("\nTodas las verificaciones de los documentos de Diseño pasaron.")
