# Auditoria de Rendimiento Nivel 2

Fecha: 2026-07-08  
Objetivo: identificar el verdadero cuello de botella antes de optimizar prompts o arquitectura.  
Alcance: analisis sin cambios funcionales.  
Baseline usada: ejecucion `execution_id=20` en `trazabilidad.db`.

## 1. Hallazgo principal

El cuello de botella real combina dos factores:

1. `Central_Final` es el nodo con mayor carga de contexto y generacion.
2. Ollama esta ejecutando `llama3:latest` en `100% CPU`, sin aceleracion GPU reportada.

La arquitectura contribuye al problema porque el nodo final recibe todos los JSON completos de los agentes anteriores y genera el documento mas largo del flujo. El modelo/hardware amplifica ese costo porque cada token se genera lentamente en CPU.

En la baseline historica:

| Agente | Tiempo | % del total |
|---|---:|---:|
| Central Init | `636.55 s` | `16.40%` |
| Calidad | `422.90 s` inferido | `10.90%` |
| Seguridad | `874.63 s` inferido | `22.53%` |
| Evaluador | `232.57 s` | `5.99%` |
| Central Final | `2137.76 s` | `55.07%` |
| Total | `3881.52 s` | `100%` |

## 2. Modelo exacto utilizado

El codigo usa `OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")`. No hay variable `OLLAMA_MODEL` activa en el entorno consultado, por lo que Ollama resuelve el modelo como `llama3:latest`.

Evidencia de `ollama list`:

| Modelo instalado | ID | Tamano |
|---|---|---:|
| `llama3:latest` | `365c0bd3c000` | `4.7 GB` |
| `llama3.1:latest` | `46e0c10c039e` | `4.9 GB` |

Evidencia de `ollama show llama3:latest`:

| Campo | Valor |
|---|---|
| Nombre completo | `llama3:latest` |
| Familia/version | Meta Llama 3, release 2024-04-18 |
| Arquitectura | `llama` |
| Parametros | `8.0B` |
| Cuantizacion | `Q4_0` |
| Context length del modelo | `8192` |
| Embedding length | `4096` |
| Capabilities | `completion` |

Parametros configurados:

| Parametro | Valor efectivo |
|---|---|
| `temperature` | `0.2`, configurado en `agents/__init__.py` |
| `format` | `json`, configurado cuando `json_mode=True` |
| `num_keep` | `24`, definido en el Modelfile de `llama3:latest` |
| `stop` | `<|start_header_id|>`, `<|end_header_id|>`, `<|eot_id|>` |
| `top_p` | Default de Ollama/modelo; no configurado en codigo |
| `top_k` | Default de Ollama/modelo; no configurado en codigo |
| `num_ctx` | No configurado por la aplicacion; `ollama ps` reporto contexto runtime `4096` al cargar el modelo |
| `num_predict` | Default de Ollama/modelo; no configurado en codigo |
| `repeat_penalty` | Default de Ollama/modelo; no configurado en codigo |
| `seed` | Default/no fijo; no configurado en codigo |

Observacion importante: aunque `ollama show` indica contexto maximo `8192`, `ollama ps` reporto `CONTEXT 4096` para el modelo cargado. Por lo tanto, la aplicacion no esta controlando explicitamente el contexto efectivo.

## 3. Hardware utilizado por Ollama

Evidencia del sistema:

| Recurso | Valor |
|---|---|
| CPU | AMD Ryzen 5 4500U with Radeon Graphics |
| Nucleos fisicos | `6` |
| Procesadores logicos | `6` |
| Frecuencia maxima reportada | `2375 MHz` |
| RAM total visible | `7.36 GB` |
| RAM libre al medir | `0.55 GB` |
| GPU | AMD Radeon(TM) Graphics integrada |
| VRAM reportada por Windows | `512 MB` |
| Sistema operativo | Microsoft Windows 11 Pro, 64 bits, version `10.0.26200` |

Evidencia de Ollama:

| Comando | Resultado relevante |
|---|---|
| `ollama ps` tras cargar `llama3:latest` | `PROCESSOR 100% CPU` |
| `ollama ps` tras cargar `llama3:latest` | `SIZE 5.3 GB` |
| `ollama ps` tras cargar `llama3:latest` | `CONTEXT 4096` |

Conclusion: Ollama esta ejecutando el modelo en CPU. No hay evidencia de aceleracion GPU. La GPU integrada tiene poca memoria reportada para descargar un modelo de ~5.3 GB, por lo que la ejecucion CPU es consistente con la evidencia.

Dato adicional: una consulta minima directa a Ollama (`responde solo: ok`) supero `60 s` y fue interrumpida por timeout. Esto confirma que la inferencia local actual es muy lenta incluso para cargas pequenas.

