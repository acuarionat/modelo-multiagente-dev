import unittest

from core.batch_contract import (
    ajustar_veredicto_determinista, calcular_metricas_agente, consolidar_lote,
    construir_etiquetas_resultado, validar_contenido_agente,
)
from core.utils import (
    calcular_resumen_lote, construir_filas_trazabilidad, construir_resultado_lote,
    generar_documento_formal_lote_docx,
)
from integrations.issue_mapper import mapear_issue_a_json, separar_entradas_para_analisis, validar_entrada_issue


class FakeIssue:
    def __init__(self, description, title="Registrar usuario", iid=17, labels=None):
        self.description = description
        self.title = title
        self.iid = iid
        self.labels = labels or ["Historia de Usuario", "Pendiente"]


COMPLETE_DESCRIPTION = """## Nombre
Registrar usuario
## Descripción
**Como** administrador
**Quiero** registrar un usuario
**Para** permitir su acceso
## Criterios de aceptación
- Se rechaza un correo duplicado
## Prioridad
Alta
## Restricciones
- El correo debe ser único
## Observaciones
Validar con el responsable
"""

OFFICIAL_GITLAB_DESCRIPTION = """# Historia de Usuario
## Descripción
La recepcionista necesita reprogramar citas médicas.
## Como
Recepcionista
## Quiero
Modificar la fecha y hora de una cita.
## Para
Adaptar la agenda médica según disponibilidad.
## Criterios de aceptación
* Verificar disponibilidad.
* Notificar al paciente.
* Registrar el cambio.
## Restricciones
Solo horarios disponibles.
## Seguridad
## ¿La historia maneja datos sensibles?
Sí
Datos personales y datos médicos.
## Autenticación
Usuario y contraseña.
## Autorización / Roles
Recepcionista.
## Auditoría
Sí.
Registrar usuario, fecha, hora y cambios realizados.
## Observaciones
Enviar notificación automática al paciente.
"""


def quality(index=1.0):
    return {
        "issue_iid": 17, "indice": index, "meta_cumplida": index is not None and index >= .95,
        "estado_medicion": "evaluable" if index is not None else "evidencia_insuficiente", "metricas": {},
    }


def security(index=1.0):
    return {
        "issue_iid": 17, "indice": index, "meta_cumplida": index is not None and index >= .85,
        "estado_medicion": "evaluable" if index is not None else "evidencia_insuficiente", "metricas": {},
    }


