import importlib
import json
import logging
import os
import sys
import types
import unittest
from unittest.mock import patch


class FakeChatOllama:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeChatGroq:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


sys.modules.setdefault(
    "langchain_ollama", types.SimpleNamespace(ChatOllama=FakeChatOllama),
)
sys.modules.setdefault(
    "langchain_groq", types.SimpleNamespace(ChatGroq=FakeChatGroq),
)

import core.llm_factory as llm_factory
from agents.llm_invocation import (
    InvocationResult, RemoteLLMError, invocar_con_fallback,
    obtener_ultimos_metadatos, registrar_resumen_respuesta,
)
from core.batch_contract import analizar_respuesta_lote
from core.performance_audit import (
    auditar_llamada_agente,
    obtener_contadores,
    reiniciar_contadores,
)


REMOTE_ENV = {
    "ENABLE_REMOTE_LLM": "true",
    "ENABLE_LOCAL_FALLBACK": "true",
    "LLM_PROVIDER_QUALITY": "groq",
    "LLM_PROVIDER_SECURITY": "groq",
    "GROQ_API_KEY": "secret-test-value",
    "GROQ_MODEL_QUALITY": "quality-model",
    "GROQ_MODEL_SECURITY": "security-model",
}


class HTTPErrorForTest(Exception):
    def __init__(self, status_code):
        super().__init__("secret-test-value must never be logged")
        self.status_code = status_code


class TimeoutForTest(Exception):
    pass


