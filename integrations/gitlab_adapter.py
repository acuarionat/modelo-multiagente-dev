import os
import gitlab
from typing import List, Dict, Any, Optional

class GitLabAdapter:
    """
    Clase responsable únicamente de comunicarse con la API de GitLab.
    No contiene lógica de negocio del sistema multiagente.
    """
    def __init__(self):
        self.url = os.getenv("GITLAB_URL")
        self.token = os.getenv("GITLAB_TOKEN")
        self.project_id = os.getenv("GITLAB_PROJECT_ID")
        
        if not all([self.url, self.token, self.project_id]):
            raise ValueError("Faltan variables de entorno para GitLab (GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID).")
            
        self.gl = self.connect()
        self.project = self.get_project()
        
    def connect(self) -> gitlab.Gitlab:
        """Establece conexión con GitLab."""
        gl = gitlab.Gitlab(url=self.url, private_token=self.token)
        gl.auth()
        return gl
        
    def get_project(self):
        """Obtiene el proyecto configurado."""
        return self.gl.projects.get(self.project_id)
        
    def list_open_issues(self) -> List[Any]:
        """Lista los issues abiertos del proyecto."""
        return self.project.issues.list(state='opened', all=True)
        
    def get_issue(self, issue_iid: int):
        """Obtiene un issue específico por su IID."""
        return self.project.issues.get(issue_iid)
        
    def create_issue(self, title: str, description: str, labels: Optional[List[str]] = None) -> Any:
        """Crea un nuevo issue."""
        issue_data = {
            "title": title,
            "description": description
        }
        if labels:
            issue_data["labels"] = labels
        return self.project.issues.create(issue_data)
        
    def update_issue(self, issue_iid: int, data: Dict[str, Any]):
        """Actualiza atributos de un issue."""
        issue = self.get_issue(issue_iid)
        for key, value in data.items():
            setattr(issue, key, value)
        issue.save()
        return issue
        
    def close_issue(self, issue_iid: int):
        """Cierra un issue."""
        return self.update_issue(issue_iid, {"state_event": "close"})
        
    def add_comment(self, issue_iid: int, body: str):
        """Añade un comentario a un issue."""
        issue = self.get_issue(issue_iid)
        return issue.notes.create({"body": body})
        
    def update_labels(self, issue_iid: int, labels: List[str]):
        """Actualiza las etiquetas de un issue."""
        return self.update_issue(issue_iid, {"add_labels": labels})
        
    def assign_milestone(self, issue_iid: int, milestone_id: int):
        """Asigna un milestone al issue."""
        return self.update_issue(issue_iid, {"milestone_id": milestone_id})
        
    def upload_attachment(self, filepath: str) -> Dict[str, Any]:
        """Sube un archivo al proyecto y devuelve la información del archivo adjunto."""
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            uploaded_file = self.project.upload(filename, filedata=f.read())
        return uploaded_file
