import os
from pathlib import Path

# Rutas principales del proyecto
BASE_DIR = Path(__file__).parent.parent
DB_PATH = os.path.join(BASE_DIR, "trazabilidad.db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Configuraciones de IA (Ollama Local)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Asegurarse de que el directorio de logs exista
os.makedirs(LOGS_DIR, exist_ok=True)
