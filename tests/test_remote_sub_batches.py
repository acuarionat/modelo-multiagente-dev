import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agents.llm_invocation import (
    InvocationResult,
    RemoteLLMError,
    invocar_con_fallback,
    rechazar_respuesta_remota_truncada,
)
from core.execution_summary import (
    build_sanitized_execution_summary,
    persist_sanitized_execution_summary,
)
from core.graph import _ejecutar_sublotes_remotos, construir_grafo
from core.llm_factory import LLMSelection
from core.performance_audit import obtener_contadores, reiniciar_contadores
from core.remote_execution import (
    RemoteBatchError,
    RemotePacer,
    dividir_payload_en_sublotes,
    remote_batch_size,
    remote_inter_call_delay,
    remote_single_attempt,
    validar_sublote_estricto,
)


def payload(ids=(6, 7, 8, 9, 10)):
    return {
        "agente": "central",
        "milestone": "Fixture",
        "resultados": [{"issue_iid": iid, "historia_id": f"HU-{iid:03d}"} for iid in ids],
    }


class FakeMessage:
    def __init__(self, content="{}", finish_reason="stop"):
        self.content = content
        self.response_metadata = {"finish_reason": finish_reason}


class RemoteSubBatchTests(unittest.TestCase):
    def setUp(self):
        reiniciar_contadores()

    def test_quality_and_security_split_five_as_2_2_1(self):
        batches = dividir_payload_en_sublotes(payload(), 2)
        self.assertEqual([[x["issue_iid"] for x in b["resultados"]] for b in batches], [[6, 7], [8, 9], [10]])
        self.assertTrue(all(b["agente"] == "central" and b["milestone"] == "Fixture" for b in batches))

    def test_strict_association_restores_original_order(self):
        parsed = {"resultados": [{"issue_iid": 7}, {"issue_iid": 6}]}
        self.assertEqual([x["issue_iid"] for x in validar_sublote_estricto(parsed, [6, 7], agent="Calidad", sub_batch=1)], [6, 7])

    def test_strict_association_rejects_unexpected_duplicate_and_missing(self):
        cases = [
            ({"resultados": [{"issue_iid": 6}, {"issue_iid": 8}]}, "REMOTE_UNEXPECTED_ISSUE"),
            ({"resultados": [{"issue_iid": 6}, {"issue_iid": 6}]}, "REMOTE_DUPLICATE_ISSUE"),
            ({"resultados": [{"issue_iid": 6}]}, "REMOTE_INCOMPLETE_BATCH"),
        ]
        for parsed, category in cases:
            with self.subTest(category=category), self.assertRaises(RemoteBatchError) as ctx:
                validar_sublote_estricto(parsed, [6, 7], agent="Calidad", sub_batch=1)
            self.assertEqual(ctx.exception.category, category)

    def test_invalid_contract_is_rejected(self):
        with self.assertRaises(RemoteBatchError) as ctx:
            validar_sublote_estricto({"resultados": "bad"}, [6], agent="Seguridad", sub_batch=1)
        self.assertEqual(ctx.exception.category, "REMOTE_CONTRACT_ERROR")

    def test_consolidation_only_returns_after_all_batches(self):
        calls = []
        def invoke(raw, batch):
            ids = [item["issue_iid"] for item in json.loads(raw)["resultados"]]
            calls.append(ids)
            if batch == 3:
                raise RemoteBatchError("REMOTE_INVALID_RESPONSE", agent="Calidad", sub_batch=batch, issue_ids=ids)
            return json.dumps({"agente": "calidad", "resultados": [{"issue_iid": iid} for iid in reversed(ids)]})
        with patch("core.graph.validar_respuesta_lote", return_value=[]), self.assertRaises(RemoteBatchError):
            _ejecutar_sublotes_remotos(json.dumps(payload()), "Calidad", 2, invoke)
        self.assertEqual(calls, [[6, 7], [8, 9], [10]])
        audit = obtener_contadores()
        self.assertEqual(audit["resumen_parcial_remoto"]["completed_issue_ids"], [6, 7, 8, 9])

    def test_successful_consolidation_preserves_order(self):
        def invoke(raw, _batch):
            ids = [item["issue_iid"] for item in json.loads(raw)["resultados"]]
            return json.dumps({"agente": "calidad", "resultados": [{"issue_iid": iid} for iid in reversed(ids)]})
        with patch("core.graph.validar_respuesta_lote", return_value=[]):
            result = _ejecutar_sublotes_remotos(json.dumps(payload()), "Calidad", 2, invoke)
        self.assertEqual([x["issue_iid"] for x in result["resultados"]], [6, 7, 8, 9, 10])

    def test_stop_is_accepted_and_length_is_rejected_even_with_valid_json(self):
        stop = InvocationResult(FakeMessage(finish_reason="stop"), "groq", "model")
        rechazar_respuesta_remota_truncada(agent_name="Quality", result=stop, metadata={"finish_reason": "stop", "response_chars": 2}, sub_batch=1, issue_ids=[6], max_completion_tokens=2048)
        length = InvocationResult(FakeMessage(finish_reason="length"), "groq", "model")
        with self.assertRaises(RemoteLLMError) as ctx:
            rechazar_respuesta_remota_truncada(agent_name="Quality", result=length, metadata={"finish_reason": "length", "response_chars": 2}, sub_batch=1, issue_ids=[6], max_completion_tokens=2048)
        self.assertEqual(ctx.exception.category, "REMOTE_TRUNCATED_RESPONSE")
        self.assertEqual(ctx.exception.response_chars, 2)

    def test_remote_nodes_do_not_use_repair_helper_in_remote_branch(self):
        source = inspect.getsource(_ejecutar_sublotes_remotos)
        self.assertNotIn("_analizar_con_un_reintento", source)
        self.assertNotIn("_validar_y_reparar", source)
        self.assertNotIn("fallback", source.casefold())

    def test_remote_single_attempt_forces_zero_and_restores_configuration(self):
        with patch.dict("os.environ", {"REMOTE_LLM_MAX_RETRIES": "3", "ENABLE_LOCAL_FALLBACK": "true"}):
            with remote_single_attempt():
                self.assertEqual(__import__("os").environ["REMOTE_LLM_MAX_RETRIES"], "0")
                self.assertEqual(__import__("os").environ["ENABLE_LOCAL_FALLBACK"], "false")
            self.assertEqual(__import__("os").environ["REMOTE_LLM_MAX_RETRIES"], "3")
            self.assertEqual(__import__("os").environ["ENABLE_LOCAL_FALLBACK"], "true")

    def test_delay_zero_and_invalid_defaults(self):
        with patch.dict("os.environ", {"REMOTE_INTER_CALL_DELAY_SECONDS": "0"}):
            self.assertEqual(remote_inter_call_delay(), 0)
        with patch.dict("os.environ", {"REMOTE_INTER_CALL_DELAY_SECONDS": "bad"}):
            self.assertEqual(remote_inter_call_delay(), 60)
        with patch.dict("os.environ", {"REMOTE_QUALITY_BATCH_SIZE": "0", "REMOTE_SECURITY_BATCH_SIZE": "x"}):
            self.assertEqual(remote_batch_size("quality"), 2)
            self.assertEqual(remote_batch_size("security"), 2)

    def test_pacer_uses_only_remaining_time_and_injected_clock_sleep(self):
        ticks = iter([100.0, 110.0, 140.0])
        sleeps = []
        pacer = RemotePacer(clock=lambda: next(ticks), sleeper=sleeps.append)
        self.assertEqual(pacer.before_call("groq", "Quality"), 0)
        pacer.after_call("groq", "Quality")
        with patch.dict("os.environ", {"REMOTE_INTER_CALL_DELAY_SECONDS": "60"}):
            self.assertEqual(pacer.before_call("groq", "Security"), 50)
        self.assertEqual(sleeps, [50])
        pacer.after_call("groq", "Security")

    def test_rate_limit_keeps_only_sanitized_retry_after(self):
        response = Mock(status_code=429, headers={"retry-after": "12.5", "authorization": "secret"})
        exc = RuntimeError("body secret")
        exc.response = response
        selection = LLMSelection(Mock(), "groq", "model", False)
        with self.assertRaises(RemoteLLMError) as ctx:
            invocar_con_fallback("Quality", selection, lambda: (_ for _ in ()).throw(exc), lambda: (None, "local"))
        error = ctx.exception
        self.assertEqual((error.category, error.http_status, error.retry_after_seconds), ("REMOTE_RATE_LIMIT", 429, 12.5))
        self.assertFalse(hasattr(error, "headers"))
        self.assertNotIn("secret", str(error))

    def test_audit_registers_start_end_and_error_without_semantic_content(self):
        def invoke(_raw, _batch):
            raise RemoteBatchError("REMOTE_INVALID_RESPONSE", agent="Seguridad", sub_batch=1, issue_ids=[6])
        with self.assertRaises(RemoteBatchError):
            _ejecutar_sublotes_remotos(json.dumps(payload((6,))), "Seguridad", 2, invoke)
        events = obtener_contadores()["eventos_sublotes_remotos"]
        self.assertEqual([x["event"] for x in events], ["remote_sub_batch_start", "remote_sub_batch_call_start", "remote_sub_batch_error", "remote_sub_batch_end"])
        serialized = json.dumps(events).casefold()
        self.assertNotIn("recomendacion", serialized)
        self.assertNotIn("prompt", serialized)

    def test_partial_summary_is_persisted_and_sanitized(self):
        error = RemoteLLMError("REMOTE_RATE_LIMIT", http_status=429, retry_after_seconds=10, agent="Quality", sub_batch=2, issue_ids=[8, 9])
        audit = {"llamadas_remotas": 1, "eventos_sublotes_remotos": [], "quality_input_prepared": {"by_issue": [{"issue_iid": 6}]}}
        summary = build_sanitized_execution_summary(execution_id="fixture", estado="incompleto", etapa_alcanzada="Quality", auditoria=audit, historias_esperadas=[6, 7, 8], historias_completas=[6], error=error, artefactos={}, gitlab_usado=False)
        summary["ignored_secret"] = "GROQ_API_KEY"  # caller-only field proves persistence is exact
        summary.pop("ignored_secret")
        with tempfile.TemporaryDirectory() as directory:
            path = persist_sanitized_execution_summary(summary, directory)
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["historias_pendientes"], [7, 8])
        self.assertEqual(loaded["error_category"], "REMOTE_RATE_LIMIT")
        self.assertNotIn("prompt", json.dumps(loaded).casefold())
        self.assertTrue(loaded["resumen_json_temporal"].endswith("fixture-summary.json"))

    def test_app_preserves_partial_summary_path(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('st.session_state["last_partial_summary_path"]', source)
        self.assertIn('getattr(e, "summary_path", None)', source)

    def test_graph_topology_has_not_added_nodes(self):
        source = inspect.getsource(construir_grafo)
        self.assertEqual(source.count("workflow.add_node("), 5)
        for name in ("Central_Init", "Quality", "Security", "Evaluator", "Central_Final"):
            self.assertIn(f'workflow.add_node("{name}"', source)


if __name__ == "__main__":
    unittest.main()
