import unittest

from core.batch_contract import (
    completar_resultado_calidad,
    completar_resultado_seguridad,
)


def fixture_calidad(especificadas=2, faltantes=0, evaluables=2, alineadas=2):
    return {
        "issue_iid": 7,
        "historia_id": "HU-002",
        "metricas": {
            "cobertura_funcional": {
                "funciones_especificadas": [f"FE-{i}" for i in range(especificadas)],
                "funciones_incluidas": [f"FI-{i}" for i in range(max(especificadas - faltantes, 0))],
                "funciones_faltantes": [f"FF-{i}" for i in range(faltantes)],
                "justificacion": "Evidencia funcional.",
                "recomendacion": "Revisar faltantes." if faltantes else "",
            },
            "adecuacion_funcional": {
                "objetivo_evaluado": "Objetivo de prueba",
                "funciones_evaluables": [f"EV-{i}" for i in range(evaluables)],
                "funciones_alineadas": [f"AL-{i}" for i in range(alineadas)],
                "funciones_no_alineadas": [],
                "justificacion": "Evidencia de alineación.",
                "recomendacion": "",
            },
        },
    }


def fixture_seguridad(aplicables=2, documentados=2, identificados=2, clasificados=2, lot="LoT-2"):
    return {
        "issue_iid": 7,
        "historia_id": "HU-002",
        "lot_recomendado": lot,
        "metricas": {
            "cobertura_seguridad": {
                "aspectos_aplicables": [f"AA-{i}" for i in range(aplicables)],
                "aspectos_documentados": [f"AD-{i}" for i in range(documentados)],
                "aspectos_parciales": [], "aspectos_faltantes": [],
                "aspectos_inferidos": [], "justificacion": "Evidencia de seguridad.",
                "recomendacion": "",
            },
            "clasificacion_datos": {
                "datos_identificados": [f"DI-{i}" for i in range(identificados)],
                "datos_clasificados": [f"DC-{i}" for i in range(clasificados)],
                "datos_sin_clasificacion": [], "clasificaciones_inferidas": [],
                "justificacion": "Evidencia de clasificación.", "recomendacion": "",
            },
        },
    }


class MetricasOficialesTests(unittest.TestCase):
    def test_mc01_mc02_and_quality_indicator(self):
        result = completar_resultado_calidad(
            fixture_calidad(especificadas=4, faltantes=1, evaluables=4, alineadas=3)
        )
        self.assertEqual(result["metricas"]["cobertura_funcional"]["valor"], 0.75)
        self.assertEqual(result["metricas"]["adecuacion_funcional"]["valor"], 0.75)
        self.assertEqual(result["indicador"]["valor"], 0.75)
        self.assertEqual(result["indicador"]["meta"], 0.95)
        self.assertEqual(result["indicador"]["estado"], "No cumple")

    def test_quality_zero_denominator_is_not_applicable(self):
        result = completar_resultado_calidad(
            fixture_calidad(especificadas=0, faltantes=0, evaluables=0, alineadas=0)
        )
        for metric in result["metricas"].values():
            self.assertEqual(metric["estado_calculo"], "No aplica")
            self.assertIsNone(metric["valor"])
            self.assertIsNone(metric["porcentaje"])
        self.assertEqual(result["indicador"]["estado"], "No evaluado")
        self.assertIsNone(result["indice"])

    def test_invalid_quality_value_does_not_feed_indicator(self):
        result = completar_resultado_calidad(
            fixture_calidad(especificadas=1, faltantes=2, evaluables=1, alineadas=1)
        )
        self.assertEqual(
            result["metricas"]["cobertura_funcional"]["estado_calculo"], "No evaluado"
        )
        self.assertIsNone(result["indicador"]["valor"])

    def test_ms01_ms02_and_lot2_indicator(self):
        result = completar_resultado_seguridad(
            fixture_seguridad(aplicables=2, documentados=2, identificados=2, clasificados=1)
        )
        self.assertEqual(result["metricas"]["cobertura_seguridad"]["valor"], 1.0)
        self.assertEqual(result["metricas"]["clasificacion_datos"]["valor"], 0.5)
        self.assertEqual(result["indicador"]["valor"], 0.75)
        self.assertEqual(result["indicador"]["meta"], 0.90)
        self.assertEqual(result["indicador"]["estado"], "No cumple")

    def test_lot3_meta_and_success(self):
        result = completar_resultado_seguridad(fixture_seguridad(lot="LoT-3"))
        self.assertEqual(result["indicador"]["meta"], 0.95)
        self.assertEqual(result["indicador"]["estado"], "Cumple")

    def test_invalid_security_value_does_not_feed_indicator(self):
        result = completar_resultado_seguridad(
            fixture_seguridad(aplicables=1, documentados=2, identificados=0, clasificados=0)
        )
        self.assertEqual(
            result["metricas"]["cobertura_seguridad"]["estado_calculo"], "No evaluado"
        )
        self.assertEqual(
            result["metricas"]["clasificacion_datos"]["estado_calculo"], "No aplica"
        )
        self.assertIsNone(result["indicador"]["valor"])


if __name__ == "__main__":
    unittest.main()
