from typing import TypedDict, Optional, Dict, Any, List

class AgentState(TypedDict):
    """
    Estado compartido que fluye a través del grafo de LangGraph.
    """
    project_name: str               # Nombre del proyecto
    sprint_context: str             # Contexto resumido de todas las historias del Sprint
    issues_data: List[Dict[str, Any]] # Lista de JSON base extraído de las Historias de Usuario
    
    central_init: Optional[str]     # Respuesta inicial del central (JSON Array estructurado)
    
    quality_report: Optional[str]   # Output JSON Array del Agente de Calidad (y cálculos en nodo)
    security_report: Optional[str]  # Output JSON Array del Agente de Seguridad (y cálculos en nodo)
    
    evaluation: Optional[str]       # Veredicto JSON Array del Evaluador
    final_report: Optional[str]     # Reporte final JSON Array (consolidado en Python)
    validation_errors: List[str]
    content_validation_errors: Dict[int, List[str]]

    # --- Diseño (independiente de Requerimientos; no reutilizar los campos de arriba) ---
    design_issues: List[Dict[str, Any]]      # Issues DIS-xxx mapeados (design_issue_mapper)
    design_context: List[Dict[str, Any]]     # Contexto construido (design_context + matriz heredada)

    design_central_result: Optional[Dict[str, Any]]    # Resultado del Central de Diseño
    design_quality_result: Optional[Dict[str, Any]]    # {"raw", "mc03", "mc04"}
    design_security_result: Optional[Dict[str, Any]]   # {"raw", "ms03", "ms04"}
    design_evaluator_result: Optional[Dict[str, Any]]  # Hallazgos del Evaluador de Diseño

    design_metrics: Optional[Dict[str, Any]]           # Reservado para fases posteriores
    design_summary: Optional[Dict[str, Any]]           # Consolidación determinística final
    design_traceability: Optional[List[Dict[str, Any]]]  # Reservado para la matriz RF/RNF → DIS → ED

    # --- Matriz de entrada de Diseño (previa al análisis) ---
    matriz_requerimientos_original: Optional[List[Dict[str, Any]]]  # Matriz generada al finalizar Requerimientos
    matriz_entrada_diseno: Optional[List[Dict[str, Any]]]           # Matriz vigente (GitLab TRZ-001 o Excel), normalizada
    matriz_estado: Optional[str]            # ORIGINAL / EDITADA / INVALIDA
    matriz_fuente: Optional[str]            # "GitLab" / "EXCEL" / "Original"
    matriz_confirmada: Optional[bool]       # True solo tras la confirmación explícita del responsable
    matriz_validacion: Optional[Dict[str, Any]]        # {"valida": bool, "errores": [...]}
    matriz_cambios_pre_diseno: Optional[Dict[str, Any]]  # {"agregados","modificados","retirados","hay_cambios"}
    matriz_diseno_evolucionada: Optional[List[Dict[str, Any]]]  # Filas de construir_filas_matriz_diseno (post-análisis)

    # --- Codificación (independiente de Requerimientos y de Diseño; no
    # reutiliza design_quality_result, design_summary, matriz_estado, etc.) ---
    coding_issues: List[Dict[str, Any]]          # Issues COD-xxx mapeados (coding_issue_mapper)
    coding_codigo_localizado: Optional[Dict[str, Any]]  # Salida de code_repository_service.obtener_codigo_codificacion (pre-grafo)
    coding_context: List[Dict[str, Any]]         # Contexto construido (coding_context.py): issue + matriz + código + evidencia de herramientas

    coding_tool_results: Optional[Dict[str, Any]]       # Evidencia normalizada {"radon","semgrep","pip_audit","gitleaks"}
    coding_central_result: Optional[Dict[str, Any]]     # Resultado del Central de Codificación
    coding_quality_result: Optional[Dict[str, Any]]     # {"raw", "mc05"}
    coding_security_result: Optional[Dict[str, Any]]    # {"raw", "ms05", "ms06", "ms07"}
    coding_evaluator_result: Optional[Dict[str, Any]]   # Hallazgos del Evaluador de Codificación

    coding_metrics: Optional[Dict[str, Any]]            # Reservado para fases posteriores
    coding_summary: Optional[Dict[str, Any]]            # Consolidación determinística final
    coding_traceability: Optional[List[Dict[str, Any]]]  # Matriz evolucionada HU→RF/RNF→DIS→ED→COD

    # --- Matriz de Diseño heredada como entrada de Codificación (previa al análisis) ---
    coding_matrix_input: Optional[List[Dict[str, Any]]]      # Matriz de Diseño vigente (heredada), normalizada
    coding_matrix_source: Optional[str]         # "GitLab" / "EXCEL" / "Diseño"
    coding_matrix_status: Optional[str]         # ORIGINAL / EDITADA / INVALIDA
    coding_matrix_version: Optional[str]
    coding_matrix_changes: Optional[Dict[str, Any]]     # {"agregados","modificados","retirados","errores_estructura","hay_cambios"}
    coding_matrix_snapshot: Optional[Dict[str, Any]]    # Snapshot versionado antes de comenzar Codificación
    coding_matrix_metadata: Optional[Dict[str, Any]]    # Envoltorio de versión de la matriz evolucionada (post-análisis)

    # --- Descubrimiento y validación del repositorio de Codificación ---
    coding_repository_tree: Optional[List[Dict[str, str]]]    # Árbol completo del repositorio (archivos + directorios)
    coding_repository_discovery: Optional[Dict[str, Any]]    # {"rama", "lenguajes", "archivos", "manifiestos", "lockfiles", ...}
    coding_repository_profile: Optional[Dict[str, Any]]      # Perfil técnico consolidado (para UI/PDF/DOCX)
    coding_detected_technologies: Optional[Dict[str, Any]]   # {"lenguajes", "ecosistemas", "tecnologias_detectadas"}
    coding_selected_tools: Optional[Dict[str, Dict[str, Any]]]  # Herramientas seleccionadas por métrica (MC-05, MS-05, MS-06, MS-07)
    coding_repository_context: Optional[Dict[str, Any]]      # Contexto combinado pre-análisis (issues + matriz + rutas + herramientas)