class InputValidationTests(unittest.TestCase):
    def test_complete_story(self):
        data = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION))
        self.assertEqual(data["validacion_entrada"]["estado"], "entrada_valida")

    def test_official_gitlab_template_is_mapped(self):
        data = mapear_issue_a_json(FakeIssue(OFFICIAL_GITLAB_DESCRIPTION))
        self.assertEqual(data["actor"], "Recepcionista")
        self.assertEqual(data["funcionalidad"], "Modificar la fecha y hora de una cita.")
        self.assertEqual(data["objetivo"], "Adaptar la agenda médica según disponibilidad.")
        self.assertEqual(len(data["criterios_aceptacion"]), 3)
        self.assertEqual(data["restricciones"], ["Solo horarios disponibles."])
        self.assertIn("Datos personales", data["seguridad"]["maneja_datos_sensibles"])
        self.assertEqual(data["seguridad"]["autenticacion"], "Usuario y contraseña.")
        self.assertEqual(data["seguridad"]["autorizacion_roles"], "Recepcionista.")
        self.assertIn("Registrar usuario", data["seguridad"]["auditoria"])
        self.assertNotEqual(data["validacion_entrada"]["estado"], "informacion_insuficiente")

    def test_missing_actor(self):
        data = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION.replace("**Como** administrador\n", "")))
        self.assertNotEqual(data["validacion_entrada"]["estado"], "informacion_insuficiente")
        self.assertIn("actor no identificado", data["validacion_entrada"]["advertencias"])

    def test_missing_objective(self):
        data = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION.replace("**Para** permitir su acceso", "")))
        self.assertNotEqual(data["validacion_entrada"]["estado"], "informacion_insuficiente")
        self.assertIn("objetivo no identificado", data["validacion_entrada"]["advertencias"])

    def test_missing_acceptance_criteria(self):
        data = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION.replace("- Se rechaza un correo duplicado", "")))
        self.assertNotEqual(data["validacion_entrada"]["estado"], "informacion_insuficiente")
        self.assertIn("criterios de aceptación no especificados", data["validacion_entrada"]["advertencias"])

    def test_optional_priority_only_warns(self):
        data = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION.replace("Alta", "")))
        self.assertEqual(data["validacion_entrada"]["estado"], "entrada_con_advertencias")
        self.assertIn("prioridad no especificada", data["validacion_entrada"]["advertencias"])

    def test_markdown_heading_variant(self):
        variant = COMPLETE_DESCRIPTION.replace("## ", "### ").replace("## Nombre", "# Nombre:")
        data = mapear_issue_a_json(FakeIssue(variant))
        self.assertNotEqual(data["validacion_entrada"]["estado"], "informacion_insuficiente")

    def test_direct_validation_rejects_empty_description(self):
        validation = validar_entrada_issue({
            "titulo": "Historia", "descripcion_original": "", "actor": "A", "funcionalidad": "F",
            "objetivo": "O", "criterios_aceptacion": ["C"], "prioridad": "Alta",
            "restricciones": [], "observaciones": "",
        })
        self.assertIn("descripcion", validation["campos_faltantes"])

    def test_insufficient_story_is_excluded_by_default(self):
        complete = mapear_issue_a_json(FakeIssue(COMPLETE_DESCRIPTION, iid=1))
        incomplete = mapear_issue_a_json(FakeIssue("", iid=2))
        processable, excluded = separar_entradas_para_analisis([complete, incomplete])
        self.assertEqual([item["id"] for item in processable], ["1"])
        self.assertEqual([item["id"] for item in excluded], ["2"])