class HybridLLMTests(unittest.TestCase):
    def setUp(self):
        reiniciar_contadores()

    def select(self, agent):
        return llm_factory.obtener_llm_para_agente(
            agent, json_mode=True, num_predict=100, num_ctx=8192, temperature=0.1,
        )

    @patch.dict(os.environ, {"ENABLE_REMOTE_LLM": "false"}, clear=True)
    def test_central_and_evaluator_are_always_local(self):
        self.assertEqual(self.select("central").provider, "ollama")
        self.assertEqual(self.select("evaluator").provider, "ollama")

    @patch.dict(os.environ, REMOTE_ENV, clear=True)
    def test_quality_and_security_select_remote(self):
        quality = self.select("quality")
        security = self.select("security")
        self.assertEqual(quality.provider, "groq")
        self.assertEqual(quality.model, "quality-model")
        self.assertEqual(security.provider, "groq")
        self.assertEqual(security.model, "security-model")
        for selection in (quality, security):
            kwargs = selection.llm.kwargs
            self.assertEqual(kwargs["model_kwargs"]["max_completion_tokens"], 2048)
            self.assertEqual(kwargs["reasoning_effort"], "low")
            self.assertEqual(kwargs["reasoning_format"], "hidden")
            self.assertEqual(kwargs["model_kwargs"]["response_format"], {"type": "json_object"})
            self.assertNotIn("include_reasoning", kwargs)
            self.assertNotIn("max_tokens", kwargs)

    @patch.dict(os.environ, {**REMOTE_ENV, "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "3072"}, clear=True)
    def test_remote_budget_is_separate_from_local_num_predict(self):
        remote = self.select("quality")
        self.assertEqual(remote.llm.kwargs["model_kwargs"]["max_completion_tokens"], 3072)
        with patch.dict(os.environ, {"ENABLE_REMOTE_LLM": "false"}, clear=True):
            local = self.select("quality")
        local_budget = getattr(local.llm, "num_predict", None)
        if local_budget is None:
            local_budget = local.llm.kwargs["num_predict"]
        self.assertEqual(local_budget, 100)

    @patch.dict(os.environ, {**REMOTE_ENV, "REMOTE_QUALITY_MAX_COMPLETION_TOKENS": "0"}, clear=True)
    def test_invalid_remote_budget_is_controlled_configuration_error(self):
        with self.assertRaises(llm_factory.LLMConfigurationError):
            self.select("quality")

    @patch.dict(os.environ, {**REMOTE_ENV, "ENABLE_REMOTE_LLM": "false"}, clear=True)
    def test_remote_disabled_uses_local(self):
        self.assertEqual(self.select("quality").provider, "ollama")
        self.assertEqual(self.select("security").provider, "ollama")

    @patch.dict(os.environ, {
        **REMOTE_ENV, "GROQ_API_KEY": "", "ENABLE_LOCAL_FALLBACK": "true",
    }, clear=True)
    def test_missing_configuration_with_fallback_uses_local(self):
        self.assertEqual(self.select("quality").provider, "ollama")
        self.assertEqual(obtener_contadores()["fallbacks_locales"], 1)

    @patch.dict(os.environ, {
        **REMOTE_ENV, "GROQ_API_KEY": "", "ENABLE_LOCAL_FALLBACK": "false",
    }, clear=True)
    def test_missing_configuration_without_fallback_is_controlled_error(self):
        with self.assertRaises(llm_factory.LLMConfigurationError):
            self.select("quality")

    @patch.dict(os.environ, REMOTE_ENV, clear=True)
    def test_supported_technical_errors_use_one_local_fallback(self):
        for error in (TimeoutForTest(), HTTPErrorForTest(401), HTTPErrorForTest(429), HTTPErrorForTest(503)):
            with self.subTest(error=type(error).__name__, status=getattr(error, "status_code", None)):
                reiniciar_contadores()
                calls = {"remote": 0, "local": 0}
                selection = self.select("quality")

                def remote():
                    calls["remote"] += 1
                    raise error

                def local():
                    calls["local"] += 1
                    return "local-response", "local-model"

                result = invocar_con_fallback("Quality", selection, remote, local)
                self.assertEqual(result.response, "local-response")
                self.assertTrue(result.used_fallback)
                self.assertEqual(calls, {"remote": 1, "local": 1})
                self.assertEqual(obtener_contadores()["fallbacks_locales"], 1)

    @patch.dict(os.environ, {**REMOTE_ENV, "ENABLE_LOCAL_FALLBACK": "false"}, clear=True)
    def test_remote_error_without_fallback_is_sanitized(self):
        selection = self.select("quality")
        with self.assertRaisesRegex(RemoteLLMError, "REMOTE_AUTH_ERROR") as captured:
            invocar_con_fallback(
                "Quality", selection,
                lambda: (_ for _ in ()).throw(HTTPErrorForTest(401)),
                lambda: ("unused", "local-model"),
            )
        self.assertNotIn("secret-test-value", str(captured.exception))

    @patch.dict(os.environ, REMOTE_ENV, clear=True)
    def test_semantic_or_unclassified_error_does_not_trigger_fallback(self):
        selection = self.select("quality")
        calls = {"local": 0}

        def local():
            calls["local"] += 1
            return "unused", "local-model"

        with self.assertRaises(ValueError):
            invocar_con_fallback(
                "Quality", selection,
                lambda: (_ for _ in ()).throw(ValueError("invalid semantic result")),
                local,
            )
        self.assertEqual(calls["local"], 0)
        self.assertEqual(obtener_contadores()["fallbacks_locales"], 0)

    @patch.dict(os.environ, REMOTE_ENV, clear=True)
    def test_logs_do_not_expose_api_key(self):
        selection = self.select("quality")
        with self.assertLogs("agents.llm_invocation", level=logging.WARNING) as logs:
            invocar_con_fallback(
                "Quality", selection,
                lambda: (_ for _ in ()).throw(HTTPErrorForTest(429)),
                lambda: ("local", "local-model"),
            )
        self.assertNotIn("secret-test-value", "\n".join(logs.output))

    def test_audit_counts_local_remote_and_fallback(self):
        with auditar_llamada_agente("Central", "", "", provider="ollama"):
            pass
        with auditar_llamada_agente(
            "Quality", "", "", model_params={"model": "remote"}, provider="groq",
        ):
            pass
        counters = obtener_contadores()
        self.assertEqual(counters["llamadas_ollama"], 1)
        self.assertEqual(counters["llamadas_remotas"], 1)

    def test_finish_reason_is_optional_technical_metadata(self):
        response = types.SimpleNamespace(
            content='{"agente":"calidad","resultados":[]}',
            response_metadata={"finish_reason": "stop", "model_name": "remote-model"},
        )
        result = InvocationResult(response, "groq", "configured-model", False)
        registrar_resumen_respuesta("Quality", result, response.content)
        metadata = obtener_ultimos_metadatos("Quality")
        self.assertEqual(metadata["finish_reason"], "stop")
        self.assertEqual(metadata["model"], "remote-model")

        response_without_metadata = types.SimpleNamespace(content="{}")
        registrar_resumen_respuesta(
            "Security", InvocationResult(response_without_metadata, "groq", "model", False), "{}",
        )
        self.assertIsNone(obtener_ultimos_metadatos("Security")["finish_reason"])

    def test_diagnostic_agent_selector_is_explicit(self):
        from scripts.test_remote_agents import selected_agents
        self.assertEqual(selected_agents(False, None), [])
        self.assertEqual(selected_agents(True, "quality"), ["quality"])
        self.assertEqual(selected_agents(True, "security"), ["security"])
        with self.assertRaises(ValueError):
            selected_agents(True, None)

    def test_existing_parser_and_contract_are_preserved(self):
        payload = {"agente": "calidad", "resultados": [{"issue_iid": 6, "metricas": {}}]}
        parsed = analizar_respuesta_lote(json.dumps(payload), "Calidad")
        self.assertEqual(parsed, payload)

if __name__ == "__main__":
    unittest.main()
