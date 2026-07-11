from typing import TypedDict, Optional, Dict, Any

class AgentState(TypedDict):
    """
    Estado compartido que fluye a través del grafo de LangGraph.
    """
    project_name: str               # Nombre del proyecto
    issue_data: Dict[str, Any]      # JSON base extraído de la Historia de Usuario de GitLab
    
    central_init: Optional[str]     # Respuesta inicial del central (JSON estructurado)
    
    quality_report: Optional[str]   # Output JSON del Agente de Calidad
    security_report: Optional[str]  # Output JSON del Agente de Seguridad
    
    evaluation: Optional[str]       # Veredicto JSON del Evaluador
    final_report: Optional[str]     # Reporte final JSON (metadata y docs) del Agente Central
