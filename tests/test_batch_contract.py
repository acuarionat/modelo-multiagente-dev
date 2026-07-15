import json
import unittest

from core.batch_contract import (
    calculate_agent_metrics, calculate_num_predict, collect_recommendations,
    consolidate_batch, parse_batch_response, reconcile_issue_ids,
    validate_agent_content, validate_batch_response,
)


def batch(agent, results):
    return {"agente": agent, "resultados": results}


class BatchContractTests(unittest.TestCase):
    def setUp(self):
        self.central = batch("central", [
            {"issue_iid": 22, "historia_id": "HU-022", "titulo": "B", "actor": "Y", "objetivo": "OB", "requerimientos": [{"id": "RF-001", "tipo": "RF", "nombre": "B1", "descripcion": "DB", "justificacion": "JB", "prioridad": "Alta"}]},
            {"issue_iid": 11, "historia_id": "HU-011", "titulo": "A", "actor": "X", "objetivo": "OA", "requerimientos": [{"id": "RF-001", "tipo": "RF", "nombre": "A1", "descripcion": "DA", "justificacion": "JA", "prioridad": "Media"}]},
        ])
        self.quality = batch("calidad", [
            {"issue_iid": 11, "indice": .9, "metricas": {}, "recomendaciones": []},
            {"issue_iid": 22, "indice": .8, "metricas": {}, "recomendaciones": []},
        ])
        self.security = batch("seguridad", [
            {"issue_iid": 22, "indice": .7, "metricas": {}, "recomendaciones": [], "lot_recomendado": "LoT-2"},
            {"issue_iid": 11, "indice": .6, "metricas": {}, "recomendaciones": [], "lot_recomendado": "LoT-1"},
        ])
        self.evaluation = batch("evaluador", [
            {"issue_iid": 11, "veredicto": "APROBADO", "riesgos_criticos": [], "correcciones_obligatorias": []},
            {"issue_iid": 22, "veredicto": "CORREGIR", "riesgos_criticos": [], "correcciones_obligatorias": ["Corregir"]},
        ])

    def test_contract_rejects_array_root(self):
        with self.assertRaisesRegex(ValueError, "resultados"):
            parse_batch_response(json.dumps([]), "Central")

    def test_consolidates_by_iid_not_position_and_renumbers_globally(self):
        final = consolidate_batch({11, 22}, self.central, self.quality, self.security, self.evaluation)
        first, second = final["resultados"]
        self.assertEqual(first["central"]["titulo"], "A")
        self.assertEqual(first["quality"]["indice"], .9)
        self.assertEqual(second["central"]["titulo"], "B")
        ids = [x["central"]["requerimientos"][0]["id"] for x in final["resultados"]]
        self.assertEqual(ids, ["RF-001", "RF-002"])
        self.assertEqual(sum(len(x["central"]["requerimientos"]) for x in final["resultados"]), 2)

    def test_only_missing_story_is_marked_error(self):
        self.security["resultados"] = [self.security["resultados"][1]]
        errors = validate_batch_response(self.security, {11, 22}, "Seguridad")
        final = consolidate_batch({11, 22}, self.central, self.quality, self.security, self.evaluation, errors)
        self.assertEqual(final["resultados"][0]["status"], "ok")
        self.assertEqual(final["resultados"][1]["status"], "error")
        self.assertEqual(final["resumen_global"]["historias_procesadas"], 1)
        self.assertEqual(final["resumen_global"]["historias_con_error"], 1)

    def test_invalid_index_is_explicit(self):
        self.quality["resultados"][0]["indice"] = 100
        errors = validate_batch_response(self.quality, {11, 22}, "Calidad")
        self.assertTrue(any("índice inválido" in error for error in errors))
        final = consolidate_batch({11, 22}, self.central, self.quality, self.security, self.evaluation, errors)
        self.assertEqual(final["resultados"][0]["status"], "error")

    def test_reconciles_llm_example_ids_to_real_gitlab_iids(self):
        response = batch("central", [
            {"issue_iid": 1, "historia_id": "HU-001", "titulo": "A", "requerimientos": []},
            {"issue_iid": 2, "historia_id": "HU-002", "titulo": "B", "requerimientos": []},
            {"issue_iid": 3, "historia_id": "HU-003", "titulo": "C", "requerimientos": []},
            {"issue_iid": 4, "historia_id": "HU-004", "titulo": "D", "requerimientos": []},
        ])
        notes = reconcile_issue_ids(response, [6, 7, 9, 10], "Central")
        self.assertEqual([x["issue_iid"] for x in response["resultados"]], [6, 7, 9, 10])
        self.assertEqual([x["historia_id"] for x in response["resultados"]], ["HU-006", "HU-007", "HU-009", "HU-010"])
        self.assertEqual(validate_batch_response(response, {6, 7, 9, 10}, "Central"), [])
        self.assertEqual(len(notes), 4)

    def test_quality_math_preserves_specific_evidence(self):
        response = batch("calidad", [{
            "issue_iid": 6,
            "metricas": {
                "cobertura_funcional": {
                    "elementos_evaluados": ["Registrar", "Validar", "Evitar duplicado"],
                    "elementos_con_problemas": ["Corregir rechazo"],
                    "justificacion": "Se evaluaron Registrar, Validar y Evitar duplicado; falta definir Corregir rechazo.",
                    "recomendacion": "Definir cómo corregir un registro rechazado.",
                },
                "adecuacion_funcional": {
                    "elementos_evaluados": ["Registrar", "Validar"],
                    "elementos_alineados": ["Registrar", "Validar"],
                    "elementos_con_problemas": [],
                    "justificacion": "Registrar y Validar contribuyen directamente al objetivo.",
                    "recomendacion": "",
                },
            },
        }])
        calculate_agent_metrics(response, "Calidad")
        item = response["resultados"][0]
        self.assertAlmostEqual(item["metricas"]["cobertura_funcional"]["valor"], 2 / 3)
        self.assertEqual(item["metricas"]["adecuacion_funcional"]["valor"], 1)
        self.assertIn("Corregir rechazo", item["metricas"]["cobertura_funcional"]["justificacion"])
        self.assertEqual(validate_agent_content(response, "Calidad"), {})

    def test_rejects_placeholder_content(self):
        response = batch("central", [{
            "issue_iid": 6,
            "requerimientos": [{
                "temp_id": "RF-TEMP-01", "nombre": "...", "descripcion_formal": "",
                "tipo": "RF", "origen": "N/A", "justificacion": "...", "prioridad": "Alta",
            }],
        }])
        errors = validate_agent_content(response, "Central")
        self.assertIn(6, errors)
        self.assertTrue(any("campos inválidos" in message for message in errors[6]))

    def test_collects_metric_and_evaluator_recommendations(self):
        result = {
            "quality": {"metricas": {"cobertura": {"recomendacion": "Definir corrección."}}},
            "security": {"metricas": {"controles": {"recomendacion": "Agregar auditoría."}}},
            "evaluation": {"correcciones_obligatorias": ["Definir permisos."]},
            "central": {"observaciones": []},
        }
        self.assertEqual(collect_recommendations(result), ["Definir corrección.", "Agregar auditoría.", "Definir permisos."])

    def test_dynamic_output_budget(self):
        self.assertEqual(calculate_num_predict("Central_Init", 5), 1900)
        self.assertEqual(calculate_num_predict("Quality", 5), 1750)
        self.assertEqual(calculate_num_predict("Security", 5), 2000)
        self.assertEqual(calculate_num_predict("Evaluator", 5), 750)

    def test_parser_recovers_json_wrapped_in_markdown(self):
        raw = '```json\n{"agente":"seguridad","resultados":[]}\n```'
        parsed = parse_batch_response(raw, "Seguridad")
        self.assertEqual(parsed["resultados"], [])

    def test_parser_reports_truncated_json(self):
        with self.assertRaisesRegex(ValueError, "truncada"):
            parse_batch_response('{"agente":"seguridad","resultados":[', "Seguridad")


if __name__ == "__main__":
    unittest.main()
