import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.central_agent import (
    _entorno_ssl_local_ollama, _normalizar_respuesta_central,
    crear_cliente_ollama_central, crear_sublotes_central,
    obtener_tamano_sublote_central, procesar_central_en_sublotes,
)
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.graph import CentralIncompleteBatchError, nodo_central_inicial


def issue(iid):
    return {
        "id": iid, "titulo": f"Historia {iid}", "actor": "Actor",
        "objetivo": f"Objetivo {iid}", "funcionalidad": f"Acción {iid}",
    }


def result(iid, **extra):
    return {
        "issue_iid": iid, "historia_id": f"HU-{iid:03d}",
        "actor": "Actor", "objetivo": f"Objetivo {iid}",
        "requerimientos": [], **extra,
    }


def wrapped(*iids):
    return json.dumps({
        "agente": "central", "milestone": "Sprint ficticio",
        "resultados": [result(iid) for iid in iids],
    }, ensure_ascii=False)


class CentralSubBatchTests(unittest.TestCase):
    def setUp(self):
        reiniciar_contadores()
        self.issues = [issue(iid) for iid in range(6, 11)]

    @staticmethod
    def complete_invoke(calls):
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append((project, context, ids))
            return wrapped(*ids)
        return invoke

    def test_size_two_splits_five_as_two_two_one(self):
        calls = []
        procesar_central_en_sublotes("P", self.issues, "C", batch_size=2, invoke=self.complete_invoke(calls))
        self.assertEqual([call[2] for call in calls], [[6, 7], [8, 9], [10]])

    def test_size_three_splits_five_as_three_two(self):
        calls = []
        procesar_central_en_sublotes("P", self.issues, "C", batch_size=3, invoke=self.complete_invoke(calls))
        self.assertEqual([call[2] for call in calls], [[6, 7, 8], [9, 10]])

    def test_single_story_produces_one_sub_batch(self):
        calls = []
        procesar_central_en_sublotes("P", self.issues[:1], "C", batch_size=2, invoke=self.complete_invoke(calls))
        self.assertEqual([call[2] for call in calls], [[6]])

    def test_invalid_batch_size_uses_two(self):
        for value in ("x", "0", "-1", None):
            with self.subTest(value=value), patch.dict(os.environ, {"CENTRAL_BATCH_SIZE": "x"} if value is None else {}):
                self.assertEqual(obtener_tamano_sublote_central(value), 2)

    def test_general_context_is_preserved_for_every_sub_batch(self):
        calls = []
        procesar_central_en_sublotes("Proyecto", self.issues, "Contexto común", batch_size=2, invoke=self.complete_invoke(calls))
        self.assertTrue(all(project == "Proyecto" and context == "Contexto común" for project, context, _ in calls))

    def test_original_order_is_restored(self):
        def reverse_invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            return wrapped(*reversed(ids))
        parsed, _ = procesar_central_en_sublotes("P", self.issues, "C", batch_size=3, invoke=reverse_invoke)
        self.assertEqual([item["issue_iid"] for item in parsed["resultados"]], [6, 7, 8, 9, 10])

    def test_association_uses_issue_iid_not_position(self):
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            return json.dumps({"resultados": [result(iid, marker=f"I-{iid}") for iid in reversed(ids)]})
        parsed, _ = procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertEqual([(x["issue_iid"], x["marker"]) for x in parsed["resultados"]], [(6, "I-6"), (7, "I-7")])

    def test_complete_sub_batch_keeps_current_contract(self):
        parsed, audit = procesar_central_en_sublotes(
            "P", self.issues[:2], "C", batch_size=2, invoke=lambda *_: wrapped(6, 7),
        )
        self.assertEqual(set(parsed), {"agente", "milestone", "resultados"})
        self.assertEqual(len(parsed["resultados"]), 2)
        self.assertEqual(audit["summary"]["incomplete_issue_ids"], [])

    def test_partial_sub_batch_keeps_valid_and_repairs_only_missing(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return wrapped(6) if ids == [6, 7] else wrapped(*ids)
        parsed, _ = procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertEqual(calls, [[6, 7], [7]])
        self.assertEqual([x["issue_iid"] for x in parsed["resultados"]], [6, 7])

    def test_only_missing_story_is_sent_to_selective_repair(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return wrapped(6) if len(calls) == 1 else wrapped(*ids)
        procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertEqual(calls[1], [7])

    def test_failed_sub_batch_does_not_remove_previous_results(self):
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            return wrapped(*ids) if ids == [6, 7] else "{"
        parsed, audit = procesar_central_en_sublotes("P", self.issues[:3], "C", batch_size=2, invoke=invoke)
        self.assertEqual([x["issue_iid"] for x in parsed["resultados"]], [6, 7])
        self.assertEqual(audit["summary"]["incomplete_issue_ids"], [8])

    def test_direct_individual_response_is_accepted_for_size_one(self):
        parsed, metadata = _normalizar_respuesta_central(json.dumps(result(10)))
        self.assertEqual(parsed["resultados"][0]["issue_iid"], 10)
        self.assertEqual(metadata["response_category"], "RESPUESTA_INDIVIDUAL")

    def test_direct_response_is_partial_for_larger_sub_batch(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return json.dumps(result(6)) if ids == [6, 7] else json.dumps(result(ids[0]))
        parsed, _ = procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertEqual(calls, [[6, 7], [7]])
        self.assertEqual([x["issue_iid"] for x in parsed["resultados"]], [6, 7])

    def test_valid_json_without_results_does_not_use_technical_retry(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return json.dumps({"agente": "central"}) if len(ids) > 1 else json.dumps(result(ids[0]))
        _, audit = procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertEqual(calls, [[6, 7], [6], [7]])
        self.assertFalse(any(record["technical_retry"] for record in audit["records"]))
        self.assertEqual(audit["records"][0]["num_predict"], 1060)

    def test_truncated_json_allows_exactly_one_technical_retry(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return "{" if len(calls) == 1 else wrapped(*ids)
        parsed, audit = procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=invoke)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(parsed["resultados"]), 1)
        self.assertTrue(audit["records"][0]["technical_retry"])

    def test_secondary_field_does_not_trigger_repair(self):
        calls = []
        def invoke(project, payload, context):
            calls.append(1)
            item = result(6)
            item["prioridad"] = None
            return json.dumps({"resultados": [item]})
        procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=invoke)
        self.assertEqual(len(calls), 1)

    def test_absent_story_keeps_selective_repair_reason(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return json.dumps({"resultados": []}) if len(calls) == 1 else wrapped(*ids)
        _, audit = procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=invoke)
        self.assertEqual(calls, [[6], [6]])
        self.assertEqual(audit["records"][0]["reason"], "HISTORIA_AUSENTE_EN_RESULTADOS")

    def test_failed_size_three_is_split_locally_as_two_and_one(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return "{" if len(ids) == 3 else wrapped(*ids)
        parsed, audit = procesar_central_en_sublotes("P", self.issues[:3], "C", batch_size=3, invoke=invoke)
        self.assertEqual(calls, [[6, 7, 8], [6, 7, 8], [6, 7], [8]])
        self.assertEqual(len(parsed["resultados"]), 3)
        self.assertTrue(audit["records"][0]["subdivision_applied"])

    def test_subdivision_stops_at_one(self):
        calls = []
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            calls.append(ids)
            return "{"
        parsed, audit = procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=invoke)
        self.assertEqual(calls, [[6], [6]])
        self.assertEqual(parsed["resultados"], [])
        self.assertEqual(audit["summary"]["failed_sub_batches"], 1)

    def test_subdivision_is_finite(self):
        calls = []
        def invoke(project, payload, context):
            calls.append([item["id"] for item in json.loads(payload)])
            return "{"
        _, audit = procesar_central_en_sublotes("P", self.issues[:3], "C", batch_size=3, invoke=invoke)
        self.assertLessEqual(len(calls), 10)
        self.assertEqual(audit["summary"]["incomplete_issue_ids"], [6, 7, 8])

    def test_sub_batches_execute_sequentially(self):
        active = 0
        max_active = 0
        order = []
        def invoke(project, payload, context):
            nonlocal active, max_active
            ids = [item["id"] for item in json.loads(payload)]
            active += 1
            max_active = max(max_active, active)
            order.append(ids)
            active -= 1
            return wrapped(*ids)
        procesar_central_en_sublotes("P", self.issues, "C", batch_size=2, invoke=invoke)
        self.assertEqual(max_active, 1)
        self.assertEqual(order, [[6, 7], [8, 9], [10]])

    def test_audit_accumulates_sub_batch_durations(self):
        _, service_audit = procesar_central_en_sublotes("P", self.issues, "C", batch_size=2, invoke=lambda p, raw, c: wrapped(*[x["id"] for x in json.loads(raw)]))
        audit = obtener_contadores()
        self.assertEqual(len(audit["sublotes_central"]), 3)
        self.assertAlmostEqual(
            sum(item["elapsed_seconds"] for item in audit["sublotes_central"]),
            service_audit["summary"]["elapsed_seconds"],
        )

    def test_audit_records_split_level(self):
        def invoke(project, payload, context):
            ids = [item["id"] for item in json.loads(payload)]
            return "{" if len(ids) > 1 else wrapped(*ids)
        _, audit = procesar_central_en_sublotes("P", self.issues[:2], "C", batch_size=2, invoke=invoke)
        self.assertIn(1, {record["split_level"] for record in audit["records"]})

    def test_other_agents_do_not_contain_central_batch_configuration(self):
        sources = "".join(Path(path).read_text(encoding="utf-8") for path in (
            "agents/quality_agent.py", "agents/security_agent.py", "agents/evaluator_agent.py",
        ))
        self.assertNotIn("CENTRAL_BATCH_SIZE", sources)
        self.assertNotIn("procesar_central_en_sublotes", sources)

    def test_final_central_init_structure_is_unchanged(self):
        parsed, _ = procesar_central_en_sublotes(
            "P", self.issues[:1], "C", invoke=lambda *_: wrapped(6),
        )
        self.assertEqual(set(parsed), {"agente", "milestone", "resultados"})

    def test_scoped_cache_builds_once_for_same_effective_configuration(self):
        cache = {}
        client = object()
        with patch("agents.central_agent.obtener_llm", return_value=client) as constructor:
            first = crear_cliente_ollama_central(cache, num_predict=780)
            second = crear_cliente_ollama_central(cache, num_predict=780)
        self.assertIs(first, second)
        constructor.assert_called_once()

    def test_different_num_predict_builds_only_required_second_client(self):
        cache = {}
        with patch("agents.central_agent.obtener_llm", side_effect=[object(), object()]) as constructor:
            crear_cliente_ollama_central(cache, num_predict=1060)
            crear_cliente_ollama_central(cache, num_predict=780)
            crear_cliente_ollama_central(cache, num_predict=1060)
        self.assertEqual(constructor.call_count, 2)

    def test_selective_repair_reuses_scoped_client(self):
        cache = {}
        with patch("agents.central_agent.obtener_llm", return_value=object()) as constructor:
            crear_cliente_ollama_central(cache, num_predict=780)
            crear_cliente_ollama_central(cache, num_predict=780)
        constructor.assert_called_once()

    def test_technical_retry_reuses_scoped_client(self):
        cache = {}
        with patch("agents.central_agent.obtener_llm", return_value=object()) as constructor:
            crear_cliente_ollama_central(cache, num_predict=1060)
            crear_cliente_ollama_central(cache, num_predict=1060)
        constructor.assert_called_once()

    def test_invalid_ssl_path_is_local_and_restored(self):
        original = "Z:/ruta/ca-inexistente.pem"
        with patch.dict(os.environ, {"SSL_CERT_FILE": original}, clear=False):
            with _entorno_ssl_local_ollama("http://localhost:11434") as ignored:
                self.assertNotIn("SSL_CERT_FILE", os.environ)
                self.assertEqual(ignored, ("SSL_CERT_FILE",))
            self.assertEqual(os.environ["SSL_CERT_FILE"], original)

    def test_invalid_ssl_path_is_not_ignored_for_remote_https(self):
        original = "Z:/ruta/ca-inexistente.pem"
        with patch.dict(os.environ, {"SSL_CERT_FILE": original}, clear=False):
            with _entorno_ssl_local_ollama("https://proveedor.example") as ignored:
                self.assertEqual(os.environ["SSL_CERT_FILE"], original)
                self.assertEqual(ignored, ())

    def test_ssl_environment_is_restored_when_constructor_fails(self):
        original = "Z:/ruta/ca-inexistente.pem"
        with patch.dict(os.environ, {"SSL_CERT_FILE": original}, clear=False):
            with patch("agents.central_agent.obtener_llm", side_effect=FileNotFoundError):
                with self.assertRaises(FileNotFoundError):
                    crear_cliente_ollama_central({}, num_predict=780)
            self.assertEqual(os.environ["SSL_CERT_FILE"], original)

    def test_no_global_verify_false_is_used(self):
        source = Path("agents/central_agent.py").read_text(encoding="utf-8")
        self.assertNotIn("verify=False", source)

    def test_remote_and_other_agents_do_not_use_local_ssl_sanitizer(self):
        sources = "".join(Path(path).read_text(encoding="utf-8") for path in (
            "core/llm_factory.py", "agents/quality_agent.py",
            "agents/security_agent.py", "agents/evaluator_agent.py",
        ))
        self.assertNotIn("_entorno_ssl_local_ollama", sources)
        self.assertNotIn("crear_cliente_ollama_central", sources)

    def test_durable_events_survive_invoke_exception(self):
        def failing_invoke(*_):
            raise FileNotFoundError("ruta sensible omitida")
        with self.assertRaises(FileNotFoundError):
            procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=failing_invoke)
        audit = obtener_contadores()
        events = audit["eventos_sublotes_central"]
        self.assertEqual(events[0]["event"], "central_sub_batch_start")
        self.assertTrue(any(item["event"] == "central_sub_batch_error" for item in events))
        self.assertEqual(events[-1]["event"], "central_sub_batch_end")
        self.assertEqual(events[-1]["status"], "failed")
        self.assertEqual(audit["resumen_parcial_central"]["active_sub_batch"], None)
        self.assertEqual(audit["resumen_parcial_central"]["failed_sub_batch"], 1)
        self.assertEqual(audit["resumen_parcial_central"]["active_sub_batch_at_failure"], 1)
        self.assertEqual(audit["resumen_parcial_central"]["last_error"], "OLLAMA_CLIENT_CONFIGURATION_ERROR")

    def test_partial_summary_keeps_previous_results(self):
        calls = 0
        def invoke(project, payload, context):
            nonlocal calls
            calls += 1
            ids = [item["id"] for item in json.loads(payload)]
            if calls == 1:
                return wrapped(*ids)
            raise RuntimeError("technical")
        with self.assertRaises(RuntimeError):
            procesar_central_en_sublotes("P", self.issues[:3], "C", batch_size=2, invoke=invoke)
        partial = obtener_contadores()["resumen_parcial_central"]
        self.assertEqual(partial["received"], [6, 7])
        self.assertGreater(partial["elapsed_seconds"], 0)

    def test_audit_never_stores_prompt_response_or_secret(self):
        def failing_invoke(*_):
            raise RuntimeError("technical")
        with self.assertRaises(RuntimeError):
            procesar_central_en_sublotes("P", self.issues[:1], "C", invoke=failing_invoke)
        serialized = json.dumps(obtener_contadores()["eventos_sublotes_central"])
        self.assertNotIn("prompt", serialized.casefold())
        self.assertNotIn("response", serialized.casefold())
        self.assertNotIn("api_key", serialized.casefold())

    def test_incomplete_story_stops_before_downstream_nodes(self):
        parsed = {"agente": "central", "milestone": "M", "resultados": [result(6)]}
        state = {
            "project_name": "P", "sprint_context": "C",
            "issues_data": self.issues[:2], "validation_errors": [],
            "content_validation_errors": {},
        }
        with patch("core.graph.procesar_central_en_sublotes", return_value=(parsed, {"records": []})), \
             patch("core.graph._persistir_fallo_central") as persist:
            with self.assertRaises(CentralIncompleteBatchError) as raised:
                nodo_central_inicial(state)
        self.assertEqual(raised.exception.missing_issue_ids, [7])
        self.assertEqual(raised.exception.category, "CENTRAL_INCOMPLETE_BATCH")
        persist.assert_called_once()


if __name__ == "__main__":
    unittest.main()
