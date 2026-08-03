import os
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from types import SimpleNamespace

from core.batch_contract import (
    _evidencia_seguridad_contexto, ajustar_veredicto_determinista,
    calcular_metricas_agente, completar_requerimientos_explicitos_faltantes,
    normalizar_capitalizacion_requerimiento, normalizar_presentacion_requerimientos,
    validar_contenido_agente, validar_respuesta_lote,
)
from core.performance_audit import (
    auditar_llamada_agente, obtener_contadores, reiniciar_contadores,
    registrar_motivo_reparacion,
)
from core.graph import _validar_y_reparar, diagnosticar_reparacion_central
from agents.security_agent import parametros_auditoria_seguridad
from scripts.test_hybrid_flow import HU010, controlled_parser
from tests.test_remote_contract_diagnostic import quality_fixture


def security_fixture():
    return {
        "agente": "seguridad",
        "resultados": [{
            "issue_iid": 10,
            "historia_id": "HU-010",
            "metricas": {
                "cobertura_seguridad": {
                    "aspectos_aplicables": ["a", "b", "c", "d"],
                    "aspectos_documentados": ["a", "b", "c", "d"],
                    "aspectos_parciales": [], "aspectos_faltantes": [],
                    "aspectos_inferidos": [], "justificacion": "Evidencia específica.",
                    "recomendacion": "",
                },
                "clasificacion_datos": {
                    "datos_identificados": ["dato 1", "dato 2"],
                    "datos_clasificados": [], "datos_sin_clasificacion": ["dato 1", "dato 2"],
                    "clasificaciones_inferidas": [], "justificacion": "Evidencia específica.",
                    "recomendacion": "Clasificar los datos.",
                },
            },
        }],
    }


