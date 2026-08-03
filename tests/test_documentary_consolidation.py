import unittest

from core.batch_contract import (
    consolidar_requerimientos_formales_equivalentes, recopilar_recomendaciones,
    renumerar_requerimientos, validar_consolidacion_documental_final,
)
from core.performance_audit import (
    obtener_contadores, registrar_evento_grafo, registrar_integridad_central,
    reiniciar_contadores,
)


def req(name, kind="RF", description=None, origin="fixture", provenance="explícita — criterio de aceptación", code=None):
    return {
        "id": code, "temp_id": f"TEMP-{name}", "nombre": name, "tipo": kind,
        "descripcion_formal": description or f"El sistema deberá {name[:1].lower() + name[1:]}",
        "descripcion": description or f"El sistema deberá {name[:1].lower() + name[1:]}",
        "origen": origin, "procedencia": provenance, "justificacion": "Fixture.", "prioridad": "Media",
    }


HU006 = [
    req("Consulta Horarios Disponibles", origin="consultar horarios disponibles", provenance="explícita — funcionalidad", code="RF-X1"),
    req("Mostrar nombre y especialidad", code="RF-X2"),
    req("Actualizar disponibilidad", code="RF-X3"),
    req("Mostrar únicamente horarios disponibles", origin="mostrar únicamente horarios disponibles", code="RF-X4"),
    req("Tiempo de respuesta", "RNF", "El sistema deberá responder a la consulta en menos de tres segundos.", code="RNF-X1"),
    req("Disponibilidad en tiempo real", "RNF", "El sistema deberá mostrar información de disponibilidad en tiempo real.", code="RNF-X2"),
]

HU009 = [
    req("Filtrar reportes por fecha"), req("Exportar reportes en PDF"),
    req("Mostrar estadísticas de citas en reportes", code="RF-S1"),
    req("Generar reportes de citas"), req("Mostrar estadísticas de citas", code="RF-S2"),
    req("Imprimir reportes"),
]


def quality_security(*, recommendations=None, unclassified=None, identified=None, ms02=1.0):
    return {
        "quality": {"indice": 1.0, "metricas": {
            "cobertura_funcional": {"funciones_faltantes": [], "recomendacion": ""},
            "adecuacion_funcional": {"funciones_no_alineadas": [], "recomendacion": ""},
        }, "recomendaciones": recommendations or []},
        "security": {"indice": ms02, "metricas": {
            "cobertura_seguridad": {"aspectos_faltantes": [], "aspectos_parciales": [], "recomendacion": ""},
            "clasificacion_datos": {
                "datos_identificados": identified or [], "datos_sin_clasificacion": unclassified or [],
                "valor": ms02, "recomendacion": "",
            },
        }, "recomendaciones": []},
        "evaluation": {"correcciones_obligatorias": []},
    }


class DocumentaryDedupTests(unittest.TestCase):
    def test_hu006_merges_equivalent_rf_and_preserves_both_evidences(self):
        consolidated, audit = consolidar_requerimientos_formales_equivalentes(HU006)
        self.assertEqual((audit["rf_before"], audit["rf_after"], audit["rnf_after"]), (4, 3, 2))
        self.assertEqual(audit["equivalent_rf_merged"], 1)
        canonical = consolidated[0]
        self.assertEqual(len(canonical["evidencias_equivalentes"]), 2)
        self.assertEqual(
            {item["procedencia"] for item in canonical["evidencias_equivalentes"]},
            {"explícita — funcionalidad", "explícita — criterio de aceptación"},
        )

    def test_first_representation_order_and_codes_after_merge(self):
        consolidated, _ = consolidar_requerimientos_formales_equivalentes(HU006)
        self.assertEqual(consolidated[0]["nombre"], "Consulta Horarios Disponibles")
        renumerar_requerimientos([{"requerimientos": consolidated}])
        self.assertEqual([x["id"] for x in consolidated], ["RF-001", "RF-002", "RF-003", "RNF-001", "RNF-002"])

    def test_idempotent(self):
        once, _ = consolidar_requerimientos_formales_equivalentes(HU006)
        twice, audit = consolidar_requerimientos_formales_equivalentes(once)
        self.assertEqual(len(twice), len(once))
        self.assertEqual(audit["equivalent_rf_merged"], 0)
        self.assertEqual(twice[0]["evidencias_equivalentes"], once[0]["evidencias_equivalentes"])

    def test_rf_and_rnf_never_merge(self):
        values = [req("Actualizar información"), req("Actualizar información", "RNF")]
        consolidated, _ = consolidar_requerimientos_formales_equivalentes(values)
        self.assertEqual(len(consolidated), 2)

    def test_contextual_rule_remains_separate(self):
        values = [
            req("Cancelar una reserva"),
            req("Impedir cancelar una reserva cuando falten menos de 24 horas"),
        ]
        consolidated, _ = consolidar_requerimientos_formales_equivalentes(values)
        self.assertEqual(len(consolidated), 2)

    def test_generate_export_and_print_remain_separate(self):
        values = [req("Generar reportes"), req("Exportar reportes en PDF"), req("Imprimir reportes")]
        consolidated, _ = consolidar_requerimientos_formales_equivalentes(values)
        self.assertEqual(len(consolidated), 3)

    def test_hu009_merges_only_statistics(self):
        consolidated, audit = consolidar_requerimientos_formales_equivalentes(HU009)
        self.assertEqual((audit["rf_before"], audit["rf_after"], audit["equivalent_rf_merged"]), (6, 5, 1))
        statistics = [x for x in consolidated if "estadísticas" in x["nombre"]]
        self.assertEqual(len(statistics), 1)
        self.assertEqual(len(statistics[0]["evidencias_equivalentes"]), 2)

    def test_agenda_rf_and_realtime_rnf_remain_and_are_formalized(self):
        values = [
            req("La agenda deberá actualizarse", "RF", "El sistema deberá actualizar agenda."),
            req("Agenda en tiempo real", "RNF", "El sistema deberá actualizar agenda en tiempo real."),
        ]
        consolidated, _ = consolidar_requerimientos_formales_equivalentes(values)
        self.assertEqual([x["tipo"] for x in consolidated], ["RF", "RNF"])
        self.assertIn("cuando cambie la información", consolidated[0]["descripcion_formal"])
        self.assertEqual(consolidated[1]["descripcion_formal"], "El sistema deberá reflejar la información actualizada en tiempo real.")


