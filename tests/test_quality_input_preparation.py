import copy
import io
import inspect
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from core.batch_contract import (
    _descripcion_requerimiento_explicito, _firma_funcional,
    completar_requerimientos_explicitos_faltantes, completar_resultado_calidad,
    funciones_equivalentes, obtener_universo_funcional_calidad,
)
from core.graph import nodo_calidad, nodo_seguridad, preparar_entrada_calidad
from scripts.test_hybrid_flow_five import _persist_and_print_summary
from tests.test_semantic_traceability import ISSUES, RAW


def central_fixture(order=(6, 7, 8, 9, 10)):
    return {
        "agente": "central",
        "milestone": "Fixture local",
        "resultados": [
            {
                "issue_iid": iid,
                "historia_id": ISSUES[iid]["historia_id"],
                "actor": f"Actor {iid}",
                "objetivo": f"Objetivo {iid}",
                "requerimientos": copy.deepcopy(RAW[iid]),
                "restricciones": copy.deepcopy(ISSUES[iid]["restricciones"]),
                "observaciones": copy.deepcopy(ISSUES[iid]["observaciones"]),
            }
            for iid in order
        ],
    }


def parsed_prepared(central=None, issues=None):
    central = central or central_fixture()
    issues = issues or list(ISSUES.values())
    with patch("core.graph.registrar_evento_grafo"):
        return json.loads(preparar_entrada_calidad(json.dumps(central, ensure_ascii=False), issues))