## 4. Velocidad de inferencia aproximada por agente

Los tokens se estiman como `caracteres / 4`, porque la ejecucion historica no guardo `prompt_eval_count`, `eval_count`, `prompt_eval_duration` ni `eval_duration` de Ollama. La instrumentacion agregada en la auditoria anterior permitira medir estos datos con mas precision en la siguiente corrida si se extiende para capturar metadatos nativos del cliente.

| Agente | Tokens entrada aprox. | Tokens salida aprox. | Tiempo | Tokens salida/s | Tokens totales/s aprox. |
|---|---:|---:|---:|---:|---:|
| Central Init | No disponible | `742` | `636.55 s` | `1.166` | No disponible |
| Calidad | `1300` | `562` | `422.90 s` | `1.329` | `4.403` |
| Seguridad | `1352` | `482` | `874.63 s` | `0.551` | `2.097` |
| Evaluador | `1456` | `66` | `232.57 s` | `0.284` | `6.544` |
| Central Final | `2441` | `1797` | `2137.76 s` | `0.841` | `1.982` |

Interpretacion: la velocidad efectiva es extremadamente baja para un flujo interactivo. La salida del Agente Central Final es grande y, en CPU, el costo de generacion domina.

## 5. Descomposicion del Agente Central Final

Prompt total reconstruido: `9722 caracteres`, aproximadamente `2431 tokens`.

| Componente | Caracteres | % del prompt | Tokens aprox. |
|---|---:|---:|---:|
| Instrucciones permanentes | `2281` | `23.46%` | `570` |
| Nombre del proyecto | `35` | `0.36%` | `9` |
| JSON Central Init | `2967` | `30.52%` | `742` |
| JSON Calidad | `2248` | `23.12%` | `562` |
| JSON Seguridad | `1927` | `19.82%` | `482` |
| JSON Evaluador | `266` | `2.74%` | `66` |
| Respuesta generada | `7189` | No aplica | `1797` |

El Agente Central Final consume tanto tiempo porque tiene simultaneamente:

| Factor | Evidencia |
|---|---|
| Mayor prompt reconstruido | `9722 chars` |
| Mayor contexto dinamico | `7411 chars` |
| Mayor respuesta generada | `7189 chars` |
| Ejecucion en CPU | `ollama ps`: `100% CPU` |
| Sin limite explicito de salida | `num_predict` no configurado |

## 6. Tamano real de prompts por agente

| Agente | Instrucciones permanentes | Datos dinamicos/contexto | Respuesta |
|---|---:|---:|---:|
| Central Init | `2427 chars` | Texto original no guardado en BD | `2967 chars` |
| Calidad | `2259 chars` | `2967 chars` del JSON Central | `2248 chars` |
| Seguridad | `2442 chars` | `2967 chars` del JSON Central | `1927 chars` |
| Evaluador | `1650 chars` | `4176 chars` Calidad + Seguridad | `266 chars` |
| Central Final | `2354 chars` | `7411 chars` Central + Calidad + Seguridad + Evaluador | `7189 chars` |

Diferenciacion:

| Tipo de informacion | Donde aparece |
|---|---|
| Instrucciones permanentes | Archivos en `prompts/*.txt` |
| Datos del proyecto | `requirements_text`, luego JSON Central |
| Resultados de otros agentes | Evaluador y Central Final |
| Documento formal y matriz | Solo Central Final |

## 7. Redundancias detectadas

### Redundancias hacia Central Final

| Informacion | Donde se repite | Puede eliminarse sin afectar resultado |
|---|---|---|
| `agente` y `etapa` | Calidad, Seguridad, Evaluador | Si. Son metadatos internos no necesarios para redactar documento final |
| `meta_cumplida` | Calidad, Seguridad y decision del Evaluador | Parcialmente. Central Final puede usar veredicto + indices |
| Recomendaciones y observaciones | Calidad/Seguridad y se sintetizan en Evaluador/conclusion | Parcialmente. Mantener solo recomendaciones finales relevantes |
| Justificaciones extensas | Calidad y Seguridad | Si para Evaluador; parcialmente para Central Final |
| Campos de plantilla de justificacion | `descripcion`, `evidencia`, `analisis`, `calculo`, `interpretacion`, `impacto`, `conclusion` | No todos son necesarios para la matriz final |
| Proyecto | Central Init y parametro `project_name` | Si. Mantener un solo origen |
| Resultado de calidad/seguridad detallado | JSON completo + columnas de matriz pedidas | Se puede reducir a metricas y resumen por requerimiento |

