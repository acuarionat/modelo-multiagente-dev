# Modelo Multiagente Dev

Sistema multiagente para evaluación de código basado en LangGraph, LangChain y Ollama.

## Arquitectura

El sistema utiliza un orquestador (Agente Central) para enrutar tareas. Los análisis de calidad (Radon) y seguridad (Semgrep) se ejecutan en paralelo. Un Evaluador dictamina, y el Agente Central consolida los resultados.

## Configuración Inicial

1. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Ollama**:
   Asegúrate de tener [Ollama](https://ollama.com/) corriendo de forma local con el modelo `llama3` u otro de tu elección.
   ```bash
   ollama run llama3
   ```
3. **Ejecutar**:
   ```bash
   streamlit run app.py
   ```