class QualityInputPreparationTests(unittest.TestCase):
    def _hu006_single_raw_fixture(self):
        issue = copy.deepcopy(ISSUES[6])
        issue.update({"actor": "Paciente", "seguridad": {}})
        central = {
            "agente": "central", "milestone": "Fixture HU-006", "resultados": [{
                "issue_iid": 6, "historia_id": "HU-006", "actor": "Paciente",
                "objetivo": "Programar una cita médica sin conflictos de horario.",
                "requerimientos": [{
                    "nombre": "Consulta Horarios Disponibles", "tipo": "RF",
                    "descripcion_formal": (
                        "El sistema deberá mostrar únicamente horarios disponibles "
                        "para consulta por parte del paciente."
                    ),
                    "origen": "", "procedencia": "inferida",
                }],
            }],
        }
        return central, issue

    def test_hu006_single_raw_requirement_prepares_four_rf_and_two_rnf(self):
        central, issue = self._hu006_single_raw_fixture()
        prepared = parsed_prepared(central, [issue])["resultados"][0]["requerimientos"]
        self.assertEqual(len(prepared), 6)
        self.assertEqual(sum(item["tipo"] == "RF" for item in prepared), 4)
        self.assertEqual(sum(item["tipo"] == "RNF" for item in prepared), 2)

    def test_hu006_four_documentary_rf_prepare_three_metric_functions(self):
        central, issue = self._hu006_single_raw_fixture()
        central["resultados"][0]["requerimientos"] = [
            {
                "nombre": name, "tipo": "RF", "descripcion_formal": f"El sistema deberá {name.casefold()}.",
                "origen": name, "procedencia": "explícita — criterio de aceptación",
            }
            for name in (
                "Consultar horarios disponibles", "Mostrar únicamente horarios disponibles",
                "Mostrar nombre y especialidad del médico",
                "Actualizar disponibilidad después de programar la cita",
            )
        ]
        with patch("core.graph.registrar_evento_grafo") as audit:
            result = json.loads(preparar_entrada_calidad(
                json.dumps(central, ensure_ascii=False), [issue],
            ))["resultados"][0]
        universe = obtener_universo_funcional_calidad(result, issue)
        self.assertEqual((universe["documentary_rf_count"], universe["documentary_rnf_count"]), (4, 2))
        self.assertEqual(universe["main_functions_before_dedup"], 3)
        self.assertEqual(universe["main_functions_after_dedup"], 3)
        self.assertEqual(len(result["requerimientos"]), 6)
        self.assertEqual(len(result["funciones_principales_evaluables"]), 3)
        prepared_event = audit.call_args.kwargs["by_issue"][0]
        self.assertEqual(prepared_event["documentary_rf_count"], 4)
        self.assertEqual(prepared_event["documentary_rnf_count"], 2)
        self.assertEqual(prepared_event["main_functions_before_dedup"], 4)
        self.assertEqual(prepared_event["main_functions_after_dedup"], 3)
        self.assertEqual(prepared_event["equivalent_functions_merged"], 1)

    def test_hu006_single_central_requirement_recovers_four_rf_but_metric_universe_three(self):
        central, issue = self._hu006_single_raw_fixture()
        result = parsed_prepared(central, [issue])["resultados"][0]
        universe = obtener_universo_funcional_calidad(result, issue)
        self.assertEqual(universe["documentary_rf_count"], 4)
        self.assertEqual(universe["documentary_rnf_count"], 2)
        self.assertEqual(universe["main_function_count"], 3)
        self.assertEqual(len(central["resultados"][0]["requerimientos"]), 1)

    def test_hu008_realistic_variable_output_keeps_four_rf_one_rnf_but_universe_three(self):
        issue = copy.deepcopy(ISSUES[8])
        central = central_fixture(order=(8,))
        central["resultados"][0]["requerimientos"] = [
            {"nombre": "Consulta y mostrar agenda médica", "tipo": "RF", "descripcion_formal": "El sistema deberá consultar la agenda médica.", "procedencia": "explícita — funcionalidad"},
            {"nombre": "Mostrar las citas del día", "tipo": "RF", "descripcion_formal": "El sistema deberá mostrar las citas del día.", "procedencia": "explícita — criterio de aceptación"},
            {"nombre": "Mostrar el nombre del paciente", "tipo": "RF", "descripcion_formal": "El sistema deberá mostrar el nombre del paciente en cada cita.", "procedencia": "explícita — criterio de aceptación"},
            {"nombre": "Actualizar agenda", "tipo": "RF", "descripcion_formal": "El sistema deberá actualizar la agenda.", "procedencia": "explícita — observación"},
        ]
        result = parsed_prepared(central, [issue])["resultados"][0]
        universe = obtener_universo_funcional_calidad(result, issue)
        self.assertEqual((universe["documentary_rf_count"], universe["documentary_rnf_count"]), (4, 1))
        self.assertEqual(universe["main_function_count"], 3)
        self.assertTrue(any(item["tipo"] == "RNF" and "tiempo real" in item["nombre"].casefold() for item in result["requerimientos"]))

    def test_nominal_name_and_functional_description_merge_with_explicit_source(self):
        central, issue = self._hu006_single_raw_fixture()
        central["resultados"][0]["requerimientos"][0].update({
            "nombre": "Disponibilidad médica",
            "descripcion_formal": "El sistema deberá visualizar los horarios disponibles.",
        })
        trace = []
        result = completar_requerimientos_explicitos_faltantes(
            central["resultados"][0]["requerimientos"], issue, diagnostico=trace,
        )
        consultation = [item for item in result if funciones_equivalentes(
            item.get("descripcion_formal", ""), "Consultar horarios disponibles",
        )]
        self.assertEqual(len(consultation), 1)
        self.assertTrue(any(
            event["event"] == "source_merged_into_requirement"
            and event["source_kind"] in {"funcionalidad", "criterio de aceptación"}
            for event in trace
        ))
        self.assertTrue(all("source_id" in event for event in trace))

    def test_compound_object_prevents_unrelated_show_behaviors_from_merging(self):
        self.assertFalse(funciones_equivalentes("Mostrar horarios", "Mostrar nombre del médico"))
        self.assertFalse(funciones_equivalentes("Mostrar horarios", "Actualizar disponibilidad"))
        self.assertFalse(funciones_equivalentes("Consultar inventario", "Actualizar inventario"))
        self.assertFalse(funciones_equivalentes("Registrar solicitud", "Eliminar solicitud"))
        self.assertFalse(funciones_equivalentes("Generar reporte", "Imprimir reporte"))
        self.assertFalse(funciones_equivalentes("Mostrar datos", "Modificar datos"))

    def test_cross_domain_equivalences_remain_local_and_deterministic(self):
        self.assertTrue(funciones_equivalentes("Consultar horarios", "Mostrar horarios"))
        self.assertTrue(funciones_equivalentes("Consultar calificaciones", "Visualizar calificaciones"))
        self.assertTrue(funciones_equivalentes("Consultar inventario", "Visualizar existencias"))
        self.assertTrue(funciones_equivalentes("Registrar matrícula", "Permitir el registro de matrícula"))
        self.assertTrue(funciones_equivalentes("Generar reporte", "Permitir la generación de reporte"))

    def test_original_central_init_remains_identical(self):
        central = central_fixture()
        raw = json.dumps(central, ensure_ascii=False)
        snapshot = copy.deepcopy(central)
        parsed_prepared(central)
        self.assertEqual(central, snapshot)
        self.assertEqual(json.loads(raw), snapshot)

    def test_copy_recovers_requirements_for_all_five_stories(self):
        prepared = parsed_prepared()
        counts = {item["issue_iid"]: len(item["requerimientos"]) for item in prepared["resultados"]}
        self.assertEqual(counts, {6: 6, 7: 4, 8: 4, 9: 5, 10: 2})

    def test_metric_universes_for_all_five_stories_remain_expected(self):
        prepared = parsed_prepared()
        universes = {
            item["issue_iid"]: len(item["funciones_principales_evaluables"])
            for item in prepared["resultados"]
        }
        self.assertEqual(universes, {6: 3, 7: 4, 8: 3, 9: 5, 10: 1})

    def test_association_uses_iid_when_orders_differ(self):
        central = central_fixture(order=(10, 6, 9, 7, 8))
        issues = [ISSUES[iid] for iid in (8, 7, 9, 6, 10)]
        prepared = parsed_prepared(central, issues)
        indexed = {item["issue_iid"]: item for item in prepared["resultados"]}
        self.assertTrue(any("24 horas" in item["nombre"] for item in indexed[10]["requerimientos"]))
        self.assertFalse(any("24 horas" in item["nombre"] for item in indexed[6]["requerimientos"]))

    def test_expected_rf_and_rnf_are_prepared_for_quality(self):
        indexed = {item["issue_iid"]: item for item in parsed_prepared()["resultados"]}
        self.assertEqual([x["tipo"] for x in indexed[6]["requerimientos"]].count("RF"), 4)
        self.assertEqual([x["tipo"] for x in indexed[6]["requerimientos"]].count("RNF"), 2)
        self.assertTrue(any("editar" in x["nombre"].casefold() for x in indexed[7]["requerimientos"]))
        self.assertTrue(any("tiempo real" in x["nombre"].casefold() for x in indexed[8]["requerimientos"]))
        self.assertTrue(any("estadísticas" in x["nombre"].casefold() for x in indexed[9]["requerimientos"]))
        self.assertTrue(any("imprimir" in x["nombre"].casefold() for x in indexed[9]["requerimientos"]))
        rule = next(x for x in indexed[10]["requerimientos"] if "24 horas" in x["nombre"])
        self.assertEqual(rule["tipo"], "RF")

    def test_completion_is_semantically_idempotent(self):
        first = parsed_prepared()
        second = parsed_prepared(first)
        self.assertEqual(first, second)

    def test_explicit_provenance_and_evidence_are_preserved(self):
        for story in parsed_prepared()["resultados"]:
            for requirement in story["requerimientos"]:
                self.assertTrue(requirement["procedencia"].startswith("explícita —"))
                self.assertTrue(requirement["origen"].strip())

    def test_top_level_contract_is_unchanged(self):
        prepared = parsed_prepared()
        self.assertEqual(set(prepared), {"agente", "milestone", "resultados"})
        self.assertEqual(prepared["agente"], "central")

    def test_missing_source_preserves_story_without_cross_association(self):
        central = central_fixture(order=(6, 7))
        prepared = parsed_prepared(central, [ISSUES[6]])
        story7 = next(item for item in prepared["resultados"] if item["issue_iid"] == 7)
        self.assertEqual(story7["requerimientos"], central["resultados"][1]["requerimientos"])

    def test_missing_iid_is_not_associated_arbitrarily(self):
        central = central_fixture(order=(6,))
        central["resultados"][0].pop("issue_iid")
        prepared = parsed_prepared(central, [ISSUES[6]])
        self.assertEqual(prepared["resultados"][0]["requerimientos"], central["resultados"][0]["requerimientos"])

    def test_rnf_do_not_increase_mc01_universe(self):
        story6 = next(item for item in parsed_prepared()["resultados"] if item["issue_iid"] == 6)
        functional = [item["nombre"] for item in story6["requerimientos"] if item["tipo"] == "RF"]
        all_requirements = [item["nombre"] for item in story6["requerimientos"]]
        quality = {
            "issue_iid": 6,
            "metricas": {
                "cobertura_funcional": {
                    "funciones_especificadas": all_requirements,
                    "funciones_incluidas": all_requirements,
                    "funciones_faltantes": [],
                },
                "adecuacion_funcional": {
                    "funciones_evaluables": all_requirements,
                    "funciones_alineadas": all_requirements,
                    "funciones_no_alineadas": [],
                },
            },
        }
        context = copy.deepcopy(ISSUES[6])
        context["requerimientos_preparados"] = story6["requerimientos"]
        result = completar_resultado_calidad(quality, context)
        mc01 = result["metricas"]["cobertura_funcional"]
        mc02 = result["metricas"]["adecuacion_funcional"]
        self.assertEqual(len(mc01["funciones_especificadas"]), 3)
        self.assertEqual(mc02["funciones_evaluables"], mc01["funciones_especificadas"])
        self.assertEqual(mc01["valor"], 1.0)
        self.assertEqual(mc02["valor"], 1.0)

    def test_security_prepares_canonical_data_without_quality_preparation(self):
        source = inspect.getsource(nodo_seguridad)
        self.assertIn('analizar_respuesta_lote(state["central_init"]', source)
        self.assertIn("datos_canonicos_identificados", source)
        self.assertNotIn("preparar_entrada_calidad", source)

    def test_quality_prepares_copy_before_agent_invocation(self):
        source = inspect.getsource(nodo_calidad)
        preparation = source.index("preparar_entrada_calidad")
        invocation = source.index("analizar_calidad(req_text)")
        self.assertLess(preparation, invocation)

    def test_audit_is_sanitized(self):
        central = central_fixture(order=(6,))
        with patch("core.graph.registrar_evento_grafo") as audit:
            preparar_entrada_calidad(json.dumps(central, ensure_ascii=False), [ISSUES[6]])
        _, kwargs = audit.call_args
        self.assertEqual(set(kwargs), {
            "expected_stories", "found_stories", "requirements_before", "requirements_after",
            "rf_before", "rnf_before", "rf_after", "rnf_after",
            "mc01_functional_universe", "mc02_evaluable_universe", "processed_issue_iids",
            "by_issue",
        })
        self.assertEqual(kwargs["by_issue"][0]["issue_iid"], 6)
        self.assertNotIn("descripcion", json.dumps(kwargs["by_issue"], ensure_ascii=False))

    def test_observed_hu006_output_is_corrected_before_quality(self):
        issue = {
            "id": 6, "historia_id": "HU-006", "actor": "Paciente",
            "funcionalidad": "Consultar horarios disponibles",
            "criterios_aceptacion": [
                "Mostrar únicamente horarios disponibles.",
                "Mostrar nombre y especialidad del médico.",
                "Actualizar la disponibilidad después de programar una cita.",
            ],
            "restricciones": ["La información de disponibilidad deberá mostrarse en tiempo real."],
            "observaciones": "La consulta debe responder en menos de tres segundos.",
            "prioridad": "Alta",
        }
        raw = {
            "agente": "central", "milestone": "Fixture", "resultados": [{
                "issue_iid": 6, "historia_id": "HU-006", "actor": "Paciente",
                "objetivo": "Programar una cita sin conflictos.",
                "requerimientos": [
                    {
                        "nombre": "Consulta Horarios Disponibles", "tipo": "RNF",
                        "descripcion_formal": "El sistema deberá mostrar únicamente horarios disponibles.",
                        "procedencia": "explícita — restricción",
                        "origen": "El tiempo de respuesta deberá ser menor a tres segundos.",
                    },
                    {
                        "nombre": "Mostrar Nombre y Especialidad", "tipo": "RF",
                        "descripcion_formal": "El sistema deberá mostrar nombre y especialidad del médico.",
                    },
                    {
                        "nombre": "Actualizar Disponibilidad", "tipo": "RF",
                        "descripcion_formal": "El sistema deberá actualizar la disponibilidad después del paciente haber programado una cita.",
                    },
                ],
            }],
        }
        prepared = parsed_prepared(raw, [issue])["resultados"][0]["requerimientos"]
        self.assertEqual(len(prepared), 6)
        self.assertEqual(sum(item["tipo"] == "RF" for item in prepared), 4)
        self.assertEqual(sum(item["tipo"] == "RNF" for item in prepared), 2)
        consultation = next(item for item in prepared if "Consulta Horarios" in item["nombre"])
        self.assertEqual(consultation["tipo"], "RF")
        self.assertEqual(consultation["procedencia"], "explícita — funcionalidad")
        response_time = next(item for item in prepared if item["nombre"] == "Tiempo de respuesta de la consulta")
        self.assertIn("tres segundos", response_time["descripcion_formal"])
        self.assertEqual(response_time["procedencia"], "explícita — observación")
        update = next(item for item in prepared if item["nombre"] == "Actualizar Disponibilidad")
        self.assertIn("después de que el paciente programe", update["descripcion_formal"])

    def test_cp1252_summary_uses_ascii_escaping(self):
        payload = {
            "clasificación": "Nombre → PERSONAL", "mc01": {"A": 0, "B": 3},
            "veredicto": "APROBADO", "auditoria": {"fallbacks": 0},
        }
        with tempfile.TemporaryDirectory() as directory:
            raw = io.BytesIO()
            stream = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")
            with patch.dict(os.environ, {"TEMP": directory}):
                path = _persist_and_print_summary(payload, prefix="test-summary", stream=stream)
            stream.flush()
            printed = raw.getvalue().decode("cp1252")
            self.assertIn(r"\u2192", printed)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["resumen_json_temporal"], str(path))
            self.assertEqual(json.loads(printed), persisted)
            self.assertEqual({k: persisted[k] for k in payload}, payload)

    def test_hu006_quality_variants_reconcile_to_canonical_rf(self):
        requirements = [
            {"nombre": "Consulta Horarios Disponibles", "tipo": "RF", "descripcion_formal": "El sistema deberá mostrar los horarios disponibles.", "origen": "Consultar horarios disponibles"},
            {"nombre": "Mostrar Nombre y Especialidad del Médico", "tipo": "RF", "descripcion_formal": "El sistema deberá mostrar el nombre y la especialidad del médico.", "origen": "Mostrar nombre y especialidad del médico"},
            {"nombre": "Actualizar Disponibilidad de Horarios", "tipo": "RF", "descripcion_formal": "El sistema deberá actualizar la disponibilidad después de programar una cita.", "origen": "Actualizar la disponibilidad después de programar una cita"},
            {"nombre": "Tiempo de respuesta", "tipo": "RNF", "descripcion_formal": "El sistema deberá responder en menos de tres segundos."},
            {"nombre": "Información en tiempo real", "tipo": "RNF", "descripcion_formal": "El sistema deberá mostrar información en tiempo real."},
        ]
        variants = [
            "Mostrar los horarios disponibles",
            "Visualizar el nombre y la especialidad del médico",
            "Actualizar la disponibilidad después de programar una cita",
        ]
        item = {
            "metricas": {
                "cobertura_funcional": {
                    "funciones_especificadas": variants + ["Información en tiempo real"],
                    "funciones_incluidas": variants + ["Tiempo de respuesta"],
                    "funciones_faltantes": [],
                    "recomendacion": "Incorporar o aclarar funciones.",
                },
                "adecuacion_funcional": {
                    "funciones_evaluables": variants,
                    "funciones_alineadas": variants + ["Información en tiempo real"],
                    "funciones_no_alineadas": [],
                    "recomendacion": "Alinear funciones.",
                },
            },
        }
        context = {
            "objetivo": "Programar una cita sin conflictos.",
            "funcionalidad": "Consultar horarios disponibles",
            "criterios_aceptacion": [
                "Mostrar nombre y especialidad del médico",
                "Actualizar la disponibilidad después de programar una cita",
            ],
            "requerimientos_preparados": requirements,
        }
        result = completar_resultado_calidad(item, context)
        mc01 = result["metricas"]["cobertura_funcional"]
        mc02 = result["metricas"]["adecuacion_funcional"]
        canonical = [requirement["nombre"] for requirement in requirements[:3]]
        self.assertEqual(mc01["funciones_especificadas"], canonical)
        self.assertEqual(mc01["funciones_incluidas"], canonical)
        self.assertEqual(mc01["funciones_faltantes"], [])
        self.assertEqual(mc01["valor"], 1.0)
        self.assertEqual(mc02["funciones_evaluables"], canonical)
        self.assertEqual(mc02["funciones_alineadas"], canonical)
        self.assertEqual(mc02["funciones_no_alineadas"], [])
        self.assertEqual(mc02["valor"], 1.0)
        self.assertEqual(result["recomendaciones"], [])

    def test_missing_or_different_action_remains_missing(self):
        requirements = [
            {"nombre": "Consultar inventario", "tipo": "RF", "origen": "Consultar inventario"},
            {"nombre": "Registrar solicitud", "tipo": "RF", "origen": "Registrar solicitud"},
            {"nombre": "Generar factura", "tipo": "RF", "origen": "Generar factura"},
        ]
        item = {"metricas": {
            "cobertura_funcional": {
                "funciones_especificadas": [x["nombre"] for x in requirements],
                "funciones_incluidas": ["Actualizar inventario", "Eliminar solicitud"],
                "funciones_faltantes": ["Generar factura"],
            },
            "adecuacion_funcional": {
                "funciones_evaluables": [], "funciones_alineadas": ["Pagar factura"],
                "funciones_no_alineadas": [],
            },
        }}
        result = completar_resultado_calidad(item, {"requerimientos_preparados": requirements})
        mc01 = result["metricas"]["cobertura_funcional"]
        self.assertEqual(mc01["funciones_incluidas"], [])
        self.assertEqual(len(mc01["funciones_faltantes"]), 3)
        self.assertTrue(result["recomendaciones"])

    def test_functional_signatures_explain_observed_variants(self):
        self.assertEqual(_firma_funcional("Consulta Horarios Disponibles")[0], "consultar")
        self.assertEqual(_firma_funcional("Mostrar los horarios disponibles")[0], "consultar")
        self.assertEqual(_firma_funcional("Visualizar el nombre y la especialidad")[0], "consultar")
        self.assertTrue(funciones_equivalentes("Consulta de calificaciones", "Mostrar las calificaciones del estudiante"))
        self.assertTrue(funciones_equivalentes("Registro de solicitudes de vacaciones", "Registrar una solicitud de vacaciones"))
        self.assertFalse(funciones_equivalentes("Mostrar nombre", "Modificar nombre"))

    def test_formal_descriptions_avoid_concatenation_and_preserve_timing(self):
        self.assertEqual(
            _descripcion_requerimiento_explicito("Mostrar nombre y especialidad del médico"),
            "El sistema deberá mostrar el nombre y la especialidad del médico.",
        )
        for phrase in ("Mostrar nombre", "Consultar número", "Registrar nombre", "Actualizar nombre"):
            description = _descripcion_requerimiento_explicito(phrase)
            self.assertNotRegex(description, r"(?:mostrar|consultar|registrar|actualizar)(?:nombre|número)")
        self.assertEqual(
            _descripcion_requerimiento_explicito("El tiempo de respuesta deberá ser menor a tres segundos"),
            "El sistema deberá responder a la consulta en menos de tres segundos.",
        )
        self.assertEqual(
            _descripcion_requerimiento_explicito("La operación debe completarse en un máximo de cinco segundos"),
            "El sistema deberá completar la operación en un máximo de cinco segundos.",
        )
        self.assertEqual(
            _descripcion_requerimiento_explicito("El procesamiento debe finalizar dentro de dos segundos"),
            "El sistema deberá finalizar el procesamiento dentro de dos segundos.",
        )

    def test_presentation_adds_article_to_coordinated_nouns(self):
        from core.batch_contract import normalizar_capitalizacion_requerimiento
        self.assertEqual(
            normalizar_capitalizacion_requerimiento(
                "El sistema deberá mostrar el nombre y especialidad del médico."
            ),
            "El sistema deberá mostrar el nombre y la especialidad del médico.",
        )


if __name__ == "__main__":
    unittest.main()