### Datos candidatos a eliminar o compactar antes de Central Final

| Fuente | Campos candidatos | Motivo |
|---|---|---|
| Calidad | `agente`, `etapa` | No aportan decision ni trazabilidad |
| Calidad | justificaciones completas | Para matriz bastan `FCp-1-G`, `FAp-1-G`, evidencia breve y conclusion |
| Seguridad | `agente`, `etapa` | No aportan decision ni trazabilidad |
| Seguridad | justificaciones completas | Para matriz bastan controles detectados/ausentes, LoT e impacto breve |
| Evaluador | `agente`, `etapa` | No aportan al documento final |
| Central Init | `supuestos` si vacio, `ambiguedades_detectadas` si vacio | Ruido contextual |
| Central Init | `texto_original_asociado` completo en cada requerimiento | Puede reemplazarse por referencia o extracto corto si no se exige cita completa |

## 8. Analisis del Agente Central Inicial

Salida real del Central Init:

| Campo | Tamano / conteo | Uso posterior |
|---|---:|---|
| `proyecto` | `47 chars` | Redundante con `project_name` |
| `objetivos_identificados` | `4 items`, `313 chars` | Usado por Calidad y Central Final |
| `requerimientos_funcionales` | `5 items`, `1243 chars` | Imprescindible |
| `requerimientos_no_funcionales` | `2 items`, `490 chars` | Imprescindible para Seguridad |
| `ambiguedades_detectadas` | `0 items` | No aporta si esta vacio |
| `restricciones` | `3 items`, `214 chars` | Util para documento final |
| `supuestos` | `0 items` | No aporta si esta vacio |
| `evidencias` | `2 items`, `135 chars` | Util para seguridad y trazabilidad |

Respuesta: no toda la representacion intermedia es igualmente util. Los campos vacios y metadatos duplicados pueden omitirse. El mayor campo util es `requerimientos_funcionales`; el mayor campo potencialmente reducible dentro de cada requerimiento es `texto_original_asociado`, si basta una referencia o extracto.

## 9. Analisis del Evaluador

El Evaluador recibe `4176 chars` de contexto y genera solo `266 chars`.

Campos imprescindibles:

| Fuente | Campos necesarios |
|---|---|
| Calidad | `indice`, `meta_cumplida`, recomendaciones criticas, observacion breve |
| Seguridad | `indice`, `meta_cumplida`, `lot_recomendado`, controles ausentes criticos, observacion breve |

Campos redundantes para el Evaluador:

| Fuente | Campos redundantes |
|---|---|
| Calidad | `agente`, `etapa`, justificaciones completas con siete subcampos |
| Seguridad | `agente`, `etapa`, justificaciones completas con siete subcampos |

Conclusion: el Evaluador no necesita leer toda la informacion enviada por Calidad y Seguridad para aplicar sus reglas deterministicas. Su prompt incluso indica que no debe recalcular metricas; por tanto, puede trabajar con un resumen estructurado mucho mas pequeno.

## 10. Paralelismo

Evidencia en codigo:

| Archivo | Linea logica | Significado |
|---|---|---|
| `core/graph.py` | `Central_Init -> Quality` | Rama Calidad |
| `core/graph.py` | `Central_Init -> Security` | Rama Seguridad |
| `core/graph.py` | `Quality -> Evaluator` | Evaluador espera Calidad |
| `core/graph.py` | `Security -> Evaluator` | Evaluador espera Seguridad |

Evidencia de runtime local:

| Prueba | Resultado |
|---|---|
| Grafo minimo con dos nodos hermanos `sleep(2)` | Ambos nodos iniciaron en el mismo segundo |
| Duracion total | `~2.01 s` |
| Duracion esperada si fuera secuencial | `~4 s` |

Evidencia historica:

| Registro | Hora |
|---|---|
| Central Init finaliza | `19:58:36` |
| Calidad finaliza | `20:05:38` |
| Seguridad finaliza | `20:13:10` |

Limitacion: la BD historica solo registro finalizacion de agentes, no inicio. Por eso no demuestra por si sola si Calidad y Seguridad corrieron solapadas en esa ejecucion. La instrumentacion anterior ya agrega `node_start` y `agent_start`; una nueva corrida completa permitira confirmar paralelismo real con evidencia directa.

Limitacion tecnica probable: aunque LangGraph lance ambas ramas en paralelo, Ollama esta en `100% CPU`. Dos inferencias concurrentes pueden competir por la misma CPU/RAM y no duplicar rendimiento. En hardware limitado, paralelismo puede mejorar latencia total solo si Ollama atiende ambas solicitudes sin serializarlas y sin saturar memoria.

## 11. Modelo vs arquitectura

