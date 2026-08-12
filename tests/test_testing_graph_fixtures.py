"""
Prueba del grafo completo de Pruebas (construir_grafo_pruebas) con datos
fijos (fixtures, sin GitLab) y proveedor LOCAL (Ollama, no remoto): fuerza
ENABLE_REMOTE_LLM=false antes de invocar el grafo para garantizar que esta
prueba nunca golpea Groq/NVIDIA de pago, tal como pide la etapa de
"fixtures antes de proveedores reales".
"""
import os

os.environ["ENABLE_REMOTE_LLM"] = "false"

import json

from core.graph import construir_grafo_pruebas
from core.testing_contract import (
    validar_salida_central_pruebas,
    validar_salida_calidad_pruebas,
    validar_salida_seguridad_pruebas,
    validar_salida_evaluador_pruebas,
)

MATRIZ_CODIFICACION = [
    {
        "HU origen": "HU-020", "Código requisito": "RF-001", "Tipo": "RF",
        "Nombre del requisito": "Registrar reserva", "Elementos de Diseño": "ED-01",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
    },
    {
        "HU origen": "HU-020", "Código requisito": "RF-002", "Tipo": "RF",
        "Nombre del requisito": "Evitar duplicados", "Elementos de Diseño": "ED-02",
        "Codificación": "COD-001", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/reservas.py", "Estado de Codificación": "CONFORME",
    },
]

ISSUE_PRUEBAS = {
    "prueba_id": "PRU-001",
    "issue_iid": 40,
    "titulo": "PRU-001 — Pruebas del módulo de reservas",
    "codificaciones_relacionadas": ["COD-001"],
    "descripcion": "Se probó el registro de reservas y la prevención de duplicados.",
    "pruebas_funcionales": [
        {"id": "CP-01", "funcionalidad": "Registrar reserva", "prueba_realizada": "Datos válidos",
         "resultado_esperado": "Se registra", "resultado_obtenido": "Se registró", "estado": "APROBADA"},
        {"id": "CP-02", "funcionalidad": "Evitar duplicados", "prueba_realizada": "Reserva repetida",
         "resultado_esperado": "Se rechaza la 2da", "resultado_obtenido": "Permitió ambas", "estado": "FALLIDA"},
    ],
    "fallos": [
        {"id": "FAL-01", "fallo": "Permitía reservas duplicadas", "detectado_en": "CP-02",
         "corregido": True, "verificado": True, "resultado_verificacion": "Verificado en una nueva corrida"},
    ],
    "controles_seguridad": [
        {"id": "CS-01", "control": "Restringir a usuarios autorizados", "aplica": True, "verificado": True,
         "forma_verificacion": "Prueba de acceso", "resultado": "Rechazado correctamente"},
        {"id": "CS-02", "control": "Registrar operaciones importantes", "aplica": True, "verificado": False,
         "forma_verificacion": "No se verificó", "resultado": "Pendiente"},
    ],
    "pruebas_seguridad": [
        {"id": "PS-01", "prueba_realizada": "Acceso sin autorización", "resultado_esperado": "Rechazo",
         "resultado_obtenido": "Rechazado", "estado": "APROBADA"},
    ],
    "evidencias": [
        {"id": "EV-01", "prueba_o_fallo_relacionado": "CP-02", "tipo_evidencia": "Captura de pantalla",
         "descripcion": "evidencias/cp-02.png"},
    ],
    "pendientes": ["Verificar el registro de auditoría (CS-02)."],
    "observaciones": [],
}

initial_state = {
    "project_name": "modelo-multiagente-dev",
    "sprint_context": "Pruebas",
    "testing_issues": [ISSUE_PRUEBAS],
    "testing_input_matrix": MATRIZ_CODIFICACION,
    "testing_input_matrix_metadata": {"fuente": "GitLab"},
}

grafo = construir_grafo_pruebas()
final_state = grafo.invoke(initial_state)

print("\n" + "=" * 70)
print("ESTADO FINAL DEL GRAFO DE PRUEBAS (fixtures, proveedor local)")
print("=" * 70)
for clave in (
    "testing_evidence", "testing_metrics", "testing_context",
    "testing_central_result", "testing_quality_result", "testing_security_result",
    "testing_evaluator_result", "testing_summary",
):
    print(f"\n--- {clave} ---")
    print(json.dumps(final_state.get(clave), ensure_ascii=False, indent=2, default=str))

contexto = final_state["testing_context"][0]
valid_codificaciones = set(contexto["trazabilidad"])

assert final_state["testing_metrics"]["MC-07"]["valor"] == 0.5
assert final_state["testing_metrics"]["MC-08"]["valor"] == 1.0

validacion_central = validar_salida_central_pruebas(
    final_state["testing_central_result"], [40], valid_codificaciones,
)
assert validacion_central["valido"], validacion_central["errores"]

validacion_calidad = validar_salida_calidad_pruebas(final_state["testing_quality_result"]["raw"])
assert validacion_calidad["valido"], validacion_calidad["errores"]

validacion_seguridad = validar_salida_seguridad_pruebas(final_state["testing_security_result"]["raw"])
assert validacion_seguridad["valido"], validacion_seguridad["errores"]

validacion_evaluador = validar_salida_evaluador_pruebas(
    final_state["testing_evaluator_result"], 40, "PRU-001", valid_codificaciones,
)
assert validacion_evaluador["valido"], validacion_evaluador["errores"]

summary = final_state["testing_summary"]
assert summary["prueba_id"] == "PRU-001"
assert summary["issue_iid"] == 40
assert summary["estado_orientativo"] in {"APROBADO", "CORREGIR", "REVISAR", "ERROR"}
# MC-07 no cumple (0.5 < 0.95) -> CORREGIR es el único estado consistente.
assert summary["estado_orientativo"] == "CORREGIR"

print("\nTodas las verificaciones del grafo de Pruebas (fixtures, proveedor local) pasaron.")
