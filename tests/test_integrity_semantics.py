import json
import unittest
from unittest.mock import patch

from core.batch_contract import consolidar_lote
from core.graph import _resultado_agente_no_evaluable, _separar_errores_centrales, nodo_central_inicial
from integrations.issue_mapper import separar_entradas_para_analisis


def source(iid, state="entrada_valida", missing=None):
    return {
        "id": str(iid), "historia_id": f"HU-{iid:03d}", "titulo": f"Historia {iid}",
        "actor": "Operador", "funcionalidad": "Registrar solicitud", "objetivo": "Gestionar solicitudes",
        "criterios_aceptacion": [], "restricciones": [], "observaciones": "", "seguridad": {},
        "validacion_entrada": {"estado": state, "campos_faltantes": missing or [], "advertencias": []},
    }


def central(iid, status=None):
    item = {
        "issue_iid": iid, "historia_id": f"HU-{iid:03d}", "actor": "Operador",
        "objetivo": "Gestionar solicitudes", "requerimientos": [],
    }
    if status:
        item["status"] = status
    return item


def report(iid, index=None):
    return {"issue_iid": iid, "indice": index, "estado_medicion": "evidencia_insuficiente", "metricas": {}}


class IntegritySemanticsTests(unittest.TestCase):
    def test_five_inputs_remain_processable_regardless_of_documentary_state(self):
        items = [source(i) for i in range(1, 6)]
        items[1]["validacion_entrada"]["estado"] = "informacion_insuficiente"
        processable, insufficient = separar_entradas_para_analisis(items)
        self.assertEqual([x["id"] for x in processable], ["1", "2", "3", "4", "5"])
        self.assertEqual([x["id"] for x in insufficient], ["2"])

    def test_missing_criteria_and_security_are_not_integrity_failures(self):
        issues = [source(21, "entrada_con_advertencias")]
        parsed = {"agente": "central", "resultados": [central(21)]}
        state = {"project_name": "Otro dominio", "sprint_context": "", "issues_data": issues}
        with patch("core.graph.procesar_central_en_sublotes", return_value=(parsed, {"records": []})):
            result = nodo_central_inicial(state)
        item = json.loads(result["central_init"])["resultados"][0]
        self.assertEqual(item["status"], "ok")
        self.assertTrue(item["evaluacion_posterior_posible"])

    def test_insufficient_identified_story_continues_with_traceability(self):
        issues = [source(22, "informacion_insuficiente", ["descripcion"])]
        parsed = {"agente": "central", "resultados": [central(22)]}
        state = {"project_name": "Otro dominio", "sprint_context": "", "issues_data": issues}
        with patch("core.graph.procesar_central_en_sublotes", return_value=(parsed, {"records": []})):
            result = nodo_central_inicial(state)
        item = json.loads(result["central_init"])["resultados"][0]
        self.assertEqual(item["status"], "informacion_insuficiente")
        self.assertEqual(item["campos_ausentes"], ["descripcion"])
        self.assertTrue(item["evaluacion_posterior_posible"])

    def test_identifiable_individual_error_is_retained(self):
        issues = [source(23)]
        parsed = {"agente": "central", "resultados": [central(23, "error")]}
        state = {"project_name": "Otro dominio", "sprint_context": "", "issues_data": issues}
        with patch("core.graph.procesar_central_en_sublotes", return_value=(parsed, {"records": []})):
            result = nodo_central_inicial(state)
        item = json.loads(result["central_init"])["resultados"][0]
        self.assertEqual(item["status"], "error")
        self.assertFalse(item["evaluacion_posterior_posible"])
        self.assertEqual(item["motivo_sanitizado"], "ESTRUCTURA_CENTRAL_INSUFICIENTE")

    def test_individual_error_is_not_sent_as_analyzable_input(self):
        payload = {"agente": "central", "resultados": [central(23, "error"), central(24, "informacion_insuficiente")]}
        active, errors = _separar_errores_centrales(json.dumps(payload))
        self.assertEqual([x["issue_iid"] for x in json.loads(active)["resultados"]], [24])
        self.assertEqual([x["issue_iid"] for x in errors], [23])
        placeholder = _resultado_agente_no_evaluable(23, "Calidad")
        self.assertIsNone(placeholder["indice"])
        self.assertEqual(placeholder["estado_medicion"], "no_evaluable")

    def test_consolidation_keeps_insufficient_and_excludes_null_metrics_from_average(self):
        iid = 24
        result = consolidar_lote(
            {iid}, {"resultados": [central(iid, "informacion_insuficiente")]},
            {"resultados": [report(iid)]}, {"resultados": [report(iid)]},
            {"resultados": [{"issue_iid": iid, "veredicto": "CORREGIR"}]},
            input_validations={iid: {"estado": "informacion_insuficiente", "campos_faltantes": ["objetivo"]}},
        )
        item = result["resultados"][0]
        summary = result["resumen_global"]
        self.assertEqual(item["status"], "informacion_insuficiente")
        self.assertEqual(item["estado_evaluacion"], "REVISIÓN REQUERIDA")
        self.assertEqual(summary["historias_procesadas"], 1)
        self.assertEqual(summary["historias_evaluables_calidad"], 0)
        self.assertIsNone(summary["calidad_promedio"])

    def test_ambiguous_non_evaluable_story_requires_review(self):
        iid = 25
        final = consolidar_lote(
            {iid}, {"resultados": [central(iid)]}, {"resultados": [report(iid)]},
            {"resultados": [report(iid)]}, {"resultados": [{"issue_iid": iid, "veredicto": "ALERTA"}]},
            input_validations={iid: {"estado": "entrada_con_advertencias", "advertencias": ["redacción ambigua"]}},
        )
        self.assertEqual(final["resultados"][0]["estado_evaluacion"], "REVISIÓN REQUERIDA")

    def test_all_expected_identifiers_are_present_in_final_consolidation(self):
        ids = {31, 32, 33, 34, 35}
        central_results = [central(i) for i in ids]
        quality = [dict(report(i, 1.0), estado_medicion="evaluable") for i in ids]
        security = [dict(report(i, 1.0), estado_medicion="evaluable") for i in ids]
        evaluations = [{"issue_iid": i, "veredicto": "APROBADO"} for i in ids]
        final = consolidar_lote(ids, {"resultados": central_results}, {"resultados": quality}, {"resultados": security}, {"resultados": evaluations})
        self.assertEqual({x["issue_iid"] for x in final["resultados"]}, ids)


if __name__ == "__main__":
    unittest.main()
