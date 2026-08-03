import copy
import unittest

from scripts.test_remote_agents import diagnosticar_contrato_calidad


def quality_fixture():
    return {
        "agente": "calidad",
        "resultados": [{
            "issue_iid": 10,
            "historia_id": "HU-010",
            "metricas": {
                "cobertura_funcional": {
                    "funciones_especificadas": ["funcion"],
                    "funciones_incluidas": ["funcion"],
                    "funciones_faltantes": ["faltante"],
                    "justificacion": "Justificacion especifica.",
                    "recomendacion": "Recomendacion especifica.",
                },
                "adecuacion_funcional": {
                    "objetivo_evaluado": "Objetivo",
                    "funciones_evaluables": ["funcion"],
                    "funciones_alineadas": ["funcion"],
                    "funciones_no_alineadas": ["no alineada"],
                    "justificacion": "Justificacion especifica diferente.",
                    "recomendacion": "Recomendacion especifica.",
                },
            },
        }],
    }


class QualityContractDiagnosticTests(unittest.TestCase):
    def test_complete_contract_with_nonempty_lists(self):
        result = diagnosticar_contrato_calidad(quality_fixture())
        self.assertTrue(result["completo"])
        self.assertEqual(result["estructura"], "actual")

    def test_empty_missing_functions_is_valid(self):
        fixture = quality_fixture()
        fixture["resultados"][0]["metricas"]["cobertura_funcional"]["funciones_faltantes"] = []
        result = diagnosticar_contrato_calidad(fixture)
        self.assertTrue(result["completo"])
        self.assertTrue(result["mc01"]["funciones_faltantes"]["vacio_valido"])

    def test_empty_unaligned_functions_is_valid(self):
        fixture = quality_fixture()
        fixture["resultados"][0]["metricas"]["adecuacion_funcional"]["funciones_no_alineadas"] = []
        result = diagnosticar_contrato_calidad(fixture)
        self.assertTrue(result["completo"])
        self.assertTrue(result["mc02"]["funciones_no_alineadas"]["vacio_valido"])

    def test_missing_field_reports_path(self):
        fixture = quality_fixture()
        del fixture["resultados"][0]["metricas"]["cobertura_funcional"]["justificacion"]
        result = diagnosticar_contrato_calidad(fixture)
        self.assertFalse(result["completo"])
        self.assertIn("resultados[0].metricas.cobertura_funcional.justificacion", result["campos_faltantes"])

    def test_wrong_type_is_sanitized(self):
        fixture = quality_fixture()
        fixture["resultados"][0]["metricas"]["cobertura_funcional"]["funciones_incluidas"] = "incorrecto"
        result = diagnosticar_contrato_calidad(fixture)
        self.assertFalse(result["completo"])
        self.assertIn({
            "ruta": "resultados[0].metricas.cobertura_funcional.funciones_incluidas",
            "tipo_esperado": "list",
            "tipo_recibido": "str",
        }, result["tipos_invalidos"])

    def test_old_key_is_reported_but_not_accepted(self):
        fixture = quality_fixture()
        metrics = fixture["resultados"][0]["metricas"]
        metrics["mc01"] = metrics.pop("cobertura_funcional")
        result = diagnosticar_contrato_calidad(fixture)
        self.assertFalse(result["completo"])
        self.assertEqual(result["estructura"], "antigua_o_alias")
        self.assertEqual(result["aliases_detectados"][0]["ruta"], "resultados[0].metricas.mc01")

    def test_missing_issue_iid_is_not_invented(self):
        fixture = quality_fixture()
        del fixture["resultados"][0]["issue_iid"]
        result = diagnosticar_contrato_calidad(fixture)
        self.assertFalse(result["completo"])
        self.assertIn("resultados[0].issue_iid", result["campos_faltantes"])

    def test_results_object_instead_of_list(self):
        fixture = quality_fixture()
        fixture["resultados"] = copy.deepcopy(fixture["resultados"][0])
        result = diagnosticar_contrato_calidad(fixture)
        self.assertFalse(result["completo"])
        self.assertIn({
            "ruta": "resultados",
            "tipo_esperado": "list",
            "tipo_recibido": "dict",
        }, result["tipos_invalidos"])

    def test_downstream_index_rule_is_reported_separately(self):
        result = diagnosticar_contrato_calidad(quality_fixture())
        self.assertTrue(result["completo"])
        self.assertFalse(result["validacion_productiva"]["aprobada"])
        self.assertEqual(
            result["validacion_productiva"]["reglas_fallidas"],
            ["indice requerido antes del calculo Python"],
        )


if __name__ == "__main__":
    unittest.main()
