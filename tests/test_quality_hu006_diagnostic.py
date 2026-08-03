"""Diagnóstico local del universo ambiguo observado en HU-006."""

import hashlib
import json
import unittest

from core.batch_contract import (
    _clave_texto, _firma_funcional, completar_resultado_calidad, funciones_equivalentes,
    obtener_universo_funcional_calidad, validar_semantica_calidad_llm,
)


LEGITIMATE = [
    "Mostrar únicamente horarios disponibles",
    "Mostrar nombre y especialidad del médico",
    "Actualizar disponibilidad después de programar la cita",
]
DUPLICATED = ["Consultar horarios disponibles", *LEGITIMATE]
RNF = ["Tiempo de respuesta de la consulta", "Disponibilidad de información en tiempo real"]


def requirement(name, kind="RF"):
    return {
        "nombre": name, "tipo": kind,
        "descripcion_formal": f"El sistema deberá {name[:1].lower() + name[1:]}",
        "origen": name, "procedencia": "explícita — criterio de aceptación",
    }


def prepared(functions):
    return {
        "agente": "central", "resultados": [{
            "issue_iid": 6, "historia_id": "HU-006",
            "funciones_principales_evaluables": list(functions),
            "reglas_funcionales_contextuales": [],
            "requerimientos": [*(requirement(value) for value in functions), *(requirement(value, "RNF") for value in RNF)],
        }],
    }


def quality_item(functions):
    return {
        "issue_iid": 6, "historia_id": "HU-006",
        "metricas": {
            "cobertura_funcional": {
                "funciones_especificadas": list(functions),
                "funciones_incluidas": list(functions), "funciones_faltantes": [],
                "justificacion": "Clasificación completa.", "recomendacion": "",
            },
            "adecuacion_funcional": {
                "funciones_evaluables": list(functions),
                "funciones_alineadas": list(functions), "funciones_no_alineadas": [],
                "justificacion": "Clasificación completa.", "recomendacion": "",
            },
        },
        "observaciones": "", "recomendaciones": [],
    }


def response(item):
    return {"agente": "calidad", "resultados": [item]}


def sanitized_diagnostic(source, llm_item):
    result = validar_semantica_calidad_llm(response(llm_item), source)
    by_issue = result["by_issue"][0]
    canonical = obtener_universo_funcional_calidad(source["resultados"][0])["funciones_principales_evaluables"]
    hashes = [hashlib.sha256(_clave_texto(value).encode("utf-8")).hexdigest()[:12] for value in canonical]
    signatures = []
    for value in llm_item["metricas"]["cobertura_funcional"]["funciones_especificadas"]:
        action, objects = _firma_funcional(value)
        matches = [item for item in canonical if funciones_equivalentes(value, item)]
        signatures.append({
            "element_hash": hashlib.sha256(_clave_texto(value).encode("utf-8")).hexdigest()[:12],
            "extracted_action": action,
            "extracted_object_hash": hashlib.sha256("|".join(objects).encode("utf-8")).hexdigest()[:12],
            "matched_canonical_hash": (
                hashlib.sha256(_clave_texto(matches[0]).encode("utf-8")).hexdigest()[:12]
                if len(matches) == 1 else None
            ),
            "match_count": len(matches),
        })
    return {
        "issue_iid": 6,
        "canonical_function_count": len(canonical),
        "canonical_function_hashes": hashes,
        "llm_function_count_by_field": {field: 4 for field in (
            "funciones_especificadas", "funciones_incluidas",
            "funciones_evaluables", "funciones_alineadas",
        )},
        "out_of_universe_by_field": by_issue["out_of_universe_by_field"],
        "out_of_universe_element_hashes": by_issue["out_of_universe_element_ids"],
        "elements": signatures,
        "classified_as_rnf_count": 0,
        "classified_as_contextual_rule_count": 0,
    }


