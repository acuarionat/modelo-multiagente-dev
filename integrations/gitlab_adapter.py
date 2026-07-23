import os
import gitlab
from typing import List, Dict, Any, Optional

class GitLabAdapter:
    """
    Clase responsable únicamente de comunicarse con la API de GitLab.
    No contiene lógica de negocio del sistema multiagente.
    """
    def __init__(self, url: str = None, token: str = None, project_id: str = None):
        self.url = url or os.getenv("GITLAB_URL")
        self.token = token or os.getenv("GITLAB_TOKEN")
        self.project_id = project_id or os.getenv("GITLAB_PROJECT_ID")
        
        if not all([self.url, self.token, self.project_id]):
            raise ValueError("Faltan variables de entorno para GitLab (GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID).")
            
        self.gl = self.conectar()
        self.project = self.obtener_proyecto()
        
    def conectar(self) -> gitlab.Gitlab:
        """Establece conexión con GitLab."""
        gl = gitlab.Gitlab(url=self.url, private_token=self.token)
        gl.auth()
        return gl
        
    def obtener_proyecto(self):
        """Obtiene el proyecto configurado."""
        return self.gl.projects.get(self.project_id)
        
    def obtener_hitos(self) -> List[Any]:
        """Obtiene la lista de Sprints (Milestones) del proyecto."""
        return self.project.milestones.list(all=True)

    def asegurar_hitos(self, titles: List[str]) -> Dict[str, str]:
        """Reutiliza milestones existentes y crea solamente los faltantes."""
        existing = {item.title: item for item in self.obtener_hitos()}
        status = {}
        for title in titles:
            if title in existing:
                status[title] = "reutilizado"
            else:
                self.project.milestones.create({"title": title})
                status[title] = "creado"
        return status

    def listar_issues_abiertos(self, milestone_title: Optional[str] = None, labels: Optional[List[str]] = None) -> List[Any]:
        """Lista los issues abiertos del proyecto. Permite filtrar por Milestone o Etiquetas."""
        params = {'state': 'opened', 'all': True}
        if milestone_title:
            params['milestone'] = milestone_title
        if labels:
            params['labels'] = ','.join(labels)
            
        return self.project.issues.list(**params)
        
    def obtener_issue(self, issue_iid: int):
        """Obtiene un issue específico por su IID."""
        return self.project.issues.get(issue_iid)
        
    def agregar_comentario(self, issue_iid: int, body: str):
        """Añade un comentario a un issue."""
        issue = self.obtener_issue(issue_iid)
        return issue.notes.create({"body": body})
        
    def subir_adjunto(self, filepath: str) -> Dict[str, Any]:
        """Sube un archivo al proyecto y devuelve la información del archivo adjunto."""
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            uploaded_file = self.project.upload(filename, filedata=f.read())
        return uploaded_file
