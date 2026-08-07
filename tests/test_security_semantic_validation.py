import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core.batch_contract import (
    clasificacion_explicita_confirmada, completar_resultado_seguridad,
    diagnosticar_estructura_seguridad_llm,
    extraer_clasificacion_dato, extraer_identidad_dato,
    obtener_universo_datos_seguridad, resumir_seguridad_post_python,
    validar_semantica_seguridad_llm,
)
from core.graph import _ejecutar_sublotes_remotos
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import RemoteBatchError


ASPECTS = ["AutenticaciÃ³n", "AutorizaciÃ³n", "AuditorÃ­a", "ProtecciÃ³n de datos"]


def evidence(data=None):
    return {
        "descripcion": "Evidencia ficticia.", "maneja_datos_sensibles": "SÃ­",
        "tipos_datos_sensibles": data or ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"],
        "autenticacion": "Usuario y contraseÃ±a", "autorizacion_roles": "Rol definido",
        "auditoria": "Registro definido",
    }


def source(iids=(8, 9), evidences=None):
    evidences = evidences or {iid: evidence() for iid in iids}
    return {"agente": "central", "resultados": [
        {"issue_iid": iid, "historia_id": f"HU-{iid:03d}", "evidencia_seguridad": copy.deepcopy(evidences[iid])}
        for iid in iids
    ]}


def security_item(iid, *, aspects=None, documented=None, partial=None, missing=None,
                  identified=None, classified=None, unclassified=None, inferred=None):
    aspects = list(ASPECTS if aspects is None else aspects)
    documented = list(aspects if documented is None else documented)
    identified = list(["Nombre ficticio", "Documento ficticio"] if identified is None else identified)
    classified = list([f"{name}: PERSONAL" for name in identified] if classified is None else classified)
    return {
        "issue_iid": iid, "historia_id": f"HU-{iid:03d}", "lot_recomendado": "LoT-2",
        "metricas": {
            "cobertura_seguridad": {
                "codigo": "MS-01", "aspectos_aplicables": aspects,
                "aspectos_documentados": documented, "aspectos_parciales": list(partial or []),
                "aspectos_faltantes": list(missing or []), "aspectos_inferidos": [],
                "justificacion": "Evidencia suficiente.", "recomendacion": "",
            },
            "clasificacion_datos": {
                "codigo": "MS-02", "datos_identificados": identified,
                "datos_clasificados": classified, "datos_sin_clasificacion": list(unclassified or []),
                "clasificaciones_inferidas": list(inferred or []),
                "justificacion": "Evidencia suficiente.", "recomendacion": "",
            },
        },
        "observaciones": "", "recomendaciones": [],
    }


def response(*items):
    return {"agente": "seguridad", "resultados": list(items)}


