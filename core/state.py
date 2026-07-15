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