Estimacion cualitativa del tiempo:

| Factor | Peso estimado | Evidencia |
|---|---:|---|
| Modelo/hardware | `60-75%` | Llama 3 8B Q4 en `100% CPU`, consulta minima >60 s, baja tokens/s |
| Arquitectura/contexto | `25-40%` | Central Final recibe `7411 chars` dinamicos y genera `7189 chars` |

Interpretacion: el problema no es solo el Agente Central Final. El nodo final es el punto donde se acumula el costo arquitectonico, pero el tiempo extremo se explica por ejecutar un modelo 8B en CPU con poca RAM libre.

## 12. Optimizaciones priorizadas sin cambiar arquitectura

| Prioridad | Optimizacion | Problema identificado | Reduccion estimada del tiempo total | Dificultad |
|---:|---|---|---:|---|
| 1 | Limitar `num_predict`, sobre todo en Central Final | Salida final de `7189 chars` sin limite explicito | `15-35%` | Muy baja |
| 2 | Reducir el contexto de Central Final a resumen estructurado | Central Final recibe todos los JSON completos | `20-40%` | Baja |
| 3 | Compactar justificaciones de Calidad y Seguridad antes de Evaluador/Central Final | Campos largos no necesarios para decision | `10-25%` | Baja |
| 4 | Usar un modelo mas pequeno para Evaluador y posiblemente Calidad/Seguridad | Tareas con salida pequena no requieren 8B siempre | `20-50%` | Media |
| 5 | Configurar `num_ctx` explicitamente | Runtime reporta `4096`, codigo no controla contexto | `0-10%` directo, alto valor de estabilidad | Muy baja |
| 6 | Revisar modelo alternativo mas eficiente (`llama3.1:latest` no necesariamente mas rapido) | `llama3:latest` Q4_0 en CPU es lento | `10-40%` segun modelo | Media |
| 7 | Separar documento final en formato mas compacto o plantilla deterministica | El LLM redacta demasiado contenido formal | `25-55%` | Media |
| 8 | Confirmar paralelismo real con logs y ajustar concurrencia | CPU saturada puede hacer que paralelo no ayude | `0-25%` | Media |

Tabla solicitada de impacto esperado:

| Optimizacion | Reduccion estimada del tiempo | Complejidad |
|---|---:|---|
| Reducir contexto del Agente Central Final | `20-40%` | Baja |
| Eliminar informacion redundante entre agentes | `10-25%` | Baja |
| Limitar `num_predict` | `15-35%` | Muy baja |
| Ejecutar Calidad y Seguridad en paralelo real, si Ollama lo permite | `0-25%` adicional | Media |
| Cambiar a un modelo mas pequeno para ciertos agentes | `20-50%` | Media |
| Generar parte del documento final con plantilla deterministica | `25-55%` | Media |

## 13. Respuestas directas

### Cual es el verdadero cuello de botella

El cuello de botella visible es `Central_Final`, pero la causa raiz es mixta: acumulacion de contexto + generacion larga + Llama 3 8B ejecutandose en CPU.

### Que porcentaje depende del modelo y que porcentaje depende de arquitectura

Estimacion: `60-75%` modelo/hardware, `25-40%` arquitectura/contexto. La evidencia mas fuerte para modelo/hardware es `ollama ps: 100% CPU` y la consulta minima >60 s. La evidencia mas fuerte para arquitectura es que `Central_Final` concentra el mayor prompt y la mayor salida.

### Que informacion circula innecesariamente

Metadatos (`agente`, `etapa`), campos vacios (`supuestos`, `ambiguedades_detectadas` cuando no contienen datos), justificaciones completas para agentes que solo necesitan decision, y duplicacion de `project_name/proyecto`.

### Que optimizaciones reducen mas tiempo sin cambiar arquitectura

Primero limitar salida (`num_predict`) y compactar `Central_Final`. Luego resumir Calidad/Seguridad para Evaluador y Central Final. Despues evaluar modelo mas pequeno por agente o generacion final parcialmente deterministica.

## 14. Siguiente evidencia recomendada

Antes de implementar optimizaciones, ejecutar una corrida completa con la instrumentacion `PERF_AUDIT` activa y guardar:

| Dato | Para que sirve |
|---|---|
| `agent_start` / `agent_end` | Confirmar paralelismo real |
| `prompt_size` / `response_size` | Validar tamanos reales |
| `ollama ps` durante Calidad/Seguridad | Ver CPU/GPU y contexto activo |
| Metadatos nativos de Ollama si se capturan | Obtener tokens exactos y tokens/s reales |

Con esa corrida se puede reemplazar la estimacion `chars/4` por tokens exactos.
