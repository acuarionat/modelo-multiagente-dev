import json
import unittest

from core.batch_contract import (
    consolidate_batch, parse_batch_response, reconcile_issue_ids,
    validate_batch_response,
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


if __name__ == "__main__":
    unittest.main()
