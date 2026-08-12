from core.testing_presentation import construir_presentacion_resultado_pruebas
from core.testing_traceability import construir_filas_matriz_pruebas, resumir_trazabilidad_pruebas
from core.utils import generar_documento_formal_pruebas_docx, generar_reporte_pruebas_pdf

issue_pruebas = {
    "prueba_id": "PRU-001",
    "issue_iid": 40,
    "titulo": "Pruebas del módulo de reservas",
    "codificaciones_relacionadas": ["COD-001"],
    "descripcion": "Se probó el registro de reservas y la prevención de duplicados.",
    "pruebas_funcionales": [
        {"id": "CP-01", "funcionalidad": "Registrar reserva", "prueba_realizada": "Datos válidos",
         "resultado_esperado": "Se registra", "resultado_obtenido": "Se registró", "estado": "APROBADA"},
        {"id": "CP-02", "funcionalidad": "Evitar duplicados", "prueba_realizada": "Reserva repetida",
         "resultado_esperado": "Se rechaza la 2da", "resultado_obtenido": "Permitió ambas", "estado": "FALLIDA"},
    ],
    "fallos": [
        {"id": "FAL-01", "fallo": "Permitía reservas duplicadas", "detectado_en": "CP-02",
         "corregido": True, "verificado": True, "resultado_verificacion": "Verificado en una nueva corrida"},
    ],
    "controles_seguridad": [
        {"id": "CS-01", "control": "Restringir a usuarios autorizados", "aplica": True, "verificado": True,
         "forma_verificacion": "Prueba de acceso", "resultado": "Rechazado correctamente"},
        {"id": "CS-02", "control": "Registrar operaciones importantes", "aplica": True, "verificado": False,
         "forma_verificacion": "No se verificó", "resultado": "Pendiente"},
    ],
    "pruebas_seguridad": [
        {"id": "PS-01", "prueba_realizada": "Acceso sin autorización", "resultado_esperado": "Rechazo",
         "resultado_obtenido": "Rechazado", "estado": "APROBADA"},
    ],
    "evidencias": [
        {"id": "EV-01", "prueba_o_fallo_relacionado": "CP-02", "tipo_evidencia": "Captura de pantalla",
         "descripcion": "evidencias/cp-02.png"},
    ],
    "pendientes": ["Verificar el registro de auditoría (CS-02)."],
    "observaciones": [],
}

contexto = {
    "prueba_id": "PRU-001",
    "issue_iid": 40,
    "titulo": issue_pruebas["titulo"],
    "codificaciones_relacionadas": ["COD-001"],
    "trazabilidad": {
        "COD-001": {"elementos_diseno": ["ED-01", "ED-02"], "requisitos": ["RF-001", "RF-002"], "historias": ["HU-020"]},
    },
    "metricas": {
        "MC-07": {"codigo": "MC-07", "valor": 0.5, "numerador": 1, "denominador": 2, "umbral": 0.95, "cumple": False, "porcentaje": 50.0, "estado": "EVALUADO"},
        "MC-08": {"codigo": "MC-08", "valor": 1.0, "numerador": 1, "denominador": 1, "fallos_detectados": 1, "fallos_corregidos": 1, "fallos_corregidos_verificados": 1, "umbral": 0.95, "cumple": True, "porcentaje": 100.0, "estado": "EVALUADO"},
        "MS-08": {"codigo": "MS-08", "valor": 0.5, "numerador": 1, "denominador": 2, "umbral": 0.92, "cumple": False, "porcentaje": 50.0, "estado": "EVALUADO"},
        "MS-09": {"codigo": "MS-09", "valor": 1.0, "numerador": 1, "denominador": 1, "umbral": 0.92, "cumple": True, "porcentaje": 100.0, "estado": "EVALUADO"},
    },
}

central_result = {
    "coherencia_declarado_vs_evidencia": {"estado": "coherente", "justificacion": "La evidencia registrada sustenta lo declarado."},
    "inconsistencias_detectadas": [],
    "trazabilidad_confirmada": contexto["trazabilidad"],
}

quality_result = {
    "raw": {
        "interpretacion_mc07": {
            "funcionalidades_con_brecha": [
                {"funcionalidad": "Evitar duplicados", "explicacion": "CP-02 falló: se permitieron reservas duplicadas."},
            ],
            "conclusion": "1 de 2 funcionalidades evaluadas está completamente correcta.",
        },
        "interpretacion_mc08": {
            "fallos_pendientes": [],
            "conclusion": "El único fallo detectado fue corregido y verificado.",
        },
        "precisiones_necesarias": [],
        "oportunidades_adicionales": [],
    },
    "mc07": contexto["metricas"]["MC-07"],
    "mc08": contexto["metricas"]["MC-08"],
}

