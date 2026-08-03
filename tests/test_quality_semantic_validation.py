import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core.batch_contract import (
    completar_resultado_calidad, obtener_universo_funcional_calidad,
    validar_semantica_calidad_llm,
)
from core.graph import _ejecutar_sublotes_remotos, preparar_entrada_calidad
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import RemoteBatchError
from tests.test_quality_input_preparation import (
    ISSUES as REAL_ISSUES, central_fixture as real_central_fixture,
)


def requirement(name, description=None, origin=None):
    return {
        "nombre": name,
        "descripcion_formal": description or f"El sistema deberá {name.casefold()}.",
        "tipo": "RF",
        "origen": origin or name,
        "procedencia": "explícita — funcionalidad",
    }


def prepared(iid=10, names=("Cancelar una cita",), functionality="Cancelar una cita"):
    return {
        "agente": "central",
        "resultados": [{
            "issue_iid": iid, "historia_id": f"HU-{iid:03d}",
            "funcionalidad": functionality,
            "requerimientos": [requirement(name) for name in names],
        }],
    }


def quality(iid=10, names=("Cancelar una cita",), *, included=None, missing=None,
            aligned=None, not_aligned=None, coverage_explanation="", alignment_explanation=""):
    return {
        "agente": "calidad",
        "resultados": [{
            "issue_iid": iid, "historia_id": f"HU-{iid:03d}",
            "metricas": {
                "cobertura_funcional": {
                    "funciones_especificadas": list(names),
                    "funciones_incluidas": [] if included is None else list(included),
                    "funciones_faltantes": [] if missing is None else list(missing),
                    "justificacion": coverage_explanation, "recomendacion": "",
                },
                "adecuacion_funcional": {
                    "funciones_evaluables": list(names),
                    "funciones_alineadas": [] if aligned is None else list(aligned),
                    "funciones_no_alineadas": [] if not_aligned is None else list(not_aligned),
                    "justificacion": alignment_explanation, "recomendacion": "",
                },
            },
            "observaciones": "", "recomendaciones": [],
        }],
    }


