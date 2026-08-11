from core.coding_presentation import construir_presentacion_resultado_codificacion
from core.coding_traceability import (
    construir_filas_matriz_codificacion,
    resumir_trazabilidad_codificacion,
)
from core.utils import (
    generar_documento_formal_codificacion_docx,
    generar_reporte_codificacion_pdf,
)

contexto = {
    "codificacion_id": "COD-001",
    "issue_iid": 25,
    "titulo": "Servicio de autenticación",
    "descripcion": "Servicio de autenticación de usuarios mediante tokens JWT.",
    "elementos_diseno_declarados": ["ED-01", "ED-02"],
    "archivos_declarados": [
        {"ruta": "core/auth_service.py", "descripcion": "Lógica principal."},
        {"ruta": "core/token_repository.py", "descripcion": "Persistencia de tokens."},
    ],
    "decisiones": ["Se usó bcrypt para el hash de contraseñas."],
    "observaciones": [],
    "lenguaje_detectado": "python",
    "elementos_diseno_contextualizados": [
        {"elemento_id": "ED-01", "relaciones_diseno": [{"diseno": "DIS-001", "codigo_requisito": "RF-001"}]},
        {"elemento_id": "ED-02", "relaciones_diseno": [{"diseno": "DIS-001", "codigo_requisito": "RF-001"}]},
    ],
}

central_result = {
    "elementos_implementados": ["ED-01"],
    "elementos_no_confirmados": ["ED-02"],
    "archivos_consolidados": [
        {"ruta": "core/auth_service.py", "elementos_diseno_implementados": ["ED-01"], "evidencia": "Función autenticar() presente."},
    ],
    "coherencia_declarado_vs_evidencia": {"estado": "parcialmente_coherente", "justificacion": "ED-02 se declara pero no hay evidencia en el código."},
    "inconsistencias_detectadas": [
        {"tipo": "elemento_no_confirmado", "descripcion": "ED-02 no tiene evidencia en los archivos localizados.", "evidencia": "token_repository.py no persiste tokens."},
    ],
}

quality_result = {
    "raw": {
        "interpretacion_mc05": {
            "funciones_criticas": [
                {"archivo": "core/auth_service.py", "nombre": "autenticar", "complejidad": 12, "problema": "Demasiadas ramas anidadas.", "recomendacion": "Extraer validaciones a funciones auxiliares."},
            ],
            "conclusion": "La función autenticar supera el umbral de complejidad aceptable.",
        },
        "precisiones_necesarias": [],
        "oportunidades_adicionales": [],
    },
    "mc05": {"codigo": "MC-05", "valor": 0.5, "numerador": 1, "denominador": 2, "estado_calculo": "calculada"},
}

security_result = {
    "raw": {
        "interpretacion_ms05": {"vulnerabilidades_criticas": [], "conclusion_ms05": "No se detectaron vulnerabilidades críticas."},
        "interpretacion_ms06": {
            "dependencias_inseguras": [{"nombre": "requests", "version": "2.25.0", "vulnerabilidades": [], "explicacion": "Versión con CVEs conocidos."}],
            "conclusion_ms06": "Una dependencia presenta vulnerabilidades conocidas.",
        },
        "interpretacion_ms07": {"archivos_con_secretos": [], "conclusion_ms07": "No se detectaron secretos expuestos."},
        "precisiones_necesarias": [],
        "oportunidades_adicionales": [],
    },
    "ms05": {"codigo": "MS-05", "valor": 1.0, "numero_criticas": 0, "estado_calculo": "calculada"},
    "ms06": {"codigo": "MS-06", "valor": 0.5, "numerador": 1, "denominador": 2, "estado_calculo": "calculada"},
    "ms07": {"codigo": "MS-07", "valor": None, "numerador": None, "denominador": None, "estado_calculo": "no_evaluable", "motivo": "gitleaks no encontrado"},
}

