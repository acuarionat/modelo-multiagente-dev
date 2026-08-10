import json

from agents.evaluator_agent import evaluar_reportes
from agents.llm_invocation import obtener_ultimos_metadatos
from core.batch_contract import analizar_respuesta_lote
from core.llm_factory import obtener_llm_para_agente


# ---------------------------------------------------------
# Provider resuelto por la fábrica
# ---------------------------------------------------------

selection = obtener_llm_para_agente(
    "evaluator", json_mode=True, num_predict=2048, num_ctx=8192, temperature=0.1,
)

print("\n" + "=" * 70)
print("CONFIGURACIÓN EVALUADOR")
print("=" * 70)

print("\nProvider:", selection.provider)
print("Model:", selection.model)


# ---------------------------------------------------------
# Entrada controlada (Calidad + Seguridad de una sola historia)
# ---------------------------------------------------------

quality_reports = json.dumps({
    "agente": "calidad",
    "resultados": [
        {
            "issue_iid": 1,
            "historia_id": "HU-001",
            "metricas": {
                "cobertura_funcional": {
                    "codigo": "MC-01", "valor": 1.0,
                    "justificacion": "Todas las funciones necesarias están documentadas.",
                },
                "adecuacion_funcional": {
                    "codigo": "MC-02", "valor": 1.0,
                    "justificacion": "Las funciones documentadas se alinean con el objetivo declarado.",
                },
            },
            "observaciones": "Entrada controlada para validar el Evaluador con NVIDIA.",
        }
    ],
}, ensure_ascii=False)

security_reports = json.dumps({
    "agente": "seguridad",
    "resultados": [
        {
            "issue_iid": 1,
            "historia_id": "HU-001",
            "indice": 1.0,
            "controles_evaluados": [],
            "observaciones": "Sin hallazgos de seguridad pendientes en esta entrada controlada.",
        }
    ],
}, ensure_ascii=False)


# ---------------------------------------------------------
# Ejecutar exclusivamente el Evaluador
# ---------------------------------------------------------

respuesta = evaluar_reportes(quality_reports, security_reports)
resultado = analizar_respuesta_lote(respuesta, "Evaluador")
metadata = obtener_ultimos_metadatos("Evaluator")

print("\n" + "=" * 70)
print("RESULTADO")
print("=" * 70)
print(json.dumps(resultado, ensure_ascii=False, indent=2))

print("\n" + "=" * 70)
print("VALIDACIÓN")
print("=" * 70)

print("\nJSON válido: Sí")
print("Provider:", metadata.get("provider"))
print("Modelo:", metadata.get("model"))
print("Fallback:", metadata.get("fallback"))

assert selection.provider == "nvidia"
assert selection.model == "z-ai/glm-5.2"
assert metadata.get("provider") == "nvidia"
assert metadata.get("fallback") is False
