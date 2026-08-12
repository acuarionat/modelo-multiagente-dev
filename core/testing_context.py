"""
Construye el contrato único de entrada para los agentes de Pruebas
(Central, Calidad, Seguridad), uniendo:

- El Issue PRU-xxx ya mapeado (integrations/testing_issue_mapper.py).
- La trazabilidad heredada ya resuelta contra testing_input_matrix
  (core/testing_validation.py -> core/testing_traceability.py).
- La evidencia ya preparada y las métricas MC-07/MC-08/MS-08/MS-09 ya
  calculadas (core/testing_metrics.py).

No inventa PRU, COD, ED, RF/RNF ni HU: solo organiza lo que ya existe.
No evalúa, no calcula métricas.
"""


def _resumir_trazabilidad_por_codificacion(cadena_por_codificacion: dict) -> dict:
    """
    Convierte la cadena por fila (core/testing_traceability.py::resolver_trazabilidad_heredada)
    en un resumen deduplicado por COD-xxx: elementos_diseno, requisitos e
    historias, tal como lo espera el contrato de contexto de los agentes.
    """
    resumen = {}
    for codificacion_id, filas in (cadena_por_codificacion or {}).items():
        elementos_diseno = []
        requisitos = []
        historias = []
        for fila in filas:
            texto_elementos = str(fila.get("elementos_diseno") or "").strip()
            if texto_elementos and texto_elementos != "—":
                for elemento_id in texto_elementos.split(","):
                    elemento_id = elemento_id.strip()
                    if elemento_id and elemento_id not in elementos_diseno:
                        elementos_diseno.append(elemento_id)

            codigo_requisito = fila.get("codigo_requisito")
            if codigo_requisito and codigo_requisito not in requisitos:
                requisitos.append(codigo_requisito)

            hu_origen = fila.get("hu_origen")
            if hu_origen and hu_origen not in historias:
                historias.append(hu_origen)

        resumen[codificacion_id] = {
            "elementos_diseno": elementos_diseno,
            "requisitos": requisitos,
            "historias": historias,
        }
    return resumen


def construir_contexto_pruebas(
    issue_pruebas: dict,
    evidencia: dict,
    metricas: dict,
    cadena_por_codificacion: dict,
) -> dict:
    """
    Ensambla el contexto completo de un PRU-xxx. issue_pruebas es la
    salida de mapear_issue_pruebas; evidencia es la salida de
    preparar_evidencia_pruebas; metricas es la salida de
    calcular_metricas_pruebas; cadena_por_codificacion es
    validacion["trazabilidad_heredada"] (core/testing_validation.py).
    """
    return {
        "prueba_id": issue_pruebas.get("prueba_id"),
        "issue_iid": issue_pruebas.get("issue_iid"),
        "titulo": issue_pruebas.get("titulo"),
        "codificaciones_relacionadas": issue_pruebas.get("codificaciones_relacionadas") or [],
        "trazabilidad": _resumir_trazabilidad_por_codificacion(cadena_por_codificacion),
        "evidencia": evidencia,
        "metricas": metricas,
    }
