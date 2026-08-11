import os
import unicodedata
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


def _normalizar_etiqueta(label: Any) -> str:
    text = unicodedata.normalize("NFKD", str(label).strip().casefold())
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char)).split()
    )


def es_issue_pendiente(issue) -> bool:
    """Permite Pendiente o Requiere modificación, salvo estados finales."""
    labels = {_normalizar_etiqueta(label) for label in getattr(issue, "labels", [])}
    completed = {
        _normalizar_etiqueta(REVIEWED_LABEL),
        *(_normalizar_etiqueta(label) for label in LEGACY_COMPLETED_LABELS),
    }
    eligible = {
        _normalizar_etiqueta(PENDING_LABEL),
        _normalizar_etiqueta(REWORK_LABEL),
    }
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
        """Lista pendientes o para modificación aplicando la alternativa localmente."""
        # GitLab combina filtros múltiples de etiquetas como AND. Consultar solo
        # "Pendiente" excluía los Issues con "Requiere modificación".
        issues = self.listar_issues_abiertos(milestone_title=milestone_title)
        return [issue for issue in issues if es_issue_pendiente(issue)]
        
    def obtener_issue(self, issue_iid: int):
        """Obtiene un issue específico por su IID."""
        return self.project.issues.get(issue_iid)

    def buscar_issue_por_titulo(self, titulo_prefijo: str):
        """Busca, entre issues abiertos y cerrados, el primero cuyo título comience con el prefijo dado."""
        for state in ("opened", "closed"):
            issues = self.project.issues.list(search=titulo_prefijo, in_="title", state=state, all=True)
            for issue in issues:
                if issue.title.strip().startswith(titulo_prefijo):
                    return issue
        return None

    def crear_issue(self, titulo: str, descripcion: str, labels: Optional[List[str]] = None):
        """Crea un issue nuevo con el título y la descripción dados."""
        payload = {"title": titulo, "description": descripcion}
        if labels:
            payload["labels"] = ",".join(labels)
        return self.project.issues.create(payload)

    def actualizar_descripcion_issue(self, issue_iid: int, descripcion: str):
        """Reemplaza la descripción de un issue existente."""
        issue = self.obtener_issue(issue_iid)
        issue.description = descripcion
        issue.save()
        return issue

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

    def obtener_lenguajes_repositorio(self) -> Dict[str, float]:
        """Obtiene los lenguajes del repositorio y sus porcentajes.

        Retorna: {"TypeScript": 83.4, "JavaScript": 10.2, ...}
        """
        try:
            languages = self.project.languages()
            return languages
        except Exception:
            return {}

    def obtener_rama_predeterminada(self) -> str:
        """Obtiene la rama predeterminada del repositorio.

        Retorna: "main" o "master" según la configuración.
        """
        try:
            default_branch = self.project.default_branch
            return default_branch if default_branch else "main"
        except Exception:
            return "main"

    def obtener_arbol_repositorio(self, *, ref: Optional[str] = None) -> List[Dict[str, str]]:
        """Obtiene el árbol del repositorio (archivos y directorios).

        Args:
            ref: rama o commit. Si es None, usa la rama predeterminada.

        Retorna lista de dicts: [{"nombre": "src", "ruta": "src", "tipo": "directorio"}, ...]
        """
        try:
            ref = ref or self.obtener_rama_predeterminada()
            tree = self.project.repository_tree(ref=ref, recursive=True, get_all=True)
            return [
                {
                    "nombre": item["name"],
                    "ruta": item["path"],
                    "tipo": "directorio" if item["type"] == "tree" else "archivo",
                }
                for item in tree
            ]
        except Exception:
            return []

    def obtener_archivo_repositorio(self, ruta: str, *, ref: Optional[str] = None) -> bytes:
        """Obtiene el contenido de un archivo del repositorio.

        Args:
            ruta: ruta del archivo en el repositorio
            ref: rama o commit. Si es None, usa la rama predeterminada.

        Retorna: contenido del archivo como bytes.
        """
        try:
            ref = ref or self.obtener_rama_predeterminada()
            archivo = self.project.files.get(file_path=ruta, ref=ref)
            return archivo.decode()
        except Exception:
            return b""