class MetricSafetyTests(unittest.TestCase):
    def test_missing_recommendation_is_completed_without_invalidating_story(self):
        response = {"resultados": [{"issue_iid": 8, "metricas": {
            "cobertura_funcional": {
                "elementos_evaluados": ["Registrar"], "elementos_con_problemas": [],
                "justificacion": "La función Registrar está definida.", "recomendacion": "",
            },
            "adecuacion_funcional": {
                "elementos_evaluados": ["Registrar", "Notificar"], "elementos_alineados": ["Registrar"],
                "elementos_con_problemas": ["Notificar"],
                "justificacion": "Notificar no está claramente relacionado con el objetivo.", "recomendacion": "",
            },
        }}]}
        calcular_metricas_agente(response, "Calidad")
        metric = response["resultados"][0]["metricas"]["adecuacion_funcional"]
        self.assertTrue(metric["recomendacion"])
        self.assertIn("Python agregó", metric["advertencias_tecnicas"][-1])
        self.assertEqual(validar_contenido_agente(response, "Calidad"), {})

    def test_empty_evidence_is_not_perfect(self):
        response = {"resultados": [{"metricas": {
            "cobertura_funcional": {"elementos_evaluados": [], "elementos_con_problemas": []},
            "adecuacion_funcional": {"elementos_evaluados": [], "elementos_alineados": [], "elementos_con_problemas": []},
        }}]}
        calcular_metricas_agente(response, "Calidad")
        item = response["resultados"][0]
        self.assertIsNone(item["indice"])
        self.assertEqual(item["estado_medicion"], "evidencia_insuficiente")

    def test_duplicates_and_placeholders_are_removed(self):
        response = {"resultados": [{"metricas": {
            "cobertura_funcional": {"elementos_evaluados": ["Registrar", " registrar ", "N/A"], "elementos_con_problemas": []},
            "adecuacion_funcional": {"elementos_evaluados": ["Registrar"], "elementos_alineados": ["REGISTRAR"], "elementos_con_problemas": []},
        }}]}
        calcular_metricas_agente(response, "Calidad")
        self.assertEqual(response["resultados"][0]["metricas"]["cobertura_funcional"]["elementos_evaluados"], ["Registrar"])

    def test_out_of_universe_aligned_item_is_removed(self):
        response = {"resultados": [{"metricas": {
            "cobertura_funcional": {"elementos_evaluados": ["Registrar"], "elementos_con_problemas": []},
            "adecuacion_funcional": {"elementos_evaluados": ["Registrar"], "elementos_alineados": ["Eliminar"], "elementos_con_problemas": []},
        }}]}
        calcular_metricas_agente(response, "Calidad")
        metric = response["resultados"][0]["metricas"]["adecuacion_funcional"]
        self.assertEqual(metric["elementos_alineados"], [])
        self.assertTrue(metric["advertencias_tecnicas"])

    def test_non_applicable_controls_are_excluded(self):
        response = {"resultados": [{"metricas": {
            "controles_seguridad": {"estado_medicion": "no_aplicable", "requerimientos_evaluados": [], "requerimientos_con_controles": [], "controles_identificados": [], "controles_ausentes": []},
            "lot_asignado": {"requerimientos_evaluados": ["RF-1"], "requerimientos_con_lot_justificado": ["RF-1"], "factores_considerados": ["Dato"], "lot_recomendado": "LoT-1"},
        }}]}
        calcular_metricas_agente(response, "Seguridad")
        item = response["resultados"][0]
        self.assertIsNone(item["metricas"]["controles_seguridad"]["valor"])
        self.assertEqual(item["indice"], 1.0)

    def test_explicit_non_evaluable_state_does_not_calculate_value(self):
        response = {"resultados": [{"metricas": {
            "cobertura_funcional": {"estado_medicion": "no_evaluable", "elementos_evaluados": ["Registrar"], "elementos_con_problemas": []},
            "adecuacion_funcional": {"estado_medicion": "no_evaluable", "elementos_evaluados": ["Registrar"], "elementos_alineados": ["Registrar"], "elementos_con_problemas": []},
        }}]}
        calcular_metricas_agente(response, "Calidad")
        self.assertIsNone(response["resultados"][0]["indice"])

    def test_null_indexes_are_excluded_from_summary(self):
        summary = calcular_resumen_lote([
            {"status": "ok", "estado_procesamiento": "completo", "quality": {"indice": None}, "security": {"indice": None}, "evaluation": {"veredicto": "ALERTA", "riesgos_criticos": []}, "central": {"requerimientos": []}},
        ])
        self.assertIsNone(summary["calidad_promedio"])
        self.assertIsNone(summary["seguridad_promedio"])