class SecuritySemanticValidationTests(unittest.TestCase):
    def assert_rule(self, result, rule, field=None):
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_CONTRADICTION")
        self.assertEqual(result["failed_semantic_rule"], rule)
        if field:
            self.assertEqual(result["by_issue"][-1]["affected_field"], field)

    def test_valid_partition_of_four_aspects_and_data(self):
        result = validar_semantica_seguridad_llm(response(security_item(8)), source((8,)))
        self.assertTrue(result["valid"])
        self.assertEqual(result["by_issue"][0]["documented_aspects"], 4)

    def test_aspect_in_two_groups(self):
        item = security_item(8, partial=[ASPECTS[0]])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_ASPECT_IN_MULTIPLE_GROUPS")

    def test_aspect_outside_applicable_universe(self):
        item = security_item(8, documented=ASPECTS + ["Cifrado"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_ASPECT_OUT_OF_APPLICABLE_UNIVERSE", "aspectos_documentados")

    def test_aspect_duplicate(self):
        item = security_item(8, aspects=ASPECTS + [ASPECTS[0]], documented=ASPECTS)
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_ASPECT_DUPLICATED", "aspectos_aplicables")

    def test_data_in_both_groups(self):
        item = security_item(8, unclassified=["Nombre ficticio"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_DATA_IN_MULTIPLE_GROUPS")

    def test_explicit_classification_without_source(self):
        ev = evidence(["Nombre ficticio: PERSONAL", "Documento ficticio"])
        result = validar_semantica_seguridad_llm(response(security_item(8)), source((8,), {8: ev}))
        self.assert_rule(result, "SECURITY_EXPLICIT_CLASSIFICATION_WITHOUT_SOURCE", "datos_clasificados")
        self.assertTrue(result["by_issue"][0]["source_evidence_found"])

    def test_inferred_classification_does_not_count_as_explicit(self):
        ev = evidence(["Nombre ficticio"])
        item = security_item(8, identified=["Nombre ficticio"], classified=["Nombre ficticio: PERSONAL"], inferred=["Nombre ficticio: PERSONAL"])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))
        self.assert_rule(result, "SECURITY_INFERRED_CLASSIFICATION_COUNTED_AS_EXPLICIT")

    def test_invented_data(self):
        item = security_item(8, identified=["Dato inexistente"], classified=[], unclassified=["Dato inexistente"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_DATA_NOT_FOUND_IN_ORIGINAL_EVIDENCE")

    def test_cross_issue_data(self):
        evidences = {8: evidence(["Nombre ficticio: PERSONAL"]), 9: evidence(["Dato comercial: PERSONAL"])}
        item = security_item(8, identified=["Dato comercial"], classified=["Dato comercial: PERSONAL"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8, 9), evidences)), "SECURITY_CROSS_ISSUE_EVIDENCE")

    def test_normalization_collision(self):
        ev = evidence(["Nombre: PERSONAL"])
        item = security_item(8, identified=["Nombre", "NOMBRE!"], classified=["Nombre: PERSONAL", "NOMBRE!: PERSONAL"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,), {8: ev})), "SECURITY_INVALID_NORMALIZATION_COLLISION")

    def test_exact_semantic_duplicate(self):
        item = security_item(8, identified=["Nombre ficticio", "Nombre ficticio"], classified=["Nombre ficticio: PERSONAL"])
        self.assert_rule(validar_semantica_seguridad_llm(response(item), source((8,))), "SECURITY_DATA_DUPLICATED")

    def test_explicit_confirmation_is_structured(self):
        check = clasificacion_explicita_confirmada("nombre ficticio", evidence(), "personal")
        self.assertTrue({
            "found_data", "found_explicit_category", "category_source", "inferred_only",
            "collision_detected", "classification_mismatch", "data_found",
            "classification_found", "classification_matches_source", "normalization_collision",
        }.issubset(check))
        self.assertTrue(check["found_explicit_category"])

    def test_text_identified_and_structured_classified_are_equivalent(self):
        ev = evidence([{"dato": "Nombre del paciente", "clasificacion": "PERSONAL"}])
        item = security_item(8, identified=["Nombre del paciente"], classified=[{"dato": "Nombre del paciente", "clasificacion": "PERSONAL"}])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))
        self.assertTrue(result["valid"])
        self.assertEqual(result["by_issue"][0]["out_of_universe_count"] if "out_of_universe_count" in result["by_issue"][0] else 0, 0)

    def test_structured_identified_and_text_classified_are_equivalent(self):
        ev = evidence(["Nombre del paciente: PERSONAL"])
        item = security_item(8, identified=[{"dato": "Nombre del paciente"}], classified=["Nombre del paciente: PERSONAL"])
        self.assertTrue(validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))["valid"])

    def test_supported_text_separators_extract_identity_and_category(self):
        for value in ("Dato A: PERSONAL", "Dato A â†’ PERSONAL", "Dato A -> PERSONAL"):
            with self.subTest(value=value):
                self.assertEqual(extraer_identidad_dato(value)["signature"], "dato a")
                self.assertEqual(extraer_clasificacion_dato(value)["signature"], "personal")

    def test_supported_object_keys_and_metadata(self):
        cases = (
            ({"dato": "Dato A", "clasificacion": "PERSONAL"}, "dict:dato", "dict:clasificacion"),
            ({"nombre": "Dato A", "categoria": "PERSONAL"}, "dict:nombre", "dict:categoria"),
            ({"dato": "Dato A", "clasificacion": "PERSONAL", "fuente": "evidencia_original"}, "dict:dato", "dict:clasificacion"),
        )
        for value, identity_strategy, category_strategy in cases:
            with self.subTest(value=value):
                identity = extraer_identidad_dato(value)
                category = extraer_clasificacion_dato(value)
                self.assertEqual(identity["signature"], "dato a")
                self.assertEqual(category["signature"], "personal")
                self.assertEqual(identity["extraction_strategy"], identity_strategy)
                self.assertEqual(category["extraction_strategy"], category_strategy)

    def test_category_and_keys_are_not_part_of_identity(self):
        plain = extraer_identidad_dato("Dato A")["signature"]
        self.assertEqual(plain, extraer_identidad_dato("Dato A: PERSONAL")["signature"])
        self.assertEqual(plain, extraer_identidad_dato({"dato": "Dato A", "clasificacion": "SENSIBLE"})["signature"])
        self.assertNotIn("clasificacion", plain)

    def test_unsupported_object_keys_fail_identity_extraction(self):
        item = security_item(8, identified=["Dato A"], classified=[{"campo_arbitrario": "Dato A", "nivel": "PERSONAL"}])
        ev = evidence(["Dato A: PERSONAL"])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))
        self.assert_rule(result, "SECURITY_DATA_IDENTITY_EXTRACTION_FAILED", "datos_clasificados")

    def test_missing_structured_category_has_distinct_rule(self):
        item = security_item(8, identified=["Dato A"], classified=[{"dato": "Dato A"}])
        ev = evidence(["Dato A: PERSONAL"])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))
        self.assert_rule(result, "SECURITY_CLASSIFICATION_EXTRACTION_FAILED", "datos_clasificados")

    def test_original_evidence_dictionary_is_supported(self):
        ev = evidence()
        ev["tipos_datos_sensibles"] = {"Dato A": "PERSONAL", "Dato B": "COMERCIAL"}
        item = security_item(8, identified=["Dato A", "Dato B"], classified=[
            {"dato": "Dato A", "clasificacion": "PERSONAL"},
            {"nombre": "Dato B", "categoria": "COMERCIAL"},
        ])
        self.assertTrue(validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))["valid"])

    def test_source_without_category_is_not_outside_universe(self):
        ev = evidence(["Dato A"])
        item = security_item(8, identified=["Dato A"], classified=[{"dato": "Dato A", "clasificacion": "PERSONAL"}])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: ev}))
        self.assert_rule(result, "SECURITY_EXPLICIT_CLASSIFICATION_WITHOUT_SOURCE", "datos_clasificados")

    def test_mixed_format_audit_contains_only_structure_metadata(self):
        item = security_item(8, identified=["Dato A"], classified=[{"dato": "Otro dato", "clasificacion": "PERSONAL", "fuente": "secreta"}])
        result = validar_semantica_seguridad_llm(response(item), source((8,), {8: evidence(["Dato A: PERSONAL"])}))
        diagnostic = result["by_issue"][0]
        self.assertEqual(diagnostic["classified_item_type"], "dict")
        self.assertEqual(diagnostic["classified_item_keys"], ["clasificacion", "dato", "fuente"])
        self.assertEqual(diagnostic["extraction_strategy"], "dict:dato")
        self.assertFalse(diagnostic["identity_match_found"])
        serialized = json.dumps(diagnostic, ensure_ascii=False)
        self.assertNotIn("Otro dato", serialized)
        self.assertNotIn("secreta", serialized)

    def test_llm_raw_diagnostic_captures_two_text_matches_before_calculation(self):
        ev = evidence(["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"])
        item = security_item(8)
        diagnostic = diagnosticar_estructura_seguridad_llm(response(item), source((8,), {8: ev}))[0]
        self.assertEqual(diagnostic["contract_stage"], "llm_raw")
        self.assertEqual(diagnostic["identified_items"], {
            "count": 2, "types": {"str": 2},
            "identity_extraction_success": 2, "identity_extraction_failed": 0,
        })
        self.assertEqual(diagnostic["classified_items"]["strategies"], {"text_separator": 2})
        self.assertEqual(diagnostic["classified_items"]["identity_matches"], 2)
        self.assertEqual(diagnostic["classified_items"]["classification_extraction_success"], 2)
        self.assertEqual(diagnostic["classified_items"]["source_classification_matches"], 2)
        self.assertEqual(diagnostic["external_data_count"], 0)

    def test_arrow_and_structured_object_strategies_are_distinct(self):
        ev = evidence(["Dato A: PERSONAL", {"dato": "Dato B", "clasificacion": "COMERCIAL"}])
        item = security_item(8, identified=["Dato A", {"dato": "Dato B"}], classified=[
            "Dato A â†’ PERSONAL", {"dato": "Dato B", "clasificacion": "COMERCIAL"},
        ])
        diagnostic = diagnosticar_estructura_seguridad_llm(response(item), source((8,), {8: ev}))[0]
        self.assertEqual(diagnostic["classified_items"]["strategies"], {
            "structured_object": 1, "text_separator": 1,
        })
        self.assertEqual(diagnostic["classified_items"]["object_keys"], {"clasificacion": 1, "dato": 1})

    def test_llm_raw_diagnostic_survives_post_python_mutation(self):
        ev = evidence()
        item = security_item(8)
        parsed = response(item)
        raw_diagnostic = copy.deepcopy(diagnosticar_estructura_seguridad_llm(parsed, source((8,), {8: ev})))
        completar_resultado_seguridad(item, {"seguridad": ev})
        item["metricas"]["clasificacion_datos"]["datos_clasificados"].clear()
        self.assertEqual(raw_diagnostic[0]["classified_items"]["identity_matches"], 2)
        self.assertEqual(raw_diagnostic[0]["classified_items"]["source_classification_matches"], 2)

    def test_hu009_zero_data_is_valid_raw_diagnostic(self):
        ev = evidence([])
        ev["maneja_datos_sensibles"] = "No"
        item = security_item(9, identified=[], classified=[], unclassified=[])
        diagnostic = diagnosticar_estructura_seguridad_llm(response(item), source((9,), {9: ev}))[0]
        self.assertEqual(diagnostic["identified_items"]["count"], 0)
        self.assertEqual(diagnostic["classified_items"]["count"], 0)
        self.assertEqual(diagnostic["unclassified_items"]["count"], 0)
        self.assertTrue(validar_semantica_seguridad_llm(response(item), source((9,), {9: ev}))["valid"])

    def test_post_python_summary_is_separate_and_has_official_metrics(self):
        ev = evidence()
        item = security_item(8)
        completar_resultado_seguridad(item, {"seguridad": ev})
        summary = resumir_seguridad_post_python(response(item))[0]
        self.assertEqual(summary["contract_stage"], "post_python")
        self.assertEqual((summary["ms01"], summary["ms02"], summary["security_index"]), (1.0, 1.0, 1.0))
        self.assertEqual((summary["lot"], summary["status"]), ("LoT-2", "Cumple"))
        self.assertNotIn("strategies", summary)

    def test_technical_diagnostic_never_enters_product_contract(self):
        item = security_item(8)
        parsed = response(item)
        snapshot = copy.deepcopy(parsed)
        diagnostic = diagnosticar_estructura_seguridad_llm(parsed, source((8,)))
        validar_semantica_seguridad_llm(parsed, source((8,)))
        self.assertEqual(parsed, snapshot)
        serialized = json.dumps(parsed, ensure_ascii=False)
        for forbidden in ("security_llm_raw_diagnostic", "identity_matches", "contract_stage"):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(diagnostic)

    def test_failed_semantics_preserves_partial_raw_diagnostic_and_pending_hu009(self):
        item8 = security_item(8, identified=["Dato A"], classified=["Otro dato: PERSONAL"])
        payload = source((8, 9), {8: evidence(["Dato A: PERSONAL"]), 9: evidence()})
        raw = diagnosticar_estructura_seguridad_llm(response(item8, security_item(9)), payload)
        semantic = validar_semantica_seguridad_llm(response(item8, security_item(9)), payload)
        self.assertEqual(raw[0]["classified_items"]["identity_matches"], 0)
        self.assertEqual(semantic["failed_issue_iid"], 8)
        self.assertEqual(semantic["pending_semantic_validation"], [9])

    def test_partial_batch_audit_preserves_identity_and_pending_story(self):
        reiniciar_contadores()
        item8 = security_item(8, documented=ASPECTS + ["Cifrado"])
        payload = source((8, 9))
        raw = json.dumps(response(item8, security_item(9)), ensure_ascii=False)
        with self.assertRaises(RemoteBatchError):
            _ejecutar_sublotes_remotos(json.dumps(payload, ensure_ascii=False), "Seguridad", 2, lambda _raw, _batch: raw)
        event = next(x for x in obtener_contadores()["eventos_sublotes_remotos"] if x["event"] == "remote_sub_batch_error")
        self.assertEqual(event["received_issue_ids"], [8, 9])
        self.assertEqual(event["failed_issue_iid"], 8)
        self.assertEqual(event["pending_semantic_validation"], [9])
        self.assertEqual(event["failed_semantic_rule"], "SECURITY_ASPECT_OUT_OF_APPLICABLE_UNIVERSE")
        self.assertNotIn("Cifrado", json.dumps(event, ensure_ascii=False))
        self.assertNotIn("Nombre ficticio", json.dumps(event, ensure_ascii=False))

    def test_no_metrics_are_calculated_after_contradiction(self):
        item = security_item(8, documented=ASPECTS + ["Cifrado"])
        original = copy.deepcopy(item)
        validar_semantica_seguridad_llm(response(item), source((8,)))
        self.assertEqual(item, original)
        self.assertNotIn("valor", item["metricas"]["cobertura_seguridad"])

    def test_valid_hu008_and_hu009(self):
        result = validar_semantica_seguridad_llm(response(security_item(8), security_item(9)), source())
        self.assertTrue(result["valid"])
        self.assertEqual([x["issue_iid"] for x in result["by_issue"]], [8, 9])

    def test_hu006_and_hu007_remain_valid(self):
        result = validar_semantica_seguridad_llm(response(security_item(6), security_item(7)), source((6, 7)))
        self.assertTrue(result["valid"])

    def test_other_domains_personal_and_commercial(self):
        evidences = {
            20: evidence([{"dato": "Correo", "clasificacion": "PERSONAL"}]),
            21: evidence([{"dato": "NÃºmero de pedido", "clasificacion": "COMERCIAL"}]),
        }
        items = response(
            security_item(20, identified=["Correo"], classified=["Correo: PERSONAL"]),
            security_item(21, identified=["NÃºmero de pedido"], classified=["NÃºmero de pedido: COMERCIAL"]),
        )
        self.assertTrue(validar_semantica_seguridad_llm(items, source((20, 21), evidences))["valid"])

    def test_canonical_universe_preserves_two_individual_data(self):
        ev = evidence(["Nombre ficticio", "Documento ficticio"])
        self.assertEqual(
            obtener_universo_datos_seguridad({}, ev),
            ["Nombre ficticio", "Documento ficticio"],
        )

    def test_generic_group_cannot_replace_or_expand_canonical_universe(self):
        ev = evidence(["Nombre ficticio", "Documento ficticio"])
        item = security_item(
            10, identified=["Datos personales"], classified=[],
            unclassified=["Datos personales"],
        )
        result = validar_semantica_seguridad_llm(response(item), source((10,), {10: ev}))
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_INCOMPLETE")
        self.assertEqual(result["failed_semantic_rule"], "SECURITY_GENERIC_DATA_GROUP_RETURNED")
        diagnostic = result["by_issue"][0]
        self.assertEqual(diagnostic["canonical_data_count"], 2)
        self.assertEqual(diagnostic["llm_identified_data_count"], 1)
        self.assertEqual(diagnostic["missing_canonical_data_count"], 2)
        self.assertEqual(diagnostic["generic_group_count"], 1)
        self.assertNotIn("valor", item["metricas"]["clasificacion_datos"])
        self.assertNotIn("Datos personales", obtener_universo_datos_seguridad({}, ev))

    def test_generic_group_is_discarded_only_when_source_has_no_canonical_data(self):
        from core.batch_contract import descartar_grupos_genericos_sin_datos_canonicos

        ev = evidence([])
        ev["maneja_datos_sensibles"] = "Sí. Datos personales."
        ev["tipos_datos_sensibles"] = []
        item = security_item(
            10, identified=["Datos personales"], classified=[],
            unclassified=["Datos personales"], inferred=["Datos personales: PERSONAL"],
        )
        parsed = response(item)
        payload = source((10,), {10: ev})

        self.assertEqual(descartar_grupos_genericos_sin_datos_canonicos(parsed, payload), [10])
        metric = parsed["resultados"][0]["metricas"]["clasificacion_datos"]
        self.assertEqual(
            [metric[field] for field in ("datos_identificados", "datos_clasificados", "datos_sin_clasificacion", "clasificaciones_inferidas")],
            [[], [], [], []],
        )
        self.assertTrue(validar_semantica_seguridad_llm(parsed, payload)["valid"])

    def test_concrete_external_data_keeps_original_error(self):
        ev = evidence(["Nombre ficticio", "Documento ficticio"])
        item = security_item(
            10, identified=["DirecciÃ³n domiciliaria"], classified=[],
            unclassified=["DirecciÃ³n domiciliaria"],
        )
        result = validar_semantica_seguridad_llm(response(item), source((10,), {10: ev}))
        self.assert_rule(result, "SECURITY_DATA_NOT_FOUND_IN_ORIGINAL_EVIDENCE")
        self.assertEqual(result["by_issue"][0]["external_data_count"], 1)
        self.assertEqual(result["by_issue"][0]["generic_group_count"], 0)

    def test_missing_one_canonical_data_is_incomplete(self):
        ev = evidence(["Nombre ficticio", "Documento ficticio"])
        item = security_item(
            10, identified=["Nombre ficticio"], classified=[],
            unclassified=["Nombre ficticio"],
        )
        result = validar_semantica_seguridad_llm(response(item), source((10,), {10: ev}))
        self.assertEqual(result["error_category"], "REMOTE_SEMANTIC_INCOMPLETE")
        self.assertEqual(result["failed_semantic_rule"], "SECURITY_CANONICAL_DATA_MISSING")
        self.assertEqual(result["by_issue"][0]["missing_canonical_data_count"], 1)

    def test_canonical_ms02_ratios_zero_half_and_one(self):
        cases = (
            (["Nombre ficticio", "Documento ficticio"], [], ["Nombre ficticio", "Documento ficticio"], 0.0),
            (["Nombre ficticio: PERSONAL", "Documento ficticio"], ["Nombre ficticio: PERSONAL"], ["Documento ficticio"], 0.5),
            (["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"], ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"], [], 1.0),
        )
        for source_values, classified, unclassified, expected in cases:
            with self.subTest(expected=expected):
                ev = evidence(source_values)
                item = security_item(
                    10, identified=["Nombre ficticio", "Documento ficticio"],
                    classified=classified, unclassified=unclassified,
                )
                parsed = response(item)
                self.assertTrue(validar_semantica_seguridad_llm(parsed, source((10,), {10: ev}))["valid"])
                completar_resultado_seguridad(item, {"seguridad": ev})
                self.assertEqual(item["metricas"]["clasificacion_datos"]["valor"], expected)

    def test_inferred_category_is_preserved_but_does_not_count(self):
        ev = evidence(["Nombre del empleado", "Documento del empleado"])
        item = security_item(
            30, identified=["Nombre del empleado", "Documento del empleado"],
            classified=[], unclassified=["Nombre del empleado", "Documento del empleado"],
            inferred=["Nombre del empleado: PERSONAL", "Documento del empleado: PERSONAL"],
        )
        self.assertTrue(validar_semantica_seguridad_llm(response(item), source((30,), {30: ev}))["valid"])
        completar_resultado_seguridad(item, {"seguridad": ev})
        metric = item["metricas"]["clasificacion_datos"]
        self.assertEqual(metric["valor"], 0.0)
        self.assertEqual(len(metric["clasificaciones_inferidas"]), 2)

    def test_educational_commercial_and_hr_canonical_universes(self):
        cases = (
            ["MatrÃ­cula estudiantil", "CalificaciÃ³n"],
            ["NÃºmero de pedido", "Identificador de cliente"],
            ["Nombre del empleado", "Documento del empleado"],
        )
        for values in cases:
            with self.subTest(values=values):
                self.assertEqual(obtener_universo_datos_seguridad({}, evidence(values)), values)

    def test_canonical_audit_is_counts_only(self):
        ev = evidence(["Nombre ficticio", "Documento ficticio"])
        item = security_item(10, identified=["Datos personales"], classified=[], unclassified=["Datos personales"])
        diagnostic = diagnosticar_estructura_seguridad_llm(response(item), source((10,), {10: ev}))[0]
        serialized = json.dumps(diagnostic, ensure_ascii=False)
        self.assertEqual(diagnostic["canonical_data_count"], 2)
        self.assertEqual(diagnostic["generic_group_count"], 1)
        for sensitive in ("Nombre ficticio", "Documento ficticio", "Datos personales"):
            self.assertNotIn(sensitive, serialized)

    def test_prompt_states_exact_partitions_and_source_association(self):
        prompt = Path("prompts/security_prompt.txt").read_text(encoding="utf-8").casefold()
        self.assertIn("exactamente una vez", prompt)
        self.assertIn("asocia directamente el dato con su categoria", prompt)
        self.assertIn("clasificaciones_inferidas", prompt)
        self.assertIn("datos_canonicos_identificados", prompt)
        self.assertIn("clasifica individualmente cada dato can", prompt)


if __name__ == "__main__":
    unittest.main()
