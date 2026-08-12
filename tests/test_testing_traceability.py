from core.testing_traceability import extraer_codificaciones_validas, resolver_trazabilidad_heredada

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
    {
        "HU origen": "HU-021", "Código requisito": "RF-003", "Tipo": "RF",
        "Nombre del requisito": "Cancelar reserva", "Elementos de Diseño": "ED-03",
        "Codificación": "COD-002", "Estado de implementación": "Implementado en Codificación",
        "Ubicación de implementación": "core/cancelaciones.py", "Estado de Codificación": "CONFORME",
    },
    {
        "HU origen": "HU-022", "Código requisito": "RF-004", "Tipo": "RF",
        "Nombre del requisito": "Listar reservas", "Elementos de Diseño": "—",
        "Codificación": "—", "Estado de implementación": "No evaluado",
        "Ubicación de implementación": "—", "Estado de Codificación": "—",
    },
]

# ==========================================================
# extraer_codificaciones_validas
# ==========================================================

validas = extraer_codificaciones_validas(MATRIZ_CODIFICACION)
print("\nCodificaciones válidas:", validas)
assert validas == {"COD-001", "COD-002"}
assert extraer_codificaciones_validas([]) == set()

# ==========================================================
# resolver_trazabilidad_heredada
# ==========================================================

resuelto = resolver_trazabilidad_heredada(["COD-001", "COD-999"], MATRIZ_CODIFICACION)
print("\nresolver_trazabilidad_heredada:", resuelto)

assert resuelto["codificaciones_no_encontradas"] == ["COD-999"]
assert set(resuelto["cadena_por_codificacion"]) == {"COD-001"}

filas_cod_001 = resuelto["cadena_por_codificacion"]["COD-001"]
assert len(filas_cod_001) == 2
assert filas_cod_001[0]["hu_origen"] == "HU-020"
assert filas_cod_001[0]["codigo_requisito"] == "RF-001"
assert filas_cod_001[0]["elementos_diseno"] == "ED-01"
assert filas_cod_001[1]["codigo_requisito"] == "RF-002"

resuelto_multiple = resolver_trazabilidad_heredada(["COD-001", "COD-002"], MATRIZ_CODIFICACION)
assert set(resuelto_multiple["cadena_por_codificacion"]) == {"COD-001", "COD-002"}
assert resuelto_multiple["codificaciones_no_encontradas"] == []

resuelto_vacio = resolver_trazabilidad_heredada([], MATRIZ_CODIFICACION)
assert resuelto_vacio == {"cadena_por_codificacion": {}, "codificaciones_no_encontradas": []}

print("\nTodas las verificaciones de testing_traceability pasaron.")
