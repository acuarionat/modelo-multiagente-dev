import copy
import json
import unittest
from unittest.mock import patch

from core.batch_contract import (
    completar_resultado_calidad,
    diagnosticar_contrato_calidad_llm,
    es_funcion_principal_evaluable,
    validar_respuesta_lote,
)
from core.graph import _ejecutar_sublotes_remotos, preparar_entrada_calidad
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import RemoteBatchError
from tests.test_quality_input_preparation import ISSUES, central_fixture


def quality_item(iid):
    return {
        "issue_iid": iid,
        "historia_id": f"HU-{iid:03d}",
        "metricas": {
            "cobertura_funcional": {
                "funciones_especificadas": ["Función principal"],
                "funciones_incluidas": ["Función principal"],
                "funciones_faltantes": [],
                "recomendacion": "",
            },
            "adecuacion_funcional": {
                "funciones_evaluables": ["Función principal"],
                "funciones_alineadas": ["Función principal"],
                "funciones_no_alineadas": [],
                "recomendacion": "",
            },
        },
        "observaciones": [],
        "recomendaciones": [],
    }


def response(ids=(6, 7)):
    return {"agente": "calidad", "resultados": [quality_item(iid) for iid in ids]}


def requirement(name, description):
    return {"nombre": name, "descripcion_formal": description, "tipo": "RF", "origen": name}


