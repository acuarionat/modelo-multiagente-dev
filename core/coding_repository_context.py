"""
Contexto de repositorio previo a coding_context.py.

Junta:
- Perfil técnico del repositorio
- Matriz de Diseño heredada
- Issues de Codificación
- Rutas validadas
- Herramientas seleccionadas

Último objeto antes de ejecutar herramientas.
"""

from typing import Dict, List, Any

from core.coding_matrix_input import extraer_elementos_diseno_validos


def construir_contexto_repository_codificacion(
    coding_issues: List[Dict[str, Any]],
    repository_profile: Dict[str, Any],
    herramientas_seleccionadas: Dict[str, Dict[str, Any]],
    repository_tree: List[Dict[str, str]],
    matriz_diseno: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construye el contexto pre-análisis que combina todas las entradas.

    Args:
        coding_issues: Issues COD del milestone Codificación (formato de
            integrations.coding_issue_mapper.mapear_issue_codificacion)
        repository_profile: salida de construir_perfil_repositorio()
        herramientas_seleccionadas: salida de seleccionar_herramientas()
        repository_tree: árbol completo del repositorio (para validación)
        matriz_diseno: filas de la matriz de Diseño heredada (contrato de
            core/design_traceability.py::construir_filas_matriz_diseno:
            "HU origen", "Código requisito", "Diseño", "Elementos de Diseño", ...)

    Retorna:
        {
            "repositorio": {...},
            "issues_validas": [...],
            "issues_bloqueadas": int,
            "problemas": [...],
            "trazabilidad": {
                "COD-001": {
                    "archivos_validos": [...],
                    "elementos_diseno": ["ED-01", "ED-02"],
                    "disenos": ["DIS-001"],
                    "requisitos": ["RF-001", "RF-002"],
                    "historias": ["HU-001"],
                }
            },
            "herramientas_seleccionadas": {...},
            "estado_global": "OK" | "CON_ADVERTENCIAS" | "BLOQUEADO"
        }
    """
    archivos_repo = {item["ruta"] for item in repository_tree if item["tipo"] == "archivo"}
    elementos_diseno_vigentes = extraer_elementos_diseno_validos(matriz_diseno)

    issues_validas = []
    problemas = []
    trazabilidad = {}

    for issue in coding_issues:
        codificacion_id = issue.get("codificacion_id") or f"issue-{issue.get('issue_iid')}"
        archivos_declarados = issue.get("archivos_declarados", [])
        elementos_diseno_declarados = issue.get("elementos_diseno_declarados", [])

        rutas_declaradas = [
            item.get("ruta") if isinstance(item, dict) else item
            for item in archivos_declarados
        ]

        rutas_invalidas = []
        rutas_expandidas = set()
        for ruta in rutas_declaradas:
            if not ruta:
                continue
            if ruta in archivos_repo:
                rutas_expandidas.add(ruta)
            elif any(archivo.startswith(ruta + "/") for archivo in archivos_repo):
                rutas_expandidas.update(
                    archivo for archivo in archivos_repo
                    if archivo.startswith(ruta + "/")
                )
            else:
                rutas_invalidas.append(ruta)

        elementos_invalidos = [
            ed for ed in elementos_diseno_declarados
            if ed not in elementos_diseno_vigentes
        ]

        if rutas_invalidas:
            problemas.append({
                "issue": codificacion_id,
                "tipo": "rutas_invalidas",
                "detalle": rutas_invalidas
            })

        if elementos_invalidos:
            problemas.append({
                "issue": codificacion_id,
                "tipo": "elementos_diseno_invalidos",
                "detalle": elementos_invalidos
            })

        if not rutas_invalidas and not elementos_invalidos:
            issues_validas.append(codificacion_id)
            disenos, requisitos, historias = _resolver_trazabilidad_desde_matriz(
                elementos_diseno_declarados, matriz_diseno
            )
            trazabilidad[codificacion_id] = {
                "archivos_validos": sorted(rutas_expandidas),
                "elementos_diseno": elementos_diseno_declarados,
                "disenos": disenos,
                "requisitos": requisitos,
                "historias": historias,
            }

    estado_global = "OK"
    if problemas:
        estado_global = "CON_ADVERTENCIAS" if issues_validas else "BLOQUEADO"

    return {
        "repositorio": repository_profile,
        "issues_validas": issues_validas,
        "issues_bloqueadas": len(coding_issues) - len(issues_validas),
        "problemas": problemas,
        "trazabilidad": trazabilidad,
        "herramientas_seleccionadas": herramientas_seleccionadas,
        "estado_global": estado_global,
    }


def _resolver_trazabilidad_desde_matriz(
    elementos_diseno: List[str],
    matriz_diseno: List[Dict[str, Any]],
):
    """Resuelve DIS/RF-RNF/HU vinculados a los elementos de diseño declarados.

    La columna "Elementos de Diseño" de la matriz es texto separado por comas
    ("ED-01, ED-02" o "—"), tal como la produce construir_filas_matriz_diseno.
    """
    elementos_set = set(elementos_diseno)
    disenos = set()
    requisitos = set()
    historias = set()

    for fila in matriz_diseno:
        texto_elementos = str(fila.get("Elementos de Diseño") or "").strip()
        if not texto_elementos or texto_elementos == "—":
            continue
        elementos_fila = {e.strip() for e in texto_elementos.split(",") if e.strip()}
        if not elementos_fila & elementos_set:
            continue

        diseno_id = fila.get("Diseño")
        if diseno_id and diseno_id != "—":
            disenos.add(diseno_id)

        codigo_requisito = fila.get("Código requisito")
        if codigo_requisito:
            requisitos.add(codigo_requisito)

        hu_origen = fila.get("HU origen")
        if hu_origen:
            historias.add(hu_origen)

    return sorted(disenos), sorted(requisitos), sorted(historias)