class ControlledHybridFlowTests(unittest.TestCase):
    @staticmethod
    def _central_result(priority="Alta"):
        return {
            "agente": "central", "resultados": [{
                "issue_iid": 10, "historia_id": "HU-010",
                "actor": "Paciente", "objetivo": "Liberar el horario reservado",
                "requerimientos": [{
                    "temp_id": "TMP-1", "nombre": "Cancelar cita",
                    "descripcion_formal": "El sistema deberá permitir cancelar una cita.",
                    "tipo": "RF", "origen": "Cancelar una cita",
                    "justificacion": "Funcionalidad explícita.", "prioridad": priority,
                    "procedencia": "explícita — funcionalidad",
                }],
            }],
        }

    def test_central_missing_story_diagnostic_is_sanitized_and_critical(self):
        diagnostic = diagnosticar_reparacion_central(
            {"agente": "central", "resultados": []}, {10: "HU-010"},
        )
        self.assertEqual(diagnostic, [{
            "issue_iid": 10,
            "historia_id": "HU-010",
            "campos_fallidos": [{
                "campo": "resultados[issue_iid=10]",
                "tipo_esperado": "objeto",
                "tipo_recibido": "ausente",
                "valor": "ausente",
            }],
            "categoria_error": "HISTORIA_AUSENTE_EN_RESULTADOS",
            "reparable_en_python": False,
            "reparacion_llm_necesaria": True,
        }])

    def test_secondary_central_field_does_not_request_repair(self):
        response = self._central_result(priority=None)
        repair = Mock()
        errors, content_errors = _validar_y_reparar(
            response, {10}, "Central", repair,
        )
        repair.assert_not_called()
        self.assertEqual(errors, [])
        self.assertIn("prioridad", " ".join(content_errors[10]))

    def test_critical_missing_central_story_preserves_repair(self):
        repaired = self._central_result()
        repair = Mock(return_value=__import__("json").dumps(repaired, ensure_ascii=False))
        response = {"agente": "central", "resultados": []}
        errors, _ = _validar_y_reparar(response, {10}, "Central", repair)
        repair.assert_called_once_with([10])
        self.assertEqual(errors, [])
        self.assertEqual(response["resultados"][0]["issue_iid"], 10)

    def test_central_audit_accumulates_calls_and_repair_reason(self):
        reiniciar_contadores()
        with patch("core.performance_audit.time.perf_counter", side_effect=[0.0, 2.0, 2.0, 5.0]):
            with auditar_llamada_agente("Central_Init_Batch", "", ""):
                pass
            registrar_motivo_reparacion(
                "Central_Init_Batch", [10], "HISTORIA_AUSENTE_EN_RESULTADOS",
            )
            with auditar_llamada_agente("Central_Init_Batch", "", ""):
                pass
        audit = obtener_contadores()
        self.assertEqual(audit["por_agente"]["Central_Init_Batch"], 2)
        self.assertEqual(audit["duraciones_llamadas_por_agente"]["Central_Init_Batch"], [2.0, 3.0])
        self.assertEqual(audit["duraciones_por_agente"]["Central_Init_Batch"], 5.0)
        self.assertEqual(audit["motivos_reparacion"]["Central_Init_Batch"], [{
            "issue_ids": [10], "motivo": "HISTORIA_AUSENTE_EN_RESULTADOS",
        }])

    def test_requirement_capitalization_is_localized_and_preserves_acronyms(self):
        cases = {
            "El sistema deberá permitir que el paciente CANCELLE una cita médica.":
                "El sistema deberá permitir que el paciente cancele una cita médica.",
            "El sistema deberá EXPORTAR PDF.": "El sistema deberá exportar PDF.",
            "El sistema deberá GENERAR reportes.": "El sistema deberá generar reportes.",
            "El sistema deberá generar un PDF.": "El sistema deberá generar un PDF.",
            "La API deberá responder.": "La API deberá responder.",
            "El sistema deberá registrar pacientes.": "El sistema deberá registrar pacientes.",
            "El sistema deberá permitir que el paciente cancela su cita médica.":
                "El sistema deberá permitir que el paciente cancele su cita médica.",
            "El sistema deberá permitir que el usuario registre una solicitud.":
                "El sistema deberá permitir que el usuario registre una solicitud.",
            "El sistema deberá permitir que el administrador genere reportes.":
                "El sistema deberá permitir que el administrador genere reportes.",
            "El sistema deberá permitir que el empleado solicite vacaciones.":
                "El sistema deberá permitir que el empleado solicite vacaciones.",
        }
        for original, expected in cases.items():
            with self.subTest(original=original):
                self.assertEqual(normalizar_capitalizacion_requerimiento(original), expected)
        requirement = {
            "temp_id": "RF-001", "tipo": "RNF", "nombre": "EXPORTAR PDF",
            "descripcion_formal": "El sistema deberá EXPORTAR PDF.",
            "procedencia": "explícita — funcionalidad",
        }
        normalizar_presentacion_requerimientos([requirement])
        self.assertEqual(requirement["temp_id"], "RF-001")
        self.assertEqual(requirement["tipo"], "RNF")
        self.assertEqual(requirement["nombre"], "exportar PDF")

    def test_observed_availability_sentence_is_corrected_exactly_once(self):
        incorrect = (
            "El sistema deberá actualizar la disponibilidad después del paciente "
            "de haber programado una cita."
        )
        corrected = (
            "El sistema deberá actualizar la disponibilidad después de que el "
            "paciente programe una cita."
        )
        self.assertEqual(normalizar_capitalizacion_requerimiento(incorrect), corrected)
        self.assertEqual(normalizar_capitalizacion_requerimiento(corrected), corrected)
        unrelated = "El sistema deberá mostrar únicamente horarios disponibles."
        self.assertEqual(normalizar_capitalizacion_requerimiento(unrelated), unrelated)

    def test_quality_contract_is_valid_before_index_and_complete_after_calculation(self):
        response = quality_fixture()
        self.assertEqual(validar_contenido_agente(response, "Calidad"), {})
        self.assertIn("índice inválido", validar_respuesta_lote(response, {10}, "Calidad")[0])
        calcular_metricas_agente(response, "Calidad", {10: HU010})
        self.assertEqual(validar_respuesta_lote(response, {10}, "Calidad"), [])

    def test_security_contract_is_valid_before_index_and_complete_after_calculation(self):
        response = security_fixture()
        self.assertEqual(validar_contenido_agente(response, "Seguridad"), {})
        self.assertIn("índice inválido", validar_respuesta_lote(response, {10}, "Seguridad")[0])
        calcular_metricas_agente(response, "Seguridad", {10: HU010})
        self.assertEqual(validar_respuesta_lote(response, {10}, "Seguridad"), [])
        self.assertEqual(response["resultados"][0]["indice"], 0.5)
        metricas = response["resultados"][0]["metricas"]
        self.assertEqual(len(metricas["cobertura_seguridad"]["aspectos_aplicables"]), 4)
        self.assertEqual(len(metricas["cobertura_seguridad"]["aspectos_documentados"]), 4)
        self.assertEqual(len(metricas["clasificacion_datos"]["datos_identificados"]), 2)

    def test_controlled_remote_parse_error_does_not_retry(self):
        retry = Mock()
        with self.assertRaises(ValueError):
            controlled_parser(Mock(), "{", "Calidad", retry)
        retry.assert_not_called()

    def test_two_remote_calls_are_counted_without_fallback(self):
        reiniciar_contadores()
        for agent in ("Quality", "Security"):
            with auditar_llamada_agente(agent, "", "", provider="groq", model_params={"model": "mock"}):
                pass
        audit = obtener_contadores()
        self.assertEqual(audit["llamadas_remotas"], 2)
        self.assertEqual(audit["llamadas_ollama"], 0)
        self.assertEqual(audit["fallbacks_locales"], 0)

    def test_fixture_preserves_identity_and_explicit_24_hour_rule(self):
        self.assertEqual(HU010["actor"], "Paciente")
        self.assertEqual(HU010["objetivo"], "Liberar el horario reservado")
        self.assertIn("menos de 24 horas", HU010["restricciones"][0])
        self.assertNotIn("Ninguna", str(HU010))

    def test_security_prefix_is_removed_and_two_data_are_separate(self):
        context = {"seguridad": {
            "autenticacion": "Definida", "autorizacion_roles": "Paciente",
            "auditoria": "Definida", "maneja_datos_sensibles": "Sí: nombre y documento",
            "tipos_datos_sensibles": ["Sí: Nombre ficticio", "Documento ficticio"],
        }}
        applicable, documented, data, classified = _evidencia_seguridad_contexto(context)
        self.assertEqual((len(applicable), len(documented)), (4, 4))
        self.assertEqual(data, ["Nombre ficticio", "Documento ficticio"])
        self.assertEqual(classified, [])

    def test_security_below_meta_forces_correct_even_if_evaluator_approves(self):
        evaluation = {"veredicto": "APROBADO", "conclusion": "Texto conservado."}
        quality = {"indice": 1.0, "estado_medicion": "evaluable", "metricas": {}, "indicador": {"estado": "Cumple"}}
        security = {"indice": 0.5, "estado_medicion": "evaluable", "metricas": {}, "lot_recomendado": "LoT-2", "indicador": {"estado": "No cumple"}}
        ajustar_veredicto_determinista({}, quality, security, evaluation)
        self.assertEqual(evaluation["veredicto"], "CORREGIR")
        self.assertEqual(evaluation["veredicto_original"], "APROBADO")

    def test_inferred_classifications_do_not_increment_ms02(self):
        response = security_fixture()
        ms02 = response["resultados"][0]["metricas"]["clasificacion_datos"]
        ms02["datos_identificados"] = ["Nombre ficticio", "Documento ficticio"]
        ms02["datos_clasificados"] = ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"]
        result = response["resultados"][0]
        calcular_metricas_agente(response, "Seguridad", {10: HU010})
        normalized = result["metricas"]["clasificacion_datos"]
        self.assertEqual(normalized["datos_clasificados"], [])
        self.assertEqual(normalized["datos_sin_clasificacion"], ["Nombre ficticio", "Documento ficticio"])
        self.assertEqual(normalized["clasificaciones_inferidas"], [
            "Nombre ficticio → PERSONAL", "Documento ficticio → PERSONAL",
        ])
        self.assertEqual(normalized["valor"], 0.0)
        self.assertEqual(result["indice"], 0.5)
        self.assertEqual(result["observaciones"], (
            "Los cuatro aspectos de seguridad aplicables están documentados. Sin embargo, "
            "los dos datos identificados no cuentan con clasificación explícita."
        ))
        self.assertIn("Clasificados explícitamente: ninguno", normalized["justificacion"])
        self.assertNotIn("2 de 2 datos identificados tienen clasificación explícita", normalized["justificacion"])

    def test_explicit_original_classification_increments_ms02_without_recommendation(self):
        response = security_fixture()
        context = {**HU010, "seguridad": {
            **HU010["seguridad"],
            "tipos_datos_sensibles": ["Nombre ficticio: PERSONAL", "Documento ficticio: PERSONAL"],
        }}
        calcular_metricas_agente(response, "Seguridad", {10: context})
        ms02 = response["resultados"][0]["metricas"]["clasificacion_datos"]
        self.assertEqual(len(ms02["datos_clasificados"]), 2)
        self.assertEqual(ms02["valor"], 1.0)
        self.assertEqual(ms02["datos_sin_clasificacion"], [])
        self.assertEqual(ms02["recomendacion"], "")

    def test_cancel_requirement_is_deduplicated_and_24_hour_rule_is_rf(self):
        central = [{
            "nombre": "Cancelar cita", "descripcion_formal": "El sistema deberá permitir la cancelación de una cita médica.",
            "tipo": "RF", "origen": "Cancelar una cita", "procedencia": "explícita — funcionalidad",
        }]
        result = completar_requerimientos_explicitos_faltantes(central, HU010)
        cancellation = [x for x in result if "24 horas" not in x["descripcion_formal"]]
        rule = [x for x in result if "24 horas" in x["descripcion_formal"]]
        self.assertEqual(len(cancellation), 1)
        self.assertEqual(len(rule), 1)
        self.assertEqual(rule[0]["tipo"], "RF")
        self.assertEqual(rule[0]["descripcion_formal"], "El sistema deberá impedir la cancelación de una cita cuando falten menos de 24 horas para su realización.")

    def test_mc01_exposes_a_missing_and_b_specified(self):
        response = quality_fixture()
        response["resultados"][0]["metricas"]["cobertura_funcional"]["funciones_faltantes"] = []
        calcular_metricas_agente(response, "Calidad", {10: HU010})
        justification = response["resultados"][0]["metricas"]["cobertura_funcional"]["justificacion"]
        self.assertIn("A=0 funciones faltantes", justification)
        self.assertIn("B=1 funciones especificadas", justification)

    def test_remote_security_audit_uses_2048(self):
        with patch.dict(os.environ, {"REMOTE_SECURITY_MAX_COMPLETION_TOKENS": "2048"}):
            params = parametros_auditoria_seguridad(SimpleNamespace(provider="groq", model="remote"), 800)
        self.assertEqual(params["max_completion_tokens"], 2048)
        self.assertNotIn("max_tokens", params)

    def test_productive_agents_do_not_contain_fixture_switch(self):
        sources = "".join(Path(path).read_text(encoding="utf-8") for path in (
            "agents/central_agent.py", "agents/evaluator_agent.py", "core/graph.py",
        ))
        self.assertNotIn("CONTROLLED_HYBRID_RUN", sources)


if __name__ == "__main__":
    unittest.main()
