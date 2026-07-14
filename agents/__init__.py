from langchain_ollama import ChatOllama
from core.config import OLLAMA_MODEL, OLLAMA_BASE_URL
import os

def get_llm(json_mode: bool = False, num_predict: int = 500, num_ctx: int = 4096, temperature: float = 0.1, keep_alive: str = "30m"):
    """Retorna una instancia del LLM (Ollama) configurado.
       Si json_mode es True, se fuerza la salida en formato JSON.
    """
    kwargs = {
        "model": OLLAMA_MODEL,
        "base_url": OLLAMA_BASE_URL,
        "temperature": temperature,
        "num_predict": num_predict,
        "num_ctx": num_ctx,
        "keep_alive": keep_alive
    }
    if json_mode:
        kwargs["format"] = "json"
        
    return ChatOllama(**kwargs)

def load_prompt(filename: str) -> str:
    """Carga un prompt desde la carpeta de prompts."""
    filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts', filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()