class QualityHU006DiagnosticTests(unittest.TestCase):
    def test_methodological_universe_has_three_functions_and_excludes_rnf(self):
        universe = obtener_universo_funcional_calidad(prepared(LEGITIMATE)["resultados"][0])
        self.assertEqual(universe["main_function_count"], 3)
        self.assertEqual(universe["documentary_rnf_count"], 2)
        self.assertTrue(all(value not in universe["funciones_principales_evaluables"] for value in RNF))

    def test_duplicate_criterion_is_reduced_from_four_to_three(self):
        universe = obtener_universo_funcional_calidad(prepared(DUPLICATED)["resultados"][0])
        self.assertEqual(universe["main_functions_before_dedup"], 4)
        self.assertEqual(universe["main_functions_after_dedup"], 3)
        self.assertEqual(universe["equivalent_functions_merged"], 1)
        self.assertTrue(funciones_equivalentes(DUPLICATED[0], DUPLICATED[1]))

    def test_previous_ambiguity_had_two_candidates_but_clean_universe_validates(self):
        variants = [
            "Mostrar los horarios disponibles", LEGITIMATE[1], LEGITIMATE[2],
        ]
        self.assertEqual(sum(funciones_equivalentes(variants[0], value) for value in DUPLICATED), 2)
        result = validar_semantica_calidad_llm(response(quality_item(variants)), prepared(DUPLICATED))
        self.assertTrue(result["valid"])
        diagnostic = result["by_issue"][0]
        self.assertEqual(diagnostic["expected_functions"], 3)
        self.assertEqual(diagnostic["classified_included"], 3)
        self.assertEqual(diagnostic["classified_aligned"], 3)
        self.assertEqual(diagnostic["out_of_universe_count"], 0)

    def test_three_equivalent_legitimate_functions_are_valid_without_duplicate(self):
        variants = [
            "Consultar horarios disponibles", "Mostrar el nombre y la especialidad del médico",
            "Actualizar la disponibilidad después de programar la cita",
        ]
        self.assertTrue(validar_semantica_calidad_llm(response(quality_item(variants)), prepared(LEGITIMATE))["valid"])

    def test_hu006_deduplicated_metrics_are_complete(self):
        source = prepared(DUPLICATED)
        canonical = obtener_universo_funcional_calidad(source["resultados"][0])["funciones_principales_evaluables"]
        item = quality_item(canonical)
        self.assertTrue(validar_semantica_calidad_llm(response(item), source)["valid"])
        completar_resultado_calidad(item, {
            "funcionalidad": "Consultar horarios disponibles",
            "objetivo": "Programar una cita médica sin conflictos de horario",
            "requerimientos_preparados": source["resultados"][0]["requerimientos"],
            "funciones_principales_evaluables": canonical,
            "reglas_funcionales_contextuales": [],
        })
        mc01 = item["metricas"]["cobertura_funcional"]
        mc02 = item["metricas"]["adecuacion_funcional"]
        self.assertEqual((mc01["valor"], mc02["valor"]), (1.0, 1.0))
        self.assertEqual((len(mc01["funciones_incluidas"]), len(mc01["funciones_faltantes"])), (3, 0))
        self.assertEqual((len(mc02["funciones_alineadas"]), len(mc02["funciones_no_alineadas"])), (3, 0))

    def test_rnf_returned_as_function_is_outside_universe(self):
        variants = [*LEGITIMATE, RNF[0]]
        result = validar_semantica_calidad_llm(response(quality_item(variants)), prepared(LEGITIMATE))
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_OUT_OF_UNIVERSE")

    def test_sanitized_audit_has_hashes_and_no_fixture_text(self):
        variants = ["Consultar horarios disponibles", LEGITIMATE[1], LEGITIMATE[2]]
        diagnostic = sanitized_diagnostic(prepared(DUPLICATED), quality_item(variants))
        serialized = json.dumps(diagnostic, ensure_ascii=False)
        self.assertEqual(diagnostic["canonical_function_count"], 3)
        self.assertEqual(len(diagnostic["out_of_universe_element_hashes"]), 0)
        for text in (*LEGITIMATE, *RNF, "Consultar horarios disponibles"):
            self.assertNotIn(text, serialized)

    def test_evidence_order_and_idempotence_are_preserved(self):
        universe = obtener_universo_funcional_calidad(prepared(DUPLICATED)["resultados"][0])
        self.assertEqual(universe["funciones_principales_evaluables"], [DUPLICATED[0], LEGITIMATE[1], LEGITIMATE[2]])
        self.assertEqual(universe["evidencias_funciones_equivalentes"][0]["source_indices"], [0, 1])
        second = obtener_universo_funcional_calidad({
            "funciones_principales_evaluables": universe["funciones_principales_evaluables"],
            "reglas_funcionales_contextuales": [], "requerimientos": prepared(DUPLICATED)["resultados"][0]["requerimientos"],
        })
        self.assertEqual(second["funciones_principales_evaluables"], universe["funciones_principales_evaluables"])
        self.assertEqual(second["equivalent_functions_merged"], 0)

    def test_hu007_is_independent_from_hu006_ambiguity(self):
        story7 = prepared(["Registrar pacientes", "Validar documento", "Impedir registros duplicados", "Editar información del paciente"])
        story7["resultados"][0].update({"issue_iid": 7, "historia_id": "HU-007"})
        item7 = quality_item(story7["resultados"][0]["funciones_principales_evaluables"])
        item7.update({"issue_iid": 7, "historia_id": "HU-007"})
        self.assertTrue(validar_semantica_calidad_llm(response(item7), story7)["valid"])


if __name__ == "__main__":
    unittest.main()