security_result = {
    "raw": {
        "interpretacion_ms08": {
            "controles_no_verificados": [
                {"control": "Registrar operaciones importantes", "explicacion": "No se verificó el registro de auditoría."},
            ],
            "conclusion_ms08": "1 de 2 controles aplicables fue verificado.",
        },
        "interpretacion_ms09": {
            "pruebas_fallidas": [],
            "conclusion_ms09": "La única prueba de seguridad ejecutada fue satisfactoria.",
        },
        "precisiones_necesarias": [],
        "oportunidades_adicionales": [],
    },
    "ms08": contexto["metricas"]["MS-08"],
    "ms09": contexto["metricas"]["MS-09"],
}

evaluator_result = {
    "conclusion_calidad": "La funcionalidad Evitar duplicados presenta una brecha objetiva (CP-02).",
    "conclusion_seguridad": "El control CS-02 aplicable no fue verificado todavía.",
    "correcciones_necesarias": ["Evitar duplicados tiene una prueba fallida (CP-02)."],
    "precisiones_necesarias": [],
    "oportunidades_mejora": ["Verificar el registro de auditoría (CS-02) antes de aprobar."],
    "hallazgos_prioritarios": ["Evitar duplicados tiene una prueba fallida (CP-02)."],
    "recomendacion_revision": "Corregir y volver a probar el caso CP-02 antes de aprobar COD-001.",
}

testing_summary = {
    "prueba_id": "PRU-001",
    "issue_iid": 40,
    "codificaciones_relacionadas": ["COD-001"],
    "estado_orientativo": "CORREGIR",
    "metricas": contexto["metricas"],
    "calidad": {**contexto["metricas"], "interpretacion": quality_result["raw"], "conclusion": evaluator_result["conclusion_calidad"]},
    "seguridad": {**contexto["metricas"], "interpretacion": security_result["raw"], "conclusion": evaluator_result["conclusion_seguridad"]},
    "correcciones_necesarias": evaluator_result["correcciones_necesarias"],
    "precisiones": evaluator_result["precisiones_necesarias"],
    "oportunidades_mejora": evaluator_result["oportunidades_mejora"],
    "trazabilidad": contexto["trazabilidad"],
    "conclusion": evaluator_result["recomendacion_revision"],
}

presentacion = construir_presentacion_resultado_pruebas(
    issue_pruebas, contexto, central_result, quality_result, security_result, evaluator_result, testing_summary,
)

print("\n" + "=" * 70)
print("construir_presentacion_resultado_pruebas")
print("=" * 70)
print(presentacion)

assert presentacion["prueba_id"] == "PRU-001"
assert presentacion["metricas"]["MC-07"]["funcionalidades_con_brecha"][0]["funcionalidad"] == "Evitar duplicados"
assert presentacion["metricas"]["MS-08"]["controles_no_verificados"][0]["control"] == "Registrar operaciones importantes"
assert presentacion["contexto_original"]["pruebas_funcionales"] == issue_pruebas["pruebas_funcionales"]
assert presentacion["contexto_original"]["pendientes"] == issue_pruebas["pendientes"]

matriz_codificacion = [
    {
        "HU origen": "HU-020", "Código requisito": "RF-001", "Tipo": "RF",
        "Nombre del requisito": "Registrar reserva", "Elementos de Diseño": "ED-01",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
    },
    {
        "HU origen": "HU-020", "Código requisito": "RF-002", "Tipo": "RF",
        "Nombre del requisito": "Evitar duplicados", "Elementos de Diseño": "ED-02",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
    },
]
filas_trazabilidad = construir_filas_matriz_pruebas(matriz_codificacion, [testing_summary])
resumen_trazabilidad = resumir_trazabilidad_pruebas(filas_trazabilidad)

matriz_metadata = {"fuente": "GitLab"}

pdf_buffer = generar_reporte_pruebas_pdf("Proyecto Demo", "Pruebas", [presentacion], resumen_trazabilidad, matriz_metadata)
pdf_bytes = pdf_buffer.getvalue()
print("\nPDF generado:", len(pdf_bytes), "bytes")
assert len(pdf_bytes) > 1000
assert pdf_bytes[:4] == b"%PDF"

docx_buffer = generar_documento_formal_pruebas_docx("Proyecto Demo", "Pruebas", [presentacion], matriz_metadata, filas_trazabilidad)
docx_bytes = docx_buffer.getvalue()
print("DOCX generado:", len(docx_bytes), "bytes")
assert len(docx_bytes) > 1000
assert docx_bytes[:2] == b"PK"  # DOCX es un ZIP (python-docx)

print("\nTodas las verificaciones de testing_documents pasaron.")