class RecommendationCleanupTests(unittest.TestCase):
    def test_structured_recommendation_uses_only_recognized_semantic_field(self):
        result = quality_security(recommendations=[{"accion": "Revisar la trazabilidad documental.", "hash": "x"}])
        self.assertEqual(recopilar_recomendaciones(result), ["Revisar la trazabilidad documental."])

    def test_unknown_dictionary_is_discarded(self):
        result = quality_security(recommendations=[{"temp_id": "RF-X", "tipo": "RNF"}])
        self.assertEqual(recopilar_recomendaciones(result), [])
        self.assertEqual(result["auditoria_consolidacion_documental"]["malformed_recommendations_removed"], 1)

    def test_lists_flatten_and_duplicates_are_removed(self):
        result = quality_security(recommendations=[["Revisar evidencia."], "Revisar evidencia."])
        self.assertEqual(recopilar_recomendaciones(result), ["Revisar evidencia."])
        self.assertEqual(result["auditoria_consolidacion_documental"]["duplicate_recommendations_removed"], 1)

    def test_neutral_evidence_is_not_a_recommendation(self):
        result = quality_security(recommendations=["Evidencia de seguridad completamente ficticia."])
        self.assertEqual(recopilar_recomendaciones(result), [])

    def test_hu010_classification_recommendation_is_preserved_once(self):
        result = quality_security(identified=["Nombre ficticio", "Documento ficticio"], unclassified=["Nombre ficticio", "Documento ficticio"], ms02=0.0)
        recommendations = recopilar_recomendaciones(result)
        self.assertEqual(len(recommendations), 1)
        self.assertIn("Clasificar explícitamente", recommendations[0])

    def test_hu009_no_data_does_not_get_classification_recommendation(self):
        result = quality_security(identified=[], unclassified=[], ms02=None)
        self.assertEqual(recopilar_recomendaciones(result), [])

    def test_complete_classification_removes_incompatible_recommendation(self):
        result = quality_security(
            recommendations=["Clasificar explícitamente los datos identificados."],
            identified=["Correo"], unclassified=[], ms02=1.0,
        )
        self.assertEqual(recopilar_recomendaciones(result), [])


class FinalValidationAndAuditTests(unittest.TestCase):
    def test_no_python_structure_reaches_final_validation(self):
        item = {"issue_iid": 6, "central": {"requerimientos": []}, "recommendations": ["{'tipo': 'RF'}"]}
        self.assertTrue(validar_consolidacion_documental_final([item]))

    def test_final_validation_accepts_none_metric_and_no_recommendations(self):
        item = {"issue_iid": 9, "central": {"requerimientos": []}, "quality": {"indice": 1}, "security": {"indice": None}, "recommendations": []}
        self.assertEqual(validar_consolidacion_documental_final([item]), [])

    def test_active_sub_batch_is_cleared_and_pipeline_state_is_separate(self):
        reiniciar_contadores()
        registrar_integridad_central([6], [6])
        for agent in ("Quality", "Security", "Evaluator"):
            registrar_evento_grafo("node_end", agent, elapsed_seconds=1)
        audit = obtener_contadores()
        self.assertIsNone(audit["resumen_parcial_central"]["active_sub_batch"])
        self.assertFalse(audit["central_downstream_snapshot"])
        self.assertTrue(audit["pipeline_downstream_agents_executed"])


if __name__ == "__main__":
    unittest.main()
