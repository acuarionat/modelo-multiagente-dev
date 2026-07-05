from typing import TypedDict, Optional

class AgentState(TypedDict):
    """
    Estado compartido que fluye a través del grafo de LangGraph.
    """
    project_name: str               # Nombre del proyecto
    requirements_text: str          # Texto de los requerimientos extraído
    execution_id: Optional[int]     # ID de la BD para trazabilidad
    
    central_init: Optional[str]     # Respuesta inicial del central
    
    quality_report: Optional[str]   # Output JSON del Agente de Calidad
    security_report: Optional[str]  # Output JSON del Agente de Seguridad
    
    evaluation: Optional[str]       # Veredicto JSON del Evaluador
    final_report: Optional[str]     # Reporte final MD del Agente Central