class QualitySemanticValidationTests(unittest.TestCase):
    def test_nonempty_universe_with_four_empty_lists_is_incomplete(self):
        result = validar_semantica_calidad_llm(quality(), prepared())
        self.assertEqual((result["valid"], result["error_category"]), (False, "REMOTE_SEMANTIC_INCOMPLETE"))
        self.assertEqual(result["by_issue"][0]["unclassified_coverage"], 1)
        self.assertEqual(result["by_issue"][0]["unclassified_alignment"], 1)

    def test_complete_missing_partition_with_explanation_is_valid(self):
        name = "Consultar calificaciones"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), missing=(name,), not_aligned=(name,),
                    coverage_explanation="No existe RF equivalente.",
                    alignment_explanation="No contribuye al objetivo declarado."),
            prepared(names=(name,), functionality=name),
        )
        self.assertTrue(result["valid"])

    def test_complete_included_partition_is_valid_without_recommendation(self):
        name = "Generar factura"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), included=(name,), aligned=(name,)),
            prepared(names=(name,), functionality=name),
        )
        self.assertTrue(result["valid"])

    def test_one_unclassified_function_is_incomplete(self):
        names = ("Consultar agenda", "Registrar paciente")
        result = validar_semantica_calidad_llm(
            quality(names=names, included=(names[0],), aligned=names),
            prepared(names=names, functionality=names[0]),
        )
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_INCOMPLETE")
        self.assertEqual(result["by_issue"][0]["unclassified_coverage"], 1)

    def test_function_in_both_coverage_groups_is_invalid(self):
        name = "Aprobar solicitud"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), included=(name,), missing=(name,), aligned=(name,),
                    coverage_explanation="Clasificación emitida."),
            prepared(names=(name,), functionality=name),
        )
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_INCOMPLETE")

    def test_empty_alignment_partition_is_incomplete(self):
        name = "Generar factura"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), included=(name,)), prepared(names=(name,), functionality=name),
        )
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_INCOMPLETE")

    def test_complete_not_aligned_partition_with_explanation_is_valid(self):
        name = "Generar factura"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), included=(name,), not_aligned=(name,),
                    alignment_explanation="No contribuye al objetivo comercial declarado."),
            prepared(names=(name,), functionality=name),
        )
        self.assertTrue(result["valid"])

    def test_gap_without_explanation_is_contradiction_when_rf_exists(self):
        name = "Cancelar una cita"
        result = validar_semantica_calidad_llm(
            quality(names=(name,), missing=(name,), aligned=(name,)),
            prepared(names=(name,), functionality=name),
        )
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_CONTRADICTION")
        self.assertEqual(result["by_issue"][0]["contradictions"], 1)
        self.assertEqual(len(result["by_issue"][0]["contradiction_function_ids"]), 1)

    def test_hu006_and_hu007_complete_partitions_remain_valid(self):
        for iid, count in ((6, 3), (7, 4)):
            names = tuple(f"Función {index}" for index in range(1, count + 1))
            with self.subTest(iid=iid):
                result = validar_semantica_calidad_llm(
                    quality(iid=iid, names=names, included=names, aligned=names),
                    prepared(iid=iid, names=names, functionality=names[0]),
                )
                self.assertTrue(result["valid"])
                self.assertEqual(result["by_issue"][0]["classified_included"], count)

    def test_hu010_keeps_two_documentary_rf_and_one_main_function(self):
        source = prepared(names=("Permitir la cancelación de una cita médica",), functionality="Cancelar una cita médica")
        source["resultados"][0]["requerimientos"].append(requirement(
            "Restringir la cancelación con menos de 24 horas",
            "El sistema deberá impedir la cancelación de una cita cuando falten menos de 24 horas para su realización.",
        ))
        result = validar_semantica_calidad_llm(
            quality(names=("Cancelar una cita médica",), included=("Permitir la cancelación de una cita médica",), aligned=("Cancelar una cita",)),
            source,
        )
        self.assertEqual(len(source["resultados"][0]["requerimientos"]), 2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["by_issue"][0]["expected_functions"], 1)

    def test_omissions_are_not_mutated_into_negative_lists(self):
        response = quality()
        original = copy.deepcopy(response)
        validar_semantica_calidad_llm(response, prepared())
        self.assertEqual(response, original)

    def test_contextual_hr_rule_does_not_expand_main_universe(self):
        source = prepared(names=("Aprobar solicitud",), functionality="Aprobar solicitud")
        source["resultados"][0]["requerimientos"].append(requirement(
            "Impedir aprobación bajo una condición",
            "El sistema deberá impedir aprobar una solicitud cuando falte autorización.",
        ))
        result = validar_semantica_calidad_llm(
            quality(names=("Aprobar solicitud",), included=("Aprobar solicitud",), aligned=("Aprobar solicitud",)), source,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["by_issue"][0]["expected_functions"], 1)

    def test_graph_rejects_before_consolidation_and_audits_semantics(self):
        reiniciar_contadores()
        source = prepared()
        response = quality()
        with patch("core.graph.validar_respuesta_lote", return_value=[]), self.assertRaises(RemoteBatchError) as caught:
            _ejecutar_sublotes_remotos(json.dumps(source), "Calidad", 2, lambda _raw, _batch: json.dumps(response))
        self.assertEqual(caught.exception.category, "REMOTE_SEMANTIC_INCOMPLETE")
        events = obtener_contadores()["eventos_sublotes_remotos"]
        failed = next(item for item in events if item["event"] == "remote_sub_batch_error")
        self.assertEqual(failed["identity_validation"], "success")
        self.assertEqual(failed["contract_validation"], "success")
        self.assertEqual(failed["semantic_validation"], "failed")
        self.assertEqual(failed["failed_validator"], "validar_semantica_calidad_llm")
        self.assertNotIn("Cancelar", json.dumps(failed))

    def test_all_five_stories_share_expected_prepared_universe(self):
        with patch("core.graph.registrar_evento_grafo"):
            payload = json.loads(preparar_entrada_calidad(
                json.dumps(real_central_fixture(), ensure_ascii=False), list(REAL_ISSUES.values()),
            ))
        indexed = {item["issue_iid"]: item for item in payload["resultados"]}
        self.assertEqual(
            {iid: len(indexed[iid]["funciones_principales_evaluables"]) for iid in indexed},
            {6: 3, 7: 4, 8: 3, 9: 5, 10: 1},
        )

    def test_hu010_single_source_drives_preparation_semantics_and_calculation(self):
        with patch("core.graph.registrar_evento_grafo") as audit:
            payload = json.loads(preparar_entrada_calidad(
                json.dumps(real_central_fixture(order=(10,)), ensure_ascii=False),
                [REAL_ISSUES[10]],
            ))
        source = payload["resultados"][0]
        universe = obtener_universo_funcional_calidad(source)
        main = tuple(universe["funciones_principales_evaluables"])
        self.assertEqual((universe["documentary_rf_count"], universe["documentary_rnf_count"]), (2, 0))
        self.assertEqual((len(main), universe["conditional_rule_count"]), (1, 1))
        response = quality(names=main, included=main, aligned=main)
        semantic = validar_semantica_calidad_llm(response, payload)
        self.assertTrue(semantic["valid"])
        self.assertEqual(semantic["by_issue"][0]["expected_functions"], 1)
        context = copy.deepcopy(REAL_ISSUES[10])
        context.update({
            "requerimientos_preparados": source["requerimientos"],
            "funciones_principales_evaluables": source["funciones_principales_evaluables"],
            "reglas_funcionales_contextuales": source["reglas_funcionales_contextuales"],
        })
        completed = completar_resultado_calidad(response["resultados"][0], context)
        self.assertEqual(completed["metricas"]["cobertura_funcional"]["variables"]["denominador"], 1)
        self.assertEqual(len(completed["metricas"]["adecuacion_funcional"]["funciones_evaluables"]), 1)
        event = next(call for call in audit.call_args_list if call.args[0] == "quality_input_prepared")
        hu010 = event.kwargs["by_issue"][0]
        self.assertEqual(
            (hu010["rf"], hu010["rnf"], hu010["main_functions"], hu010["conditional_rules"]),
            (2, 0, 1, 1),
        )

    def test_conditioning_rule_reported_as_function_is_out_of_universe(self):
        with patch("core.graph.registrar_evento_grafo"):
            payload = json.loads(preparar_entrada_calidad(
                json.dumps(real_central_fixture(order=(10,)), ensure_ascii=False), [REAL_ISSUES[10]],
            ))
        source = payload["resultados"][0]
        main = source["funciones_principales_evaluables"][0]
        rule = source["reglas_funcionales_contextuales"][0]
        response = quality(
            names=(main, rule), included=(main, rule), aligned=(main, rule),
        )
        semantic = validar_semantica_calidad_llm(response, payload)
        self.assertFalse(semantic["valid"])
        self.assertEqual(semantic["error_category"], "REMOTE_SEMANTIC_OUT_OF_UNIVERSE")
        self.assertEqual(semantic["by_issue"][0]["out_of_universe_count"], 1)
        self.assertNotIn("valor", response["resultados"][0]["metricas"]["cobertura_funcional"])

    def test_each_metric_list_reports_contextual_rule_by_sanitized_field(self):
        with patch("core.graph.registrar_evento_grafo"):
            payload = json.loads(preparar_entrada_calidad(
                json.dumps(real_central_fixture(order=(10,)), ensure_ascii=False), [REAL_ISSUES[10]],
            ))
        source = payload["resultados"][0]
        main = source["funciones_principales_evaluables"][0]
        rule = source["reglas_funcionales_contextuales"][0]
        fields = (
            "funciones_especificadas", "funciones_incluidas", "funciones_faltantes",
            "funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas",
        )
        for field in fields:
            with self.subTest(field=field):
                response = quality(names=(main,), included=(main,), aligned=(main,))
                coverage = response["resultados"][0]["metricas"]["cobertura_funcional"]
                alignment = response["resultados"][0]["metricas"]["adecuacion_funcional"]
                target = coverage if field in coverage else alignment
                target[field].append(rule)
                semantic = validar_semantica_calidad_llm(response, payload)
                diagnostic = semantic["by_issue"][0]
                self.assertEqual(semantic["error_category"], "REMOTE_SEMANTIC_OUT_OF_UNIVERSE")
                self.assertEqual(diagnostic["out_of_universe_count"], 1)
                self.assertEqual(diagnostic["out_of_universe_by_field"], {field: 1})
                self.assertEqual(len(diagnostic["out_of_universe_element_ids"]), 1)
                serialized = json.dumps(diagnostic, ensure_ascii=False)
                self.assertNotIn(rule, serialized)
                self.assertNotIn("24 horas", serialized)

    def test_quality_prompt_separates_context_from_metric_universe(self):
        prompt = Path("prompts/quality_prompt.txt").read_text(encoding="utf-8").casefold()
        self.assertIn("funciones_principales_evaluables", prompt)
        self.assertIn("reglas_funcionales_contextuales", prompt)
        self.assertIn("solamente para comprender", prompt)
        self.assertIn("no copies", prompt)
        self.assertIn("no amplíes", prompt)
        self.assertIn("razonamiento contextual", prompt)
        for field in (
            "funciones_especificadas", "funciones_incluidas", "funciones_faltantes",
            "funciones_evaluables", "funciones_alineadas", "funciones_no_alineadas",
        ):
            self.assertIn(field, prompt)

    def test_universe_classification_is_idempotent(self):
        with patch("core.graph.registrar_evento_grafo"):
            first = json.loads(preparar_entrada_calidad(
                json.dumps(real_central_fixture(order=(10,)), ensure_ascii=False), [REAL_ISSUES[10]],
            ))
            second = json.loads(preparar_entrada_calidad(
                json.dumps(first, ensure_ascii=False), [REAL_ISSUES[10]],
            ))
        self.assertEqual(first, second)

    def test_commercial_and_hr_conditioning_rules_are_contextual(self):
        cases = (
            ("Registrar un pedido", "Impedir registrar el pedido si no existe un cliente"),
            ("Aprobar vacaciones", "Impedir aprobarlas cuando no exista saldo"),
            ("Generar factura", "No permitir generarla sin datos fiscales"),
        )
        for main, rule in cases:
            with self.subTest(main=main):
                source = {
                    "requerimientos": [
                        requirement(main),
                        requirement(rule, f"El sistema deberá {rule.casefold()}.")
                    ]
                }
                universe = obtener_universo_funcional_calidad(source, {"funcionalidad": main})
                self.assertEqual(universe["main_function_count"], 1)
                self.assertEqual(universe["conditional_rule_count"], 1)

    def test_independent_function_is_not_excluded(self):
        source = {"requerimientos": [
            requirement("Registrar una devolución"),
            requirement("Calcular automáticamente una penalización"),
        ]}
        universe = obtener_universo_funcional_calidad(source, {"funcionalidad": "Registrar una devolución"})
        self.assertEqual(universe["main_function_count"], 2)
        self.assertEqual(universe["conditional_rule_count"], 0)


if __name__ == "__main__":
    unittest.main()