evaluator_result = {
    "conclusion_calidad": "La complejidad ciclomática de autenticar() debe reducirse.",
    "conclusion_seguridad": "Existe una dependencia insegura pendiente de actualización; MS-07 no es evaluable por ausencia de Gitleaks.",
    "correcciones_necesarias": ["La función autenticar tiene complejidad 12, por encima del umbral aceptable."],
    "precisiones_necesarias": ["MS-07 no es evaluable: Gitleaks no está disponible en el entorno de análisis."],
    "oportunidades_mejora": ["Actualizar requests a una versión sin vulnerabilidades conocidas."],
}

coding_summary = {
    "issue_iid": 25,
    "codificacion_id": "COD-001",
    "metricas": {
        "MC-05": quality_result["mc05"],
        "MS-05": security_result["ms05"],
        "MS-06": security_result["ms06"],
        "MS-07": security_result["ms07"],
    },
    "indice_calidad_codigo": 0.5,
    "indice_seguridad_codigo": 0.75,
    "estado_orientativo": "CORREGIR",
    "correcciones_necesarias": evaluator_result["correcciones_necesarias"],
    "precisiones_necesarias": evaluator_result["precisiones_necesarias"],
    "oportunidades_mejora": evaluator_result["oportunidades_mejora"],
}

matriz_diseno = [
    {
        "HU origen": "HU-006 — Consultar horarios disponibles",
        "Código requisito": "RF-001",
        "Tipo": "Funcional",
        "Nombre del requisito": "Mostrar únicamente horarios disponibles",
        "Descripción": "El sistema deberá mostrar solo los horarios libres.",
        "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-01, ED-02",
        "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME",
        "Observación": "Relación identificada con evidencia suficiente.",
    },
]
resultados_central_codificacion = [{"issue_iid": 25, "codificacion_id": "COD-001", **central_result}]
filas_trazabilidad = construir_filas_matriz_codificacion(matriz_diseno, resultados_central_codificacion, {"COD-001": "CORREGIR"})
resumen_trazabilidad = resumir_trazabilidad_codificacion(filas_trazabilidad)

presentacion = construir_presentacion_resultado_codificacion(
    contexto, central_result, quality_result, security_result, evaluator_result,
    coding_summary, filas_trazabilidad,
)

print("\n" + "=" * 70)
print("construir_presentacion_resultado_codificacion")
print("=" * 70)
print(presentacion)

assert presentacion["codificacion_id"] == "COD-001"
assert presentacion["metricas"]["MC-05"]["funciones_criticas"][0]["nombre"] == "autenticar"
assert presentacion["metricas"]["MS-06"]["dependencias_inseguras"][0]["nombre"] == "requests"
assert presentacion["metricas"]["MS-07"]["estado_calculo"] == "no_evaluable"
assert "Refactorizar la función autenticar" in presentacion["propuesta_para_maximo"][0]
assert any("requests" in item for item in presentacion["propuesta_para_maximo"])
assert presentacion["trazabilidad"]["implementados"] == ["RF-001"]
assert presentacion["trazabilidad"]["no_confirmados"] == ["RF-001"]

matriz_metadata = {"coding_matrix_version": "3.0", "coding_matrix_source": "GitLab", "coding_matrix_status": "ORIGINAL"}

pdf_buffer = generar_reporte_codificacion_pdf("Proyecto Demo", "Codificación", [presentacion], resumen_trazabilidad, matriz_metadata)
pdf_bytes = pdf_buffer.getvalue()
print("\nPDF generado:", len(pdf_bytes), "bytes")
assert len(pdf_bytes) > 1000
assert pdf_bytes[:4] == b"%PDF"

docx_buffer = generar_documento_formal_codificacion_docx("Proyecto Demo", "Codificación", [presentacion], matriz_metadata, filas_trazabilidad)
docx_bytes = docx_buffer.getvalue()
print("DOCX generado:", len(docx_bytes), "bytes")
assert len(docx_bytes) > 1000
assert docx_bytes[:2] == b"PK"  # DOCX es un ZIP (python-docx)

print("\nTodas las verificaciones de coding_documents pasaron.")