class QualityContractStageTests(unittest.TestCase):
    def test_hu006_hu007_minimum_llm_contract_is_valid_without_index(self):
        fixture = response()
        diagnostic = diagnosticar_contrato_calidad_llm(fixture)
        self.assertTrue(diagnostic["valid"])
        self.assertNotIn("indice", fixture["resultados"][0])
        self.assertEqual(validar_respuesta_lote(fixture, {6, 7}, "Calidad", contract_stage="llm_raw"), [])
        self.assertTrue(validar_respuesta_lote(fixture, {6, 7}, "Calidad", contract_stage="post_python"))

    def test_empty_gap_lists_recommendations_and_observations_are_valid(self):
        diagnostic = diagnosticar_contrato_calidad_llm(response())
        paths = diagnostic["empty_but_valid_fields"]
        self.assertTrue(any(path.endswith("funciones_faltantes") for path in paths))
        self.assertTrue(any(path.endswith("funciones_no_alineadas") for path in paths))
        self.assertTrue(any(path.endswith("recomendacion") for path in paths))
        self.assertTrue(any(path.endswith("observaciones") for path in paths))

    def test_missing_required_field_and_wrong_type_fail(self):
        fixture = response((6,))
        del fixture["resultados"][0]["metricas"]["cobertura_funcional"]["funciones_incluidas"]
        diagnostic = diagnosticar_contrato_calidad_llm(fixture)
        self.assertFalse(diagnostic["valid"])
        self.assertIn("resultados[0].metricas.cobertura_funcional.funciones_incluidas", diagnostic["missing_fields"])
        fixture = response((6,))
        fixture["resultados"][0]["metricas"]["adecuacion_funcional"]["funciones_alineadas"] = "incorrecto"
        self.assertFalse(diagnosticar_contrato_calidad_llm(fixture)["valid"])

    def test_old_alias_is_reported_but_not_accepted(self):
        fixture = response((6,))
        metrics = fixture["resultados"][0]["metricas"]
        metrics["mc01"] = metrics.pop("cobertura_funcional")
        diagnostic = diagnosticar_contrato_calidad_llm(fixture)
        self.assertFalse(diagnostic["valid"])
        self.assertEqual(diagnostic["alias_fields_detected"][0]["ruta"], "resultados[0].metricas.mc01")

    def test_python_completion_derives_values_and_index(self):
        item = quality_item(10)
        context = {
            "funcionalidad": "Cancelar una cita",
            "objetivo": "Liberar el horario reservado",
            "requerimientos_preparados": [
                requirement("Cancelar una cita", "El sistema deberá permitir cancelar una cita."),
                requirement("Restringir cancelación cuando falten menos de 24 horas", "El sistema deberá impedir cancelar cuando falten menos de 24 horas."),
            ],
        }
        item["metricas"]["cobertura_funcional"].update({
            "funciones_especificadas": ["Cancelar una cita"],
            "funciones_incluidas": ["Cancelar una cita"],
        })
        item["metricas"]["adecuacion_funcional"].update({
            "funciones_evaluables": ["Cancelar una cita"],
            "funciones_alineadas": ["Cancelar una cita"],
        })
        completar_resultado_calidad(item, context)
        self.assertEqual(item["metricas"]["cobertura_funcional"]["variables"], {
            "numerador": 0, "denominador": 1,
        })
        self.assertEqual(item["metricas"]["adecuacion_funcional"]["valor"], 1)
        self.assertEqual(item["indice"], 1)

    def test_contract_error_audit_preserves_received_ids(self):
        reiniciar_contadores()
        fixture = response()
        del fixture["resultados"][0]["observaciones"]
        with self.assertRaises(RemoteBatchError):
            _ejecutar_sublotes_remotos(
                json.dumps({"agente": "central", "resultados": [{"issue_iid": 6}, {"issue_iid": 7}]}),
                "Calidad", 2, lambda _raw, _batch: json.dumps(fixture),
            )
        error = next(e for e in obtener_contadores()["eventos_sublotes_remotos"] if e["event"] == "remote_sub_batch_error")
        self.assertEqual(error["received_issue_ids"], [6, 7])
        self.assertEqual(error["identity_validation"], "success")
        self.assertEqual(error["contract_validation"], "failed")
        self.assertEqual(error["contract_stage"], "llm_raw")

    def test_hu010_keeps_two_rf_but_one_main_universe(self):
        main = requirement("Cancelar una cita", "El sistema deberá permitir cancelar una cita.")
        rule = requirement("Restringir cancelación", "El sistema deberá impedir cancelar cuando falten menos de 24 horas.")
        self.assertEqual(sum(x["tipo"] == "RF" for x in (main, rule)), 2)
        self.assertTrue(es_funcion_principal_evaluable(main, "Cancelar una cita"))
        self.assertFalse(es_funcion_principal_evaluable(rule, "Cancelar una cita"))
        self.assertEqual(rule["tipo"], "RF")
        self.assertIn("24 horas", rule["descripcion_formal"])

    def test_prepared_audit_reports_hu010_universe_one(self):
        with patch("core.graph.registrar_evento_grafo") as audit:
            preparar_entrada_calidad(
                json.dumps(central_fixture(), ensure_ascii=False), list(ISSUES.values()),
            )
        hu010 = next(
            item for item in audit.call_args.kwargs["by_issue"]
            if item["issue_iid"] == 10
        )
        self.assertEqual((hu010["rf"], hu010["rnf"]), (2, 0))
        self.assertEqual((hu010["mc01_universe"], hu010["mc02_universe"]), (1, 1))

    def test_cross_domain_conditioning_rules_do_not_expand_universe(self):
        cases = [
            ("Aprobar vacaciones", "Impedir aprobar vacaciones sin saldo"),
            ("Registrar pedido", "Impedir registrar pedido sin cliente"),
        ]
        for main_text, rule_text in cases:
            with self.subTest(main=main_text):
                main = requirement(main_text, main_text)
                rule = requirement(rule_text, rule_text)
                self.assertEqual(sum(es_funcion_principal_evaluable(x, main_text) for x in (main, rule)), 1)
                self.assertEqual(sum(x["tipo"] == "RF" for x in (main, rule)), 2)

    def test_independent_calculation_remains_main_function(self):
        independent = requirement("Calcular penalización automáticamente", "Calcular penalización automáticamente")
        self.assertTrue(es_funcion_principal_evaluable(independent, "Registrar solicitud y calcular penalización"))


if __name__ == "__main__":
    unittest.main()
