import copy
import unittest

from core.batch_contract import normalizar_metricas_resultado


def quality(a, b, aligned, evaluable):
    item = {"metricas": {
        "cobertura_funcional": {
            "funciones_especificadas": [f"F{i}" for i in range(b)],
            "funciones_incluidas": [f"F{i}" for i in range(max(0, b - a))],
            "funciones_faltantes": [f"F{i}" for i in range(max(0, b - a), b)]
            + ([f"Fuera{i}" for i in range(a - b)] if a > b else []),
            "justificacion": "Comparación explícita entre funciones especificadas y formalizadas.",
            "recomendacion": "Incorporar las funciones faltantes." if a else "",
        },
        "adecuacion_funcional": {
            "objetivo_evaluado": "Atender la necesidad declarada.",
            "funciones_evaluables": [f"F{i}" for i in range(evaluable)],
            "funciones_alineadas_detalle": [f"F{i}" for i in range(aligned)],
            "funciones_no_alineadas": [f"F{i}" for i in range(aligned, evaluable)],
            "funciones_ambiguas": [],
            "justificacion": "La contribución de cada función fue contrastada con el objetivo.",
            "recomendacion": "Vincular las funciones no alineadas con el objetivo." if aligned < evaluable else "",
        },
    }}
    return normalizar_metricas_resultado(item, "Calidad")


def security(documented, applicable, classified, identified, lot="LoT-2"):
    item = {"lot": lot, "metricas": {
        "cobertura_seguridad": {
            "aspectos_aplicables": [f"A{i}" for i in range(applicable)],
            "aspectos_documentados": [f"A{i}" for i in range(documented)],
            "aspectos_parciales": [],
            "aspectos_faltantes": [f"A{i}" for i in range(documented, applicable)],
            "aspectos_inferidos": [],
            "justificacion": "Cada aspecto se contrastó con evidencia explícita.",
            "recomendacion": "Documentar los aspectos faltantes." if documented < applicable else "",
        },
        "clasificacion_datos": {
            "datos_identificados_detalle": [f"D{i}" for i in range(identified)],
            "datos_clasificados_detalle": [
                {"dato": f"D{i}", "clasificacion": "Personal"} for i in range(classified)
            ],
            "datos_sin_clasificacion": [f"D{i}" for i in range(classified, identified)],
            "clasificaciones_inferidas": [],
            "justificacion": "Cada dato se contrastó con una clasificación explícita.",
            "recomendacion": "Clasificar los datos pendientes." if classified < identified else "",
        },
    }}
    return normalizar_metricas_resultado(item, "Seguridad")


class RequirementsMetricsTests(unittest.TestCase):
    def test_mc01_required_cases(self):
        self.assertEqual(quality(0, 5, 5, 5)["metricas"]["cobertura_funcional"]["valor"], 1.0)
        self.assertEqual(quality(1, 5, 4, 5)["metricas"]["cobertura_funcional"]["valor"], 0.8)
        self.assertEqual(quality(5, 5, 0, 5)["metricas"]["cobertura_funcional"]["valor"], 0.0)
        invalid = quality(6, 5, 0, 5)["metricas"]["cobertura_funcional"]
        self.assertEqual(invalid["estado_calculo"], "No evaluado")
        self.assertTrue(invalid["errores_validacion"])
        self.assertEqual(quality(0, 0, 0, 0)["metricas"]["cobertura_funcional"]["estado_calculo"], "No aplica")

    def test_mc02_required_cases(self):
        self.assertEqual(quality(0, 5, 5, 5)["metricas"]["adecuacion_funcional"]["valor"], 1.0)
        self.assertEqual(quality(0, 5, 4, 5)["metricas"]["adecuacion_funcional"]["valor"], 0.8)
        invalid = quality(0, 5, 6, 5)["metricas"]["adecuacion_funcional"]
        self.assertEqual(invalid["estado_calculo"], "No evaluado")
        self.assertEqual(quality(0, 5, 0, 0)["metricas"]["adecuacion_funcional"]["estado_calculo"], "No aplica")

    def test_ms01_and_ms02_required_cases(self):
        self.assertEqual(security(4, 4, 4, 4)["metricas"]["cobertura_seguridad"]["valor"], 1.0)
        self.assertEqual(security(3, 4, 3, 4)["metricas"]["cobertura_seguridad"]["valor"], 0.75)
        self.assertEqual(security(3, 4, 3, 4)["metricas"]["clasificacion_datos"]["valor"], 0.75)
        self.assertEqual(security(4, 4, 4, 4)["metricas"]["clasificacion_datos"]["valor"], 1.0)
        self.assertEqual(security(0, 0, 0, 0)["metricas"]["cobertura_seguridad"]["estado_calculo"], "No aplica")
        self.assertEqual(security(0, 0, 0, 0)["metricas"]["clasificacion_datos"]["estado_calculo"], "No aplica")
        self.assertEqual(security(5, 4, 3, 4)["metricas"]["cobertura_seguridad"]["estado_calculo"], "No evaluado")
        self.assertEqual(security(3, 4, 5, 4)["metricas"]["clasificacion_datos"]["estado_calculo"], "No evaluado")

    def test_quality_indicator_policy(self):
        exact = quality(1, 20, 19, 20)["indicador"]
        self.assertEqual(exact["valor"], 0.95)
        self.assertEqual(exact["estado"], "Cumple")
        indicator = quality(0, 5, 4, 5)["indicador"]
        self.assertEqual(indicator["valor"], 0.9)
        self.assertEqual(indicator["estado"], "No cumple")
        self.assertEqual(quality(0, 0, 0, 0)["indicador"]["estado"], "No evaluado")

    def test_security_indicator_lot_thresholds(self):
        self.assertEqual(security(9, 10, 9, 10, "LoT-2")["indicador"]["estado"], "Cumple")
        self.assertEqual(security(9, 10, 9, 10, "LoT-3")["indicador"]["estado"], "No cumple")
        self.assertEqual(security(19, 20, 19, 20, "LoT-3")["indicador"]["estado"], "Cumple")
        self.assertEqual(security(9, 10, 9, 10, "")["indicador"]["estado"], "No evaluado")

    def test_normalization_is_idempotent_for_ui_and_pdf(self):
        report = quality(1, 5, 4, 5)
        first = copy.deepcopy(report)
        normalizar_metricas_resultado(report, "Calidad")
        self.assertEqual(report["metricas"], first["metricas"])
        self.assertEqual(report["indicador"], first["indicador"])
        historical = {"metricas": {"controles_seguridad": {}, "lot_asignado": {"lot_recomendado": "LoT-2"}}}
        normalizar_metricas_resultado(historical, "Seguridad")
        first = copy.deepcopy(historical)
        normalizar_metricas_resultado(historical, "Seguridad")
        self.assertEqual(historical["metricas"], first["metricas"])
        self.assertEqual(historical["indicador"], first["indicador"])


if __name__ == "__main__":
    unittest.main()
