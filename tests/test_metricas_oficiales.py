import unittest
from pathlib import Path

from core.batch_contract import (
    completar_requerimientos_explicitos_faltantes,
    completar_resultado_calidad,
    completar_resultado_seguridad,
    consolidar_lote,
)


def fixture_calidad(especificadas=2, faltantes=0, evaluables=2, alineadas=2):
    specified = [f"F-{i}" for i in range(especificadas)]
    return {
        "issue_iid": 7,
        "historia_id": "HU-002",
        "metricas": {
            "cobertura_funcional": {
                "funciones_especificadas": specified,
                "funciones_incluidas": specified[:max(especificadas - faltantes, 0)],
                "funciones_faltantes": specified[max(especificadas - faltantes, 0):],
                "justificacion": "Evidencia funcional.",
                "recomendacion": "Revisar faltantes." if faltantes else "",
            },
            "adecuacion_funcional": {
                "objetivo_evaluado": "Objetivo de prueba",
                "funciones_evaluables": specified[:evaluables],
                "funciones_alineadas": specified[:alineadas],
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

    def test_quality_missing_functions_are_restricted_to_specified_universe(self):
        result = completar_resultado_calidad(
            fixture_calidad(especificadas=1, faltantes=2, evaluables=1, alineadas=1)
        )
        metric = result["metricas"]["cobertura_funcional"]
        self.assertEqual(metric["funciones_faltantes"], ["F-0"])
        self.assertEqual(metric["valor"], 0.0)

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
        result = completar_resultado_seguridad(
            fixture_seguridad(lot="LoT-3"),
            {"seguridad": {
                "maneja_datos_sensibles": "Sí\nDatos clínicos",
                "autenticacion": "Usuario y contraseña",
                "autorizacion_roles": "Médico",
                "auditoria": "Sí",
            }},
        )
        self.assertEqual(result["indicador"]["meta"], 0.95)
        self.assertEqual(result["indicador"]["estado"], "Cumple")

    def test_mc01_complete_has_coherent_python_justification(self):
        result = completar_resultado_calidad(fixture_calidad())
        metric = result["metricas"]["cobertura_funcional"]
        self.assertEqual(metric["valor"], 1.0)
        self.assertIn("A=2", metric["justificacion"])
        self.assertIn("Faltantes: ninguno", metric["justificacion"])
        self.assertNotIn("no existe cobertura", metric["justificacion"].casefold())

    def test_mc01_is_not_evaluated_when_agent_classifies_no_functions(self):
        fixture = fixture_calidad(especificadas=1)
        mc01 = fixture["metricas"]["cobertura_funcional"]
        mc01["funciones_incluidas"] = []
        mc01["funciones_faltantes"] = []
        metric = completar_resultado_calidad(fixture)["metricas"]["cobertura_funcional"]
        self.assertEqual(metric["estado_calculo"], "No evaluado")
        self.assertIsNone(metric["valor"])

    def test_mc02_complete_uses_same_mc01_universe(self):
        result = completar_resultado_calidad(fixture_calidad(especificadas=2, alineadas=2))
        mc01 = result["metricas"]["cobertura_funcional"]
        mc02 = result["metricas"]["adecuacion_funcional"]
        self.assertEqual(mc02["funciones_evaluables"], mc01["funciones_especificadas"])
        self.assertEqual(mc02["valor"], 1.0)

    def test_hu010_uses_its_real_objective(self):
        result = completar_resultado_calidad(
            fixture_calidad(especificadas=1, alineadas=1),
            {"objetivo": "Liberar el horario reservado"},
        )
        mc02 = result["metricas"]["adecuacion_funcional"]
        self.assertEqual(mc02["objetivo_evaluado"], "Liberar el horario reservado")
        self.assertNotIn("report", mc02["justificacion"].casefold())

    def test_ms01_explicit_auth_role_and_audit_are_documented(self):
        result = completar_resultado_seguridad(fixture_seguridad(), {
            "seguridad": {
                "maneja_datos_sensibles": "Sí\nDatos personales",
                "autenticacion": "Usuario y contraseña",
                "autorizacion_roles": "Paciente",
                "auditoria": "Sí",
            },
        })
        ms01 = result["metricas"]["cobertura_seguridad"]
        self.assertEqual(ms01["valor"], 1.0)
        self.assertEqual(
            ms01["aspectos_documentados"],
            ["Autenticación", "Autorización", "Auditoría"],
        )

    def test_ms02_personal_data_is_classified(self):
        result = completar_resultado_seguridad(fixture_seguridad(), {
            "seguridad": {"maneja_datos_sensibles": "Sí\nDatos personales"},
        })
        ms02 = result["metricas"]["clasificacion_datos"]
        self.assertEqual(ms02["datos_identificados"], ["Datos personales"])
        self.assertEqual(ms02["valor"], 1.0)

    def test_ms02_is_not_applicable_without_identified_data(self):
        result = completar_resultado_seguridad(fixture_seguridad(), {
            "seguridad": {"maneja_datos_sensibles": "No definido"},
        })
        ms02 = result["metricas"]["clasificacion_datos"]
        self.assertEqual(ms02["estado_calculo"], "No aplica")
        self.assertIsNone(ms02["valor"])

    def test_ms02_is_zero_when_identified_data_has_no_classification(self):
        result = completar_resultado_seguridad(fixture_seguridad(), {
            "seguridad": {"maneja_datos_sensibles": "Sí\nCódigo interno"},
        })
        ms02 = result["metricas"]["clasificacion_datos"]
        self.assertEqual(ms02["estado_calculo"], "Calculada")
        self.assertEqual(ms02["valor"], 0.0)

    def test_lot2_is_default_without_explicit_high_impact(self):
        result = completar_resultado_seguridad(fixture_seguridad(lot="LoT-3"), {
            "seguridad": {"maneja_datos_sensibles": "Sí\nDatos personales"},
            "objetivo": "Liberar el horario reservado",
        })
        self.assertEqual(result["lot_recomendado"], "LoT-2")
        self.assertEqual(result["indicador"]["meta"], 0.90)

    def test_explicit_provenance_and_observation_requirements(self):
        requirements = completar_requerimientos_explicitos_faltantes([], {
            "id": "9", "funcionalidad": "Generar reportes",
            "criterios_aceptacion": [], "restricciones": [],
            "observaciones": "Los reportes deben poder imprimirse.",
            "prioridad": None, "seguridad": {},
        })
        observation = next(
            req for req in requirements
            if req["procedencia"] == "explícita — observación"
        )
        self.assertEqual(observation["tipo"], "RF")
        self.assertIn("imprimir", observation["descripcion_formal"])

    def test_requested_observations_and_restrictions_become_rf_or_rnf(self):
        sources = [
            {
                "id": "1", "funcionalidad": "Editar información del paciente",
                "criterios_aceptacion": [],
                "restricciones": ["Tiempo de respuesta menor a 3 segundos"],
                "observaciones": "", "seguridad": {},
            },
            {
                "id": "2", "funcionalidad": "Consultar disponibilidad",
                "criterios_aceptacion": [], "restricciones": [],
                "observaciones": "Actualización en tiempo real", "seguridad": {},
            },
            {
                "id": "3", "funcionalidad": "Generar reportes",
                "criterios_aceptacion": [], "restricciones": [],
                "observaciones": "Los reportes deben poder imprimirse.", "seguridad": {},
            },
        ]
        requirements = [
            req for source in sources
            for req in completar_requerimientos_explicitos_faltantes([], source)
        ]
        by_origin = {req["origen"]: req["tipo"] for req in requirements}
        self.assertEqual(by_origin["Editar información del paciente"], "RF")
        self.assertEqual(by_origin["Tiempo de respuesta menor a 3 segundos"], "RNF")
        self.assertEqual(by_origin["Actualización en tiempo real"], "RNF")
        self.assertEqual(by_origin["Los reportes deben poder imprimirse."], "RF")

    def test_quality_node_does_not_formalize_central_requirements(self):
        graph_source = Path("core/graph.py").read_text(encoding="utf-8")
        quality_node = graph_source.split("def nodo_calidad", 1)[1].split(
            "def nodo_seguridad", 1,
        )[0]
        self.assertNotIn("formalizar_fuentes_explicitas", quality_node)
        self.assertNotIn("completar_requerimientos_explicitos_faltantes", quality_node)

    def test_completion_preserves_central_requirement_and_avoids_duplicate(self):
        original = {
            "funcionalidad": "Generar reportes de citas", "criterios_aceptacion": [],
            "restricciones": [], "observaciones": "Los reportes deben poder imprimirse.",
        }
        central_requirement = {
            "temp_id": "TEMP-1", "nombre": "Imprimir reportes",
            "descripcion_formal": "El sistema deberá permitir imprimir los reportes.",
            "tipo": "RNF", "origen": "Los reportes deben poder imprimirse.",
            "justificacion": "Texto del Central.", "prioridad": None,
            "procedencia": "inferida",
        }
        result = completar_requerimientos_explicitos_faltantes(
            [central_requirement], original,
        )
        print_requirements = [r for r in result if "imprimir" in r["descripcion_formal"].casefold()]
        self.assertIs(result[0], central_requirement)
        self.assertEqual(len(print_requirements), 1)
        self.assertEqual(print_requirements[0]["tipo"], "RF")
        self.assertEqual(print_requirements[0]["procedencia"], "explícita — observación")

    def test_all_explicit_criteria_are_added_without_story_mixing(self):
        issue_a = {
            "funcionalidad": "Consultar agenda", "criterios_aceptacion": [
                "Mostrar citas del día", "Mostrar nombre del paciente",
            ], "restricciones": [], "observaciones": "",
        }
        issue_b = {
            "funcionalidad": "Generar reportes", "criterios_aceptacion": [
                "Mostrar estadísticas en los reportes",
            ], "restricciones": [], "observaciones": "Los reportes deben poder imprimirse.",
        }
        result_a = completar_requerimientos_explicitos_faltantes([], issue_a)
        result_b = completar_requerimientos_explicitos_faltantes([], issue_b)
        text_a = " ".join(r["descripcion_formal"] for r in result_a).casefold()
        text_b = " ".join(r["descripcion_formal"] for r in result_b).casefold()
        self.assertIn("citas del día", text_a)
        self.assertIn("nombre del paciente", text_a)
        self.assertNotIn("reportes", text_a)
        self.assertIn("estadísticas", text_b)
        self.assertIn("imprimir", text_b)
        self.assertTrue(all(r["tipo"] == "RF" for r in result_a + result_b))
        self.assertGreaterEqual(len(result_a + result_b), 6)

    def test_consolidation_recovers_five_actors_and_objectives_from_original(self):
        ids = set(range(1, 6))
        central = {"resultados": [
            {"issue_iid": iid, "actor": "", "objetivo": "", "requerimientos": []}
            for iid in ids
        ]}
        quality = {"resultados": [
            {"issue_iid": iid, "indice": 1.0, "estado_medicion": "evaluable", "metricas": {}}
            for iid in ids
        ]}
        security = {"resultados": [
            {"issue_iid": iid, "indice": 1.0, "estado_medicion": "evaluable", "metricas": {}}
            for iid in ids
        ]}
        evaluation = {"resultados": [
            {"issue_iid": iid, "veredicto": "APROBADO", "riesgos_criticos": []}
            for iid in ids
        ]}
        originals = {
            iid: {
                "actor": f"Actor {iid}", "funcionalidad": f"Acción {iid}",
                "objetivo": "Liberar el horario reservado" if iid == 5 else f"Objetivo {iid}",
                "criterios_aceptacion": [], "restricciones": [], "observaciones": "",
            }
            for iid in ids
        }
        result = consolidar_lote(
            ids, central, quality, security, evaluation,
            original_issues=originals,
        )
        consolidated = [item["central"] for item in result["resultados"]]
        self.assertEqual([item["actor"] for item in consolidated], [f"Actor {i}" for i in ids])
        self.assertEqual(consolidated[-1]["objetivo"], "Liberar el horario reservado")
        self.assertEqual(len([item["objetivo"] for item in consolidated if item["objetivo"]]), 5)

    def test_generic_risk_is_replaced_by_real_missing_aspects(self):
        central = {"resultados": [{"issue_iid": 6, "requerimientos": []}]}
        quality = {"resultados": [{"issue_iid": 6, "indice": 1.0, "metricas": {}}]}
        security = {"resultados": [{
            "issue_iid": 6, "indice": 0.5,
            "metricas": {
                "cobertura_seguridad": {"aspectos_faltantes": ["Auditoría"]},
                "clasificacion_datos": {"datos_sin_clasificacion": []},
            },
        }]}
        evaluation = {"resultados": [{
            "issue_iid": 6, "veredicto": "CORREGIR",
            "riesgos_criticos": ["Riesgo concreto identificado"],
        }]}
        result = consolidar_lote({6}, central, quality, security, evaluation)
        risks = result["resultados"][0]["evaluation"]["riesgos_criticos"]
        self.assertEqual(risks, ["Aspecto de seguridad sin documentar: Auditoría."])

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
