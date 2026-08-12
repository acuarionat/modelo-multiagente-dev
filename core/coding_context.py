"""
Construye el contrato único de entrada para el primer agente de
Codificación (Central), uniendo:

- El Issue COD-xxx ya mapeado (integrations/coding_issue_mapper.py).
- La matriz de Diseño heredada y vigente (core/coding_matrix_input.py).
- El código realmente localizado en el repositorio GitLab
  (integrations/code_repository_service.py).
- La evidencia normalizada de Radon, Semgrep, pip-audit y Gitleaks
  (core/code_analysis/).

No inventa ED, COD, archivos, RF/RNF ni resultados de herramientas: solo
organiza lo que ya existe. No evalúa, no calcula métricas.
"""

from core.code_analysis.orchestrator import obtener_evidencia_por_metrica
from core.coding_context_files import preparar_archivos_para_llm


def _indexar_elementos_diseno(matriz_diseno_entrada: list) -> dict:
    """
    Construye ED-xx -> lista de relaciones DIS -> RF/RNF -> HU
    a partir de la columna "Elementos de Diseño" de la matriz heredada
    (texto plano "ED-01, ED-02" o "—", tal como la produce
    construir_filas_matriz_diseno).
    """
    indice = {}
    for fila in matriz_diseno_entrada:
        texto_elementos = str(fila.get("Elementos de Diseño") or "").strip()
        if not texto_elementos or texto_elementos == "—":
            continue
        referencia = {
            "hu_origen": fila.get("HU origen"),
            "diseno": fila.get("Diseño"),
            "codigo_requisito": fila.get("Código requisito"),
            "tipo_requisito": fila.get("Tipo"),
            "nombre_requisito": fila.get("Nombre del requisito"),
            "descripcion_requisito": fila.get("Descripción"),
        }
        for elemento_id in texto_elementos.split(","):
            elemento_id = elemento_id.strip()
            if not elemento_id:
                continue
            indice.setdefault(elemento_id, []).append(referencia)
    return indice


def _contextualizar_elementos_diseno(elementos_declarados: list, indice_elementos: dict) -> tuple:
    """Cruza los ED-xx declarados en el Issue COD contra la matriz heredada. No decide validez de negocio: solo reporta lo que existe."""
    contextualizados = []
    referencias_validas = []
    referencias_invalidas = []

    for elemento_id in elementos_declarados:
        referencias = indice_elementos.get(elemento_id)
        if referencias is None:
            referencias_invalidas.append(elemento_id)
            continue
        referencias_validas.append(elemento_id)
        contextualizados.append({
            "elemento_id": elemento_id,
            "relaciones_diseno": referencias,
        })

    return contextualizados, referencias_validas, referencias_invalidas


def construir_contexto_codificacion(
    issue_codificacion: dict,
    matriz_diseno_entrada: list,
    codigo_localizado: dict,
    evidencia_herramientas: dict,
) -> dict:
    """
    Ensambla el contexto completo de un COD-xxx. issue_codificacion es la
    salida de mapear_issue_codificacion; matriz_diseno_entrada es la matriz
    de Diseño vigente (ya confirmada); codigo_localizado es la salida de
    integrations.code_repository_service.obtener_codigo_codificacion;
    evidencia_herramientas es la salida de
    core/code_analysis/orchestrator.py::ejecutar_analizadores_seleccionados
    ({"<adaptador>": ...}, una clave por cada herramienta realmente
    ejecutada según la selección de tool_selector.py — p. ej. "radon" o
    "eslint_complexity" para MC-05 según el lenguaje), cada uno ya
    normalizado por core/code_analysis/ (estado OK/NO_APLICA/ERROR + datos).
    """
    indice_elementos = _indexar_elementos_diseno(matriz_diseno_entrada)
    elementos_contextualizados, referencias_validas, referencias_invalidas = _contextualizar_elementos_diseno(
        issue_codificacion.get("elementos_diseno_declarados", []), indice_elementos,
    )

    preparacion_archivos = preparar_archivos_para_llm(codigo_localizado.get("archivos", []))

    return {
        **issue_codificacion,

        "elementos_diseno_contextualizados": elementos_contextualizados,
        "validacion_elementos_diseno": {
            "referencias_validas": referencias_validas,
            "referencias_invalidas": referencias_invalidas,
        },

        "archivos_localizados": preparacion_archivos["archivos_para_llm"],
        "archivos_omitidos_del_contexto": preparacion_archivos["archivos_omitidos_del_contexto"],
        "lenguaje_detectado": codigo_localizado.get("lenguaje"),
        "manifiesto_dependencias": codigo_localizado.get("manifiesto_dependencias"),

        "evidencia_tecnica": obtener_evidencia_por_metrica(evidencia_herramientas),
    }
