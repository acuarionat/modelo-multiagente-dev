import os
import gitlab
from typing import List, Dict, Any, Optional

PENDING_LABEL = "Pendiente"
REVIEWED_LABEL = "Revisada"
REWORK_LABEL = "Requiere modificación"
LEGACY_COMPLETED_LABELS = {"Analizada", "Analizado"}
WORKFLOW_LABELS = {
    PENDING_LABEL: "#F2C300",
    REVIEWED_LABEL: "#1F75CB",
    REWORK_LABEL: "#D9534F",
}


def es_issue_pendiente(issue) -> bool:
    """Permite analizar issues pendientes o que requieren una nueva revisión."""
    labels = {str(label).strip().casefold() for label in getattr(issue, "labels", [])}
    completed = {
        REVIEWED_LABEL.casefold(),
        *(label.casefold() for label in LEGACY_COMPLETED_LABELS),
    }
    eligible = {PENDING_LABEL.casefold(), REWORK_LABEL.casefold()}
    return bool(labels & eligible) and not bool(labels & completed)


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
        self._workflow_labels_ready = False
        
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

    def asegurar_etiquetas_flujo(self) -> Dict[str, str]:
        """Crea una sola vez las etiquetas del ciclo de revisión que aún no existan."""
        if self._workflow_labels_ready:
            return {name: "verificada" for name in WORKFLOW_LABELS}
        existing = {item.name for item in self.project.labels.list(all=True)}
        status = {}
        for name, color in WORKFLOW_LABELS.items():
            if name in existing:
                status[name] = "reutilizada"
            else:
                self.project.labels.create({"name": name, "color": color})
                status[name] = "creada"
        self._workflow_labels_ready = True
        return status

    def listar_issues_abiertos(self, milestone_title: Optional[str] = None, labels: Optional[List[str]] = None) -> List[Any]:
        """Lista los issues abiertos del proyecto. Permite filtrar por Milestone o Etiquetas."""
        params = {'state': 'opened', 'all': True}
        if milestone_title:
            params['milestone'] = milestone_title
        if labels:
            params['labels'] = ','.join(labels)
            
        return self.project.issues.list(**params)

    def listar_issues_pendientes(self, milestone_title: Optional[str] = None) -> List[Any]:
        """Lista issues pendientes o marcados para modificación."""
        # GitLab combina varias etiquetas como AND. Se consulta el milestone
        # completo y se aplica localmente la alternativa Pendiente/Modificación.
        issues = self.listar_issues_abiertos(milestone_title=milestone_title)
        return [issue for issue in issues if es_issue_pendiente(issue)]
        
    def obtener_issue(self, issue_iid: int):
        """Obtiene un issue específico por su IID."""
        return self.project.issues.get(issue_iid)
        
    def agregar_comentario(self, issue_iid: int, body: str):
        """Añade un comentario a un issue."""
        issue = self.obtener_issue(issue_iid)
        return issue.notes.create({"body": body})

    def actualizar_etiquetas(self, issue_iid: int, labels: List[str]):
        """Reemplaza las etiquetas del issue con el nuevo estado de revisión."""
        self.asegurar_etiquetas_flujo()
        issue = self.obtener_issue(issue_iid)
        issue.labels = list(dict.fromkeys(labels))
        issue.save()
        return issue
        
    def subir_adjunto(self, filepath: str) -> Dict[str, Any]:
        """Sube un archivo al proyecto y devuelve la información del archivo adjunto."""
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as f:
            uploaded_file = self.project.upload(filename, filedata=f.read())
        return uploaded_file
