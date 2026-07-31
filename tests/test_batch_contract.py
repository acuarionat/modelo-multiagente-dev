import json
import unittest

from core.batch_contract import (
    calcular_metricas_agente, calcular_num_predict, recopilar_recomendaciones,
    consolidar_lote, analizar_respuesta_lote, conciliar_ids_issues,
    explicar_texto_invalido, normalizar_lista_textos, validar_contenido_agente,
    validar_respuesta_lote, renumerar_requerimientos,
)


def batch(agent, results):
    return {"agente": agent, "resultados": results}


class BatchContractTests(unittest.TestCase):

    def test_legacy_types_are_semantically_normalized_and_renumbered(self):
        items = [{"requerimientos": [
            {"tipo": "RC", "nombre": "Cancelar cita", "descripcion_formal": "El sistema deberá permitir cancelar una cita."},
            {"tipo": "RS", "nombre": "Protección", "descripcion_formal": "Los datos deberán mantenerse protegidos."},
            {"tipo": "RS", "nombre": "Caso ambiguo", "descripcion_formal": "Debe revisarse."},
        ]}]
        renumerar_requerimientos(items)
        requirements = items[0]["requerimientos"]
        self.assertEqual([item["tipo"] for item in requirements], ["RF", "RNF", "RNF"])
        self.assertEqual([item["id"] for item in requirements], ["RF-001", "RNF-001", "RNF-002"])
        self.assertTrue(requirements[2]["_normalizacion_tipo_pendiente"])

    def test_normalizes_text_lists_without_splitting_characters(self):
        self.assertEqual(normalizar_lista_textos("Corregir permisos"), ["Corregir permisos"])
        self.assertEqual(normalizar_lista_textos(["Uno", " Dos "]), ["Uno", "Dos"])
        self.assertEqual(normalizar_lista_textos(None), [])
        self.assertEqual(normalizar_lista_textos([]), [])

    def test_security_rejection_explains_exact_generic_fragment(self):
        reason = explicar_texto_invalido("Control concreto")
        self.assertIn("texto genérico", reason)
        self.assertIn("control concreto", reason)

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
            analizar_respuesta_lote(json.dumps([]), "Central")

    def test_consolidates_by_iid_not_position_and_renumbers_globally(self):
        final = consolidar_lote({11, 22}, self.central, self.quality, self.security, self.evaluation)
        first, second = final["resultados"]
        self.assertEqual(first["central"]["titulo"], "A")
        self.assertEqual(first["quality"]["indice"], .9)
        self.assertEqual(second["central"]["titulo"], "B")
        ids = [x["central"]["requerimientos"][0]["id"] for x in final["resultados"]]
        self.assertEqual(ids, ["RF-001", "RF-002"])
        self.assertEqual(sum(len(x["central"]["requerimientos"]) for x in final["resultados"]), 2)

    def test_only_missing_story_is_marked_error(self):
        self.security["resultados"] = [self.security["resultados"][1]]
        errors = validar_respuesta_lote(self.security, {11, 22}, "Seguridad")
        final = consolidar_lote({11, 22}, self.central, self.quality, self.security, self.evaluation, errors)
        self.assertEqual(final["resultados"][0]["status"], "ok")
        self.assertEqual(final["resultados"][1]["status"], "error")
        self.assertEqual(final["resumen_global"]["historias_procesadas"], 1)
        self.assertEqual(final["resumen_global"]["historias_con_error"], 1)

    def test_invalid_index_is_explicit(self):
        self.quality["resultados"][0]["indice"] = 100
        errors = validar_respuesta_lote(self.quality, {11, 22}, "Calidad")
        self.assertTrue(any("índice inválido" in error for error in errors))
        final = consolidar_lote({11, 22}, self.central, self.quality, self.security, self.evaluation, errors)
        self.assertEqual(final["resultados"][0]["status"], "error")

    def test_reconciles_llm_example_ids_to_real_gitlab_iids(self):
        response = batch("central", [
            {"issue_iid": 1, "historia_id": "HU-001", "titulo": "A", "requerimientos": []},
            {"issue_iid": 2, "historia_id": "HU-002", "titulo": "B", "requerimientos": []},
            {"issue_iid": 3, "historia_id": "HU-003", "titulo": "C", "requerimientos": []},
            {"issue_iid": 4, "historia_id": "HU-004", "titulo": "D", "requerimientos": []},
        ])
        notes = conciliar_ids_issues(response, [6, 7, 9, 10], "Central")
        self.assertEqual([x["issue_iid"] for x in response["resultados"]], [6, 7, 9, 10])
        self.assertEqual([x["historia_id"] for x in response["resultados"]], ["HU-006", "HU-007", "HU-009", "HU-010"])
        self.assertEqual(validar_respuesta_lote(response, {6, 7, 9, 10}, "Central"), [])
        self.assertEqual(len(notes), 4)

    def test_valid_issue_iid_does_not_replace_original_history_id(self):
        response = batch("calidad", [{"issue_iid": 10, "historia_id": "HU-005", "metricas": {}}])
        conciliar_ids_issues(response, [10], "Calidad")
        self.assertEqual(response["resultados"][0]["issue_iid"], 10)
        self.assertEqual(response["resultados"][0]["historia_id"], "HU-005")

    def test_quality_math_preserves_specific_evidence(self):
        response = batch("calidad", [{
            "issue_iid": 6,
            "metricas": {
                "cobertura_funcional": {
                    "elementos_evaluados": ["Registrar", "Validar", "Evitar duplicado"],
                    "elementos_con_problemas": ["Evitar duplicado"],
                    "justificacion": "Se evaluaron Registrar, Validar y Evitar duplicado; falta formalizar Evitar duplicado.",
                    "recomendacion": "Formalizar cómo se evitan registros duplicados.",
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
        calcular_metricas_agente(response, "Calidad")
        item = response["resultados"][0]
        self.assertEqual(item["metricas"]["cobertura_funcional"]["valor"], 0.6667)
        self.assertEqual(item["metricas"]["adecuacion_funcional"]["valor"], 1)
        self.assertIn("Evitar duplicado", item["metricas"]["cobertura_funcional"]["justificacion"])
        self.assertEqual(validar_contenido_agente(response, "Calidad"), {})

    def test_rejects_placeholder_content(self):
        response = batch("central", [{
            "issue_iid": 6,
            "requerimientos": [{
                "temp_id": "RF-TEMP-01", "nombre": "...", "descripcion_formal": "",
                "tipo": "RF", "origen": "N/A", "justificacion": "...", "prioridad": "Alta",
            }],
        }])
        errors = validar_contenido_agente(response, "Central")
        self.assertIn(6, errors)
        self.assertTrue(any("campos inválidos" in message for message in errors[6]))

    def test_collects_metric_and_evaluator_recommendations(self):
        result = {
            "quality": {"metricas": {"cobertura": {"recomendacion": "Definir corrección."}}},
            "security": {"metricas": {"controles": {"recomendacion": "Agregar auditoría."}}},
            "evaluation": {"correcciones_obligatorias": ["Definir permisos."]},
            "central": {"observaciones": []},
        }
        self.assertEqual(recopilar_recomendaciones(result), ["Definir corrección.", "Agregar auditoría.", "Definir permisos."])

    def test_collects_string_recommendation_as_one_item(self):
        result = {"quality": {"recomendaciones": "Aclarar el objetivo."}}
        self.assertEqual(recopilar_recomendaciones(result), ["Aclarar el objetivo."])

    def test_adequacy_matches_case_accents_spacing_and_punctuation(self):
        response = batch("calidad", [{"issue_iid": 6, "metricas": {
            "cobertura_funcional": {"elementos_evaluados": ["Mostrar horarios"], "elementos_con_problemas": []},
            "adecuacion_funcional": {
                "elementos_evaluados": ["Mostrar  horarios disponibles"],
                "elementos_alineados": ["MOSTRAR HORARIOS DISPONÍBLES."],
                "elementos_con_problemas": [],
            },
        }}])
        calcular_metricas_agente(response, "Calidad")
        self.assertEqual(response["resultados"][0]["metricas"]["adecuacion_funcional"]["valor"], 1.0)

    def test_dynamic_output_budget(self):
        self.assertEqual(calcular_num_predict("Central_Init", 5), 1900)
        self.assertEqual(calcular_num_predict("Quality", 5), 1750)
        self.assertEqual(calcular_num_predict("Security", 5), 2000)
        self.assertEqual(calcular_num_predict("Evaluator", 5), 750)

    def test_parser_recovers_json_wrapped_in_markdown(self):
        raw = '```json\n{"agente":"seguridad","resultados":[]}\n```'
        parsed = analizar_respuesta_lote(raw, "Seguridad")
        self.assertEqual(parsed["resultados"], [])

    def test_parser_reports_truncated_json(self):
        with self.assertRaisesRegex(ValueError, "truncada"):
            analizar_respuesta_lote('{"agente":"seguridad","resultados":[', "Seguridad")


if __name__ == "__main__":
    unittest.main()