class VerdictAndTraceabilityTests(unittest.TestCase):
    def _evaluation(self, verdict="APROBADO", risks=None, corrections=None):
        return {"veredicto": verdict, "riesgos_criticos": risks or [], "correcciones_obligatorias": corrections or [], "conclusion": "Conclusión original."}

    def test_critical_risk_overrides_approved_and_preserves_original(self):
        evaluation = self._evaluation(risks=["Exposición crítica de datos"])
        ajustar_veredicto_determinista({}, quality(), security(), evaluation)
        self.assertEqual(evaluation["veredicto"], "ALERTA")
        self.assertEqual(evaluation["veredicto_original"], "APROBADO")
        self.assertEqual(evaluation["conclusion"], "Conclusión original.")

    def test_low_index_overrides_approved(self):
        evaluation = self._evaluation()
        ajustar_veredicto_determinista({}, quality(.8), security(), evaluation)
        self.assertEqual(evaluation["veredicto"], "CORREGIR")

    def test_insufficient_input_forces_alert(self):
        evaluation = self._evaluation()
        ajustar_veredicto_determinista({}, quality(), security(), evaluation, {"estado": "informacion_insuficiente"})
        self.assertEqual(evaluation["veredicto"], "ALERTA")

    def test_non_evaluable_metric_forces_alert(self):
        evaluation = self._evaluation()
        ajustar_veredicto_determinista({}, quality(None), security(), evaluation)
        self.assertEqual(evaluation["veredicto"], "ALERTA")

    def test_consistent_approved_is_not_rewritten(self):
        evaluation = self._evaluation()
        ajustar_veredicto_determinista({}, quality(), security(), evaluation)
        self.assertEqual(evaluation["veredicto"], "APROBADO")
        self.assertNotIn("veredicto_original", evaluation)

    def test_gitlab_labels_follow_evaluation(self):
        base = ["Historia de Usuario", "Pendiente", "Analizada"]
        approved = construir_etiquetas_resultado(base, "APROBADO", 1, 1)
        self.assertIn("Revisada", approved)
        self.assertNotIn("Pendiente", approved)
        self.assertNotIn("Analizada", approved)
        self.assertIn("Requiere modificación", construir_etiquetas_resultado(base, "CORREGIR", .8, .9))
        alert = construir_etiquetas_resultado(base, "ALERTA", .8, .5)
        self.assertIn("Requiere modificación", alert)
        self.assertNotIn("Analizada", alert)
        insufficient = construir_etiquetas_resultado(base, "NO_EVALUADO")
        self.assertIn("Requiere modificación", insufficient)
        self.assertNotIn("Pendiente", insufficient)

    def test_consolidation_separates_technical_and_evaluation_state(self):
        central = {"resultados": [{"issue_iid": 17, "requerimientos": [{"tipo": "RF", "descripcion_formal": "El sistema deberá registrar.", "procedencia": "extraido"}]}]}
        evaluator = {"resultados": [{"issue_iid": 17, **self._evaluation()}]}
        final = consolidar_lote({17}, central, {"resultados": [quality()]}, {"resultados": [security()]}, evaluator)
        result = final["resultados"][0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["estado_procesamiento"], "completo")
        self.assertEqual(result["estado_evaluacion"], "APROBADO")
        self.assertEqual(result["estado_revision_humana"], "pendiente")

    def test_traceability_contains_provenance_and_human_review(self):
        result = {
            "status": "ok", "estado_evaluacion": "CORREGIR", "responsable_revision": None,
            "estado_revision_humana": "pendiente", "issue_data": {"criterios_aceptacion": ["Correo único"]},
            "central": {"historia_id": "HU-017", "titulo": "Registro", "observaciones": [], "requerimientos": [{
                "id": "RF-001", "descripcion": "Registrar", "tipo": "RF", "justificacion": "Necesario",
                "prioridad": "Alta", "origen": "Quiero registrar", "procedencia": "extraido",
            }]},
        }
        row = construir_filas_trazabilidad([result])[0]
        self.assertEqual(row["procedencia"], "extraido")
        self.assertEqual(row["estado_evaluacion"], "CORREGIR")
        self.assertEqual(row["estado_aprobacion_humana"], "Pendiente")

    def test_docx_keeps_main_structure_with_extended_traceability(self):
        result = {
            "issue_iid": 17, "status": "ok", "estado_procesamiento": "completo",
            "estado_evaluacion": "APROBADO", "responsable_revision": None,
            "estado_revision_humana": "pendiente", "issue_data": {"criterios_aceptacion": ["Correo único"]},
            "central": {"historia_id": "HU-017", "titulo": "Registro", "actor": "Administrador",
                        "objetivo": "Permitir acceso", "restricciones": [], "observaciones": [], "requerimientos": [{
                            "id": "RF-001", "nombre": "Registrar", "descripcion": "El sistema deberá registrar.",
                            "descripcion_formal": "El sistema deberá registrar.", "tipo": "RF", "justificacion": "Necesario",
                            "prioridad": "Alta", "origen": "Quiero registrar", "procedencia": "extraido",
                        }]},
            "quality": {"indice": 1.0, "metricas": {}, "recomendaciones": []},
            "security": {"indice": 1.0, "metricas": {}, "recomendaciones": [], "lot_recomendado": "LoT-1"},
            "evaluation": self._evaluation(), "errors": [],
        }
        artifact = generar_documento_formal_lote_docx(construir_resultado_lote("Proyecto", "Sprint", [result]))
        self.assertGreater(len(artifact.getvalue()), 1000)


if __name__ == "__main__":
    unittest.main()
