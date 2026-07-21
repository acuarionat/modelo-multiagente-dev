import os
from pathlib import Path

# Rutas principales del proyecto
BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.path.join(BASE_DIR, "trazabilidad.db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Configuraciones de IA (Ollama Local)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Las historias sin los campos mínimos se conservan para seguimiento, pero no se
# envían al modelo salvo que el responsable habilite explícitamente esta opción.
ALLOW_INCOMPLETE_STORIES = os.getenv("ALLOW_INCOMPLETE_STORIES", "false").strip().casefold() in {
    "1", "true", "yes", "si", "sí",
}

# Asegurarse de que el directorio de logs exista
os.makedirs(LOGS_DIR, exist_ok=True)
