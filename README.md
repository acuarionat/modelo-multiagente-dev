# Modelo Multiagente Dev

Herramienta multiagente para evaluación de código basado en LangGraph, LangChain y Ollama.

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

## Sublotes del Agente Central

`CENTRAL_BATCH_SIZE` configura cuántas historias procesa secuencialmente cada
invocación local del Agente Central. El valor predeterminado es `2`; pueden
probarse valores `2`, `3` o `4` y usar el mayor que resulte estable para el
hardware y la longitud de las historias.

La división no cambia métricas, prompts ni contratos. Cada sublote recibe el
mismo contexto general del proyecto, y los resultados se consolidan por
`issue_iid` restaurando el orden original. Si un sublote falla técnicamente,
solo ese grupo se subdivide hasta un mínimo de una historia. El procesamiento
local es siempre secuencial, sin inferencias de Ollama en paralelo.
