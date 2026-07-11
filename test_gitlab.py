import os
from dotenv import load_dotenv
import gitlab

print("VERSION 2 DEL SCRIPT")

load_dotenv()

gl = gitlab.Gitlab(
    url=os.getenv("GITLAB_URL"),
    private_token=os.getenv("GITLAB_TOKEN")
)

# Obtener el proyecto
project = gl.projects.get(int(os.getenv("GITLAB_PROJECT_ID")))

print("=" * 40)
print("Conexión exitosa")
print("Proyecto:", project.name)
print("=" * 40)


members = project.members.list()

for m in members:
    print(m.username, m.access_level)


# Listar issues
issues = project.issues.list(all=True)

print(f"Total de Issues: {len(issues)}")

for i in issues:
    print(f"- #{i.iid}: {i.title} ({i.state})")

# Crear un issue
new_issue = project.issues.create({
    "title": "Prueba integración MultiAgente",
    "description": """
# Historia de Usuario

Como administrador

Quiero registrar estudiantes

Para gestionar la información académica.
"""
})

print("\nIssue creado correctamente")
print("IID:", new_issue.iid)
print("URL:", new_issue.web_url)