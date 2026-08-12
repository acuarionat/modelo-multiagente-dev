from core.testing_context import construir_contexto_pruebas
from core.testing_metrics import calcular_metricas_pruebas, preparar_evidencia_pruebas
from core.testing_traceability import resolver_trazabilidad_heredada

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
    "controles_seguridad": [{"aplica": True, "verificado": True}],
    "pruebas_seguridad": [{"estado": "APROBADA"}],
    "evidencias": [],
}

resolucion = resolver_trazabilidad_heredada(ISSUE_PRUEBAS["codificaciones_relacionadas"], MATRIZ_CODIFICACION)
evidencia = preparar_evidencia_pruebas(ISSUE_PRUEBAS)
metricas = calcular_metricas_pruebas(evidencia)

contexto = construir_contexto_pruebas(
    ISSUE_PRUEBAS, evidencia, metricas, resolucion["cadena_por_codificacion"],
)
print("\nconstruir_contexto_pruebas:", contexto)

assert contexto["prueba_id"] == "PRU-001"
assert contexto["issue_iid"] == 40
assert contexto["titulo"] == ISSUE_PRUEBAS["titulo"]
assert contexto["codificaciones_relacionadas"] == ["COD-001"]

assert contexto["trazabilidad"] == {
    "COD-001": {
        "elementos_diseno": ["ED-01", "ED-02"],
        "requisitos": ["RF-001", "RF-002"],
        "historias": ["HU-020"],
    },
}

assert contexto["evidencia"] is evidencia
assert contexto["metricas"] is metricas
assert contexto["metricas"]["MC-07"]["valor"] == 0.5
assert contexto["metricas"]["MC-08"]["valor"] == 1.0

# COD sin filas en la matriz: la clave simplemente no aparece en el resumen.
resolucion_sin_match = resolver_trazabilidad_heredada(["COD-999"], MATRIZ_CODIFICACION)
contexto_sin_match = construir_contexto_pruebas(
    {**ISSUE_PRUEBAS, "codificaciones_relacionadas": ["COD-999"]},
    evidencia, metricas, resolucion_sin_match["cadena_por_codificacion"],
)
assert contexto_sin_match["trazabilidad"] == {}

print("\nTodas las verificaciones de testing_context pasaron.")
