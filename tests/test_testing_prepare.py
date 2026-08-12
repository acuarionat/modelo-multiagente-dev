"""
Prueba de core/graph.py::nodo_testing_prepare con fixtures, sin LLM y sin
session_state: solo state del grafo (testing_issues, testing_input_matrix).
"""
from core.graph import nodo_testing_prepare

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
    "pruebas_funcionales": [
        {"funcionalidad": "Registrar reserva", "estado": "APROBADA"},
        {"funcionalidad": "Evitar duplicados", "estado": "FALLIDA"},
    ],
    "fallos": [{"corregido": True, "verificado": True}],
    "controles_seguridad": [
        {"aplica": True, "verificado": True},
        {"aplica": True, "verificado": False},
    ],
    "pruebas_seguridad": [{"estado": "APROBADA"}],
    "evidencias": [],
    "descripcion": "Se probó el registro de reservas.",
    "pendientes": [],
    "observaciones": [],
}

state = {
    "testing_issues": [ISSUE_PRUEBAS],
    "testing_input_matrix": MATRIZ_CODIFICACION,
    "testing_input_matrix_metadata": {"fuente": "GitLab"},
}

resultado = nodo_testing_prepare(state)
print("\nnodo_testing_prepare:", resultado)

assert set(resultado.keys()) == {"testing_evidence", "testing_metrics", "testing_context"}

evidencia = resultado["testing_evidence"]
assert evidencia["prueba_id"] == "PRU-001"
assert evidencia["conteos"]["pruebas_funcionales"] == 2
assert evidencia["conteos"]["fallos"] == 1

metricas = resultado["testing_metrics"]
assert metricas["MC-07"]["valor"] == 0.5
assert metricas["MC-07"]["cumple"] is False
assert metricas["MC-08"]["valor"] == 1.0
assert metricas["MC-08"]["cumple"] is True
assert metricas["MS-08"]["numerador"] == 1 and metricas["MS-08"]["denominador"] == 2
assert metricas["MS-09"]["valor"] == 1.0

contexto = resultado["testing_context"][0]
assert contexto["prueba_id"] == "PRU-001"
assert contexto["codificaciones_relacionadas"] == ["COD-001"]
assert contexto["trazabilidad"]["COD-001"]["elementos_diseno"] == ["ED-01", "ED-02"]
assert contexto["trazabilidad"]["COD-001"]["requisitos"] == ["RF-001", "RF-002"]
assert contexto["trazabilidad"]["COD-001"]["historias"] == ["HU-020"]
assert contexto["metricas"] is metricas
assert contexto["evidencia"] is evidencia

validacion = contexto["validacion_entrada"]
assert validacion["estado"] == "VALIDO"
assert validacion["entrada_valida"] is True
assert validacion["referencias_invalidas"] == []


# ---------------------------------------------------------
# COD declarado que no existe en testing_input_matrix
# ---------------------------------------------------------

issue_referencia_invalida = {**ISSUE_PRUEBAS, "codificaciones_relacionadas": ["COD-999"]}
resultado_invalido = nodo_testing_prepare({
    "testing_issues": [issue_referencia_invalida],
    "testing_input_matrix": MATRIZ_CODIFICACION,
    "testing_input_matrix_metadata": {"fuente": "GitLab"},
})
contexto_invalido = resultado_invalido["testing_context"][0]
print("\nnodo_testing_prepare (referencia inválida):", contexto_invalido["validacion_entrada"])
assert contexto_invalido["validacion_entrada"]["estado"] == "REFERENCIA_INVALIDA"
assert contexto_invalido["validacion_entrada"]["referencias_invalidas"] == ["COD-999"]
assert contexto_invalido["trazabilidad"] == {}
# Las métricas se siguen calculando igual: la validación de entrada es
# información adicional, no bloquea el cálculo determinístico.
assert resultado_invalido["testing_metrics"]["MC-07"]["valor"] == 0.5

print("\nTodas las verificaciones de nodo_testing_prepare pasaron.")
