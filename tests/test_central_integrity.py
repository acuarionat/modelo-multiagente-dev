import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.central_agent import _normalizar_respuesta_central, procesar_central_en_sublotes
from core.graph import CentralIncompleteBatchError, nodo_central_inicial
from core.performance_audit import obtener_contadores, reiniciar_contadores


def issue(iid):
    return {"id": iid, "historia_id": f"HU-{iid:03d}", "actor": "Actor", "objetivo": "Objetivo", "seguridad": {}}


def central_result(iid, historia_id=None):
    return {
        "issue_iid": iid, "historia_id": historia_id or f"HU-{iid:03d}",
        "actor": "Actor", "objetivo": "Objetivo", "requerimientos": [{
            "nombre": "Acción", "descripcion_formal": "El sistema deberá ejecutar la acción.",
            "tipo": "RF", "procedencia": "explícita — funcionalidad",
        }],
    }


class CentralIntegrityTests(unittest.TestCase):
    def setUp(self):
        reiniciar_contadores()
        self.issues = [issue(iid) for iid in (6, 7, 8, 9, 10)]

    def test_supported_individual_repair_shapes(self):
        shapes = (
            {"agente": "central", "resultados": [central_result(7)]},
            central_result(7),
            {"resultado": central_result(7)},
        )
        for raw in shapes:
            with self.subTest(raw=raw):
                parsed, _ = _normalizar_respuesta_central(json.dumps(raw))
                self.assertEqual(parsed["resultados"][0]["issue_iid"], 7)

    def test_non_associable_repair_shapes_remain_missing(self):
        repairs = (
            {"agente": "central"}, {"resultados": [central_result(8)]},
            {"resultados": [{"historia_id": "HU-007"}]},
            {"resultados": [central_result(7, "HU-008")]},
        )
        for repair in repairs:
            calls = 0
            def invoke(*_):
                nonlocal calls
                calls += 1
                return json.dumps({"resultados": []} if calls == 1 else repair)
            parsed, audit = procesar_central_en_sublotes("P", [issue(7)], "C", invoke=invoke)
            self.assertEqual(parsed["resultados"], [])
            self.assertEqual(audit["summary"]["incomplete_issue_ids"], [7])

    def test_observed_four_of_five_case_has_stable_missing_audit(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            if ids == [6, 7]:
                return json.dumps({"resultados": [central_result(6)]})
            if ids == [7]:
                return json.dumps({"resultados": []})
            return json.dumps({"resultados": [central_result(iid) for iid in ids]})
        parsed, _ = procesar_central_en_sublotes("P", self.issues, "C", batch_size=2, invoke=invoke)
        self.assertEqual([item["issue_iid"] for item in parsed["resultados"]], [6, 8, 9, 10])
        partial = obtener_contadores()["resumen_parcial_central"]
        self.assertEqual(partial["expected"], [6, 7, 8, 9, 10])
        self.assertEqual(partial["received"], [6, 8, 9, 10])
        self.assertEqual(partial["missing"], [7])
        self.assertEqual(partial["incomplete"], [7])
        self.assertEqual(partial["status"], "failed")
        self.assertEqual(calls, [[6, 7], [7], [8, 9], [10]])
        reasons = obtener_contadores()["motivos_reparacion"]["Central_Init_Batch"]
        self.assertEqual(reasons, [{"issue_ids": [7], "motivo": "HISTORIA_AUSENTE_EN_RESULTADOS"}])

    def test_node_blocks_and_persists_before_quality(self):
        parsed = {"agente": "central", "resultados": [central_result(iid) for iid in (6, 8, 9, 10)]}
        audit = {"records": [{"sub_batch": 2, "status": "partial", "selective_repair": True, "elapsed_seconds": 1.25}]}
        state = {"project_name": "P", "sprint_context": "C", "issues_data": self.issues, "validation_errors": [], "content_validation_errors": {}}
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"TEMP": directory}), patch("core.graph.procesar_central_en_sublotes", return_value=(parsed, audit)):
            with self.assertRaises(CentralIncompleteBatchError) as raised:
                nodo_central_inicial(state)
            error = raised.exception
            summary = json.loads(Path(error.summary_path).read_text(encoding="utf-8"))
        self.assertEqual(error.missing_issue_ids, [7])
        self.assertEqual(summary["error_category"], "CENTRAL_INCOMPLETE_BATCH")
        self.assertEqual(summary["stage_reached"], "central_validation")
        self.assertFalse(summary["downstream_agents_executed"])
        self.assertFalse(summary["documents_generated"])
        self.assertEqual(summary["artefactos"], {})
        self.assertIn("HU-007", str(error))

    def test_successful_repair_preserves_all_five_in_order(self):
        calls = 0
        def invoke(project, payload, context):
            nonlocal calls
            ids = [item["id"] for item in json.loads(payload)]
            calls += 1
            if calls == 1:
                return json.dumps({"resultados": [central_result(6)]})
            if ids == [7]:
                return json.dumps(central_result(7))
            return json.dumps({"resultados": [central_result(iid) for iid in ids]})
        parsed, _ = procesar_central_en_sublotes("P", self.issues, "C", batch_size=2, invoke=invoke)
        self.assertEqual([item["issue_iid"] for item in parsed["resultados"]], [6, 7, 8, 9, 10])
        partial = obtener_contadores()["resumen_parcial_central"]
        self.assertEqual(partial["missing"], [])
        self.assertEqual(partial["status"], "success")


if __name__ == "__main__":
    unittest.main()
