# Contexto: Proyecto modelo-multiagente-dev — Módulo de Diseño completo + integración UI + corrección de consistencia TRZ-001

Repo: `modelo-multiagente-dev` (rama `feature/etapa-diseno`). Este documento continúa exactamente donde terminó una sesión anterior (cuyo resumen describía Fases 1–4: mapper, contrato de entrada, contexto, Central de Diseño, y el arranque de Calidad de Diseño). En **esta** conversación se completó **todo** el módulo de Diseño de punta a punta: Seguridad, Evaluador, integración en el grafo, matriz de trazabilidad evolucionada, exportación CSV/XLSX, comentario y publicación real en GitLab, PDF/DOCX, integración en la interfaz Streamlit, el flujo completo de entrada de matriz previo a Diseño (TRZ-001), y una corrección de un bug real de consistencia de datos ya verificada en producción.

## Regla arquitectónica seguida en todo el módulo (sin excepción)

No se crean carpetas nuevas. Todo vive en las carpetas existentes (`agents/`, `core/`, `integrations/`, `prompts/`, `tests/`) usando el prefijo `design_` (o, para el flujo de matriz de trazabilidad compartido entre Requerimientos y Diseño, `traceability_`). Sin prefijo = Recepción de Requerimientos; `design_`/`traceability_` = Diseño / matriz compartida.

**Estilo de trabajo del usuario (muy importante para la próxima sesión):** instrucciones extremadamente estrictas y por fases, con lista explícita de archivos permitidos ("No toques nada más"), "no inventes mejoras, no agregues lógica extra", "no realices pruebas más allá de lo indicado". Toda validación se hace con datos reales de GitLab y LLM reales (NVIDIA/Groq), nunca mocks — excepto cuando la cuota diaria de Groq se agotó (ver más abajo), momento en el que el usuario autorizó explícitamente congelar resultados reales ya obtenidos como fixtures para pruebas de regresión, dejando la validación real como pendiente aparte. Cuando surge ambigüedad, se resuelve consultando datos reales (GitLab, base de datos) en vez de adivinar. Cuando aparece un bug real durante pruebas, se corrige dentro de los archivos ya autorizados para esa fase.

## Estado real en GitLab (proyecto "elanvital", sin mocks)

- Milestone "Diseño": DIS-001 (issue_iid 16, Consulta de horarios), DIS-002 (issue_iid 17, Registro de pacientes) — ambos con entrada válida. DIS-003 (issue_iid 18, Consulta de agenda médica) referencia RF-009/RF-010, que **no existían** en la matriz de 11 requerimientos original → queda bloqueado intencionalmente (`referencias_invalidas` no vacío), nunca se envía a los agentes LLM. **Confirmado en vivo**: si esos códigos llegan a existir en la matriz vigente (p. ej. porque se formalizó la HU que los define), DIS-003 se desbloquea automáticamente — comportamiento verificado con el navegador, no es un bug.
- **TRZ-001 — Matriz de Trazabilidad** (Issue #19): existe y **ya tiene el contenido correcto** (11 filas reales: RF-001..RF-008, RNF-001..RNF-003), republicado manualmente al final de esta sesión tras corregir el bug de consistencia (ver Fase 14). Antes de esa corrección tuvo contenido corrupto por ~un día real (creado 2026-08-09T17:19, corregido el mismo día).
- Un comentario real de retroalimentación de Diseño ya fue publicado en el Issue #16 (DIS-001) durante la Fase 10 (nota id `3664150836`) — sirvió para validar `publicar_comentario_diseno` en producción.

## Arquitectura de proveedores LLM resultante (sin cambios en esta sesión salvo lo ya descrito antes)

```
Requerimientos:  Central(NVIDIA GLM-5.2) → Calidad(Groq gpt-oss-120b) → Seguridad(Groq gpt-oss-120b) → Evaluador(NVIDIA GLM-5.2) → Central Final (Python puro)
Diseño:          GitLab → design_issue_mapper → design_context → Central(NVIDIA) → Calidad(Groq) → Seguridad(Groq) → Evaluador(NVIDIA) → Central Final (Python puro)
```

`core/llm_factory.py` no tuvo que tocarse en ninguna fase de esta sesión: el gate NVIDIA ya cubría `{"central","evaluator"}` y el gate Groq ya cubría `{"quality","security"}`, y los agentes de Diseño reutilizan esos mismos roles literales (`"central"`, `"quality"`, `"security"`, `"evaluator"`) — nunca se creó un alias `"design_*"` adicional.

## ⚠️ Cuota de Groq

Durante esta sesión la cuota diaria de Groq (200 000 tokens/día) se agotó por las muchas ejecuciones reales del pipeline completo de Diseño (cada corrida consume ~10 000-20 000 tokens en 2 llamadas Groq por DIS). Si al retomar la sesión el pipeline real de Diseño vuelve a fallar con `RemoteLLMError: REMOTE_RATE_LIMIT` / `groq.RateLimitError`, **no es un bug**: hay que esperar a que la cuota se libere (el propio error de Groq indica cuánto tiempo esperar) o usar las fixtures ya congeladas (`tests/fixtures_diseno.py`) para pruebas de regresión sin gastar cuota.

## Fases completadas en ESTA conversación (orden cronológico exacto)

### Fase 5 — Agente de Seguridad de Diseño (MS-03 Cobertura de Amenazas, MS-04 Cobertura de Controles)
Creados: `agents/design_security_agent.py`, `prompts/design_security_prompt.txt`, `tests/test_design_security.py`.
Modificados: `core/design_metrics.py` (+`calcular_ms03`, `calcular_ms04`), `core/design_contract.py` (+`validar_salida_seguridad_diseno`).
Provider: Groq (`obtener_llm_para_agente("security", ...)` literal, sin alias; `REMOTE_PACER` igual que Seguridad de Requerimientos). Validado con DIS-001 (MS-03=67%, MS-04=75%, "Protección de datos" correctamente detectado como faltante) y DIS-002 (MS-03=100%, MS-04=75%) reales.

### Fase 6 — Agente Evaluador de Diseño
Creados: `agents/design_evaluator_agent.py`, `prompts/design_evaluator_prompt.txt`, `tests/test_design_evaluator.py`.
Modificados: `core/design_contract.py` (+`validar_salida_evaluador_diseno`).
Provider: NVIDIA, igual patrón que `design_central_agent.py` (sin `REMOTE_PACER`). Regla de oro: el Evaluador nunca recalcula ni contradice MC-03/MC-04/MS-03/MS-04 ya calculados por Python; solo produce `conclusion_calidad`, `conclusion_seguridad`, `correcciones_necesarias`, `precisiones_necesarias`, `oportunidades_mejora`. Validado con DIS-001/DIS-002 reales.

### Fase 7 — Integración en `core/graph.py` (grafo independiente de Diseño)
Modificados: `core/state.py` (+9 campos `design_*`), `core/graph.py` (+5 nodos: `nodo_design_central`, `nodo_design_quality`, `nodo_design_security`, `nodo_design_evaluator`, `nodo_design_central_final`, + `construir_grafo_diseno()`).
**Bug real encontrado y corregido dentro del mismo archivo autorizado**: el diagrama pedía Quality y Security en paralelo desde Central; LangGraph los ejecuta de verdad en hilos concurrentes, lo que rompía el espaciado de `REMOTE_PACER` (pensado para llamadas secuenciales) y disparaba `RateLimitError`. Se corrigió encadenando `Design_Quality → Design_Security` de forma secuencial (única desviación intencional del diagrama, documentada).
Creado: `tests/test_design_full_flow.py`. Validado end-to-end real: DIS-001 (Índice Calidad=100%, Índice Seguridad=71%, CORREGIR), DIS-002 (100%/88%, CORREGIR), DIS-003 bloqueado con 0 llamadas.

### Fase 8 — Matriz de trazabilidad evolucionada (Requerimientos → Diseño)
Creados: `core/design_traceability.py` (`normalizar_matriz_requerimientos`, `evolucionar_matriz_a_diseno`, `construir_filas_matriz_diseno`, `resumir_trazabilidad_diseno`, `construir_metadata_matriz_diseno`; constantes `ESTADOS_TRAZABILIDAD_DISENO` y `ETIQUETAS_ESTADO`), `tests/test_design_traceability.py`.
Estructura de fila visible (10 columnas, contrato **estable**, ya congelado):
`HU origen | Código requisito | Tipo | Nombre del requisito | Descripción | Diseño | Elementos de Diseño | Estado de trazabilidad | Estado de Diseño | Observación`.
Estados cerrados: `CUBIERTO` (confianza alta), `PENDIENTE_RELACION` (sin relación evidente), `REQUIERE_REVISION` (confianza media/baja), `NO_EVALUADO` (nunca contextualizado por ningún DIS). El LLM nunca decide el texto visible.

### Fase 9 — Exportación CSV/XLSX
Creado: `core/traceability_export.py` (`exportar_csv_excel` con `delimiter=";"` + `utf-8-sig`, `exportar_filas_xlsx` con openpyxl: encabezados, fila 1 congelada, filtros, columnas ajustadas, wrap_text).
**Bug real corregido**: el CSV de Requerimientos existente (`core/utils.py::generar_artefactos_atomicos`) usaba `csv.DictWriter` sin delimitador → "todo en una columna" en Excel con configuración regional en español. Corregido delegando en `exportar_csv_excel`.
Dependencia nueva: `openpyxl` (agregada a `requirements.txt`).
Creado: `tests/test_traceability_export.py`.

### Fase 8b — Contrato visible actualizado
`tests/test_design_traceability.py` se actualizó al contrato de 10 columnas (antes eran 9, con "Requerimiento" combinado) y a `ETIQUETAS_ESTADO` (antes `ESTADOS_TRAZABILIDAD` con claves en minúsculas). Este es el contrato **vigente**.

### Fase 10 — Comentario de GitLab para Diseño
Modificado: `integrations/issue_service.py` (+`construir_comentario_diseno(resumen_diseno)`, +`publicar_comentario_diseno(project_id, issue_iid, resumen_diseno)` — reutiliza `GitLabAdapter.agregar_comentario`, con guards: rechaza resumen vacío y estado `"ERROR"`).
Creados: `tests/test_design_gitlab_comment.py` (construcción/validación de texto), `tests/test_design_gitlab_publish.py` (modo seguro por defecto; `PUBLISH_GITLAB_TEST=1` publica de verdad).
**Publicación real ejecutada** (autorizada explícitamente por el usuario): comentario publicado en Issue #16 (DIS-001), nota id `3664150836`.

### Fase 11 — PDF/DOCX de Diseño
Modificado: `core/utils.py` (+`generar_reporte_diseno_pdf(...)`, +`generar_documento_formal_diseno_docx(...)`, reutilizando helpers FPDF/python-docx ya existentes de Requerimientos). El DOCX **nunca** muestra MC-03/MC-04/MS-03/MS-04 (eso es solo del PDF); los aspectos sin evidencia se marcan literalmente como "Aspecto pendiente: ... / Propuesta de formalización: ... / Estado: Pendiente de revisión." — nunca se afirma que algo está documentado si no lo está.
Creados: `tests/fixtures_diseno.py` (capturas reales congeladas de NVIDIA/Groq de esta misma sesión — `RESULTADOS_CENTRAL_DISENO`, `EVALUACION_POR_DISENO`, `DESIGN_SUMMARY_POR_DISENO`, `CONCLUSIONES_EVALUADOR_DISENO`, `RESULTADOS_SECURITY_DISENO` — usadas en todas las pruebas de regresión sin gastar cuota de Groq), `tests/test_design_documents.py`.
Dependencia nueva: `pypdf` (para validar el contenido del PDF generado; agregada a `requirements.txt`).

### Fase 12 — Integración en la interfaz (Streamlit)
Creado: `core/design_ui.py` (dado que `app.py` ya tenía ~1750 líneas). Contiene 4 funciones puras de preparación de datos (testeables sin Streamlit) + `render_design_stage(...)` con los 4 bloques: A. Entrada de trazabilidad, B. Issues detectados, C. Ejecución del análisis, D. Resultados en pestañas (Resumen/Calidad/Seguridad/Trazabilidad/Formalización) + descargas de artefactos + publicación a GitLab solo por botón explícito.
Modificado: `app.py` — cambio mínimo (1 import + guard de 7 líneas `if stage_id == "diseno": render_design_stage(...); st.stop()`), sin reindentar nada del bloque de Requerimientos existente. Efecto colateral descubierto y corregido: Codificación/Pruebas antes caían silenciosamente al flujo de Requerimientos (bug preexistente); ahora muestran correctamente el placeholder "Próximamente".
Creado: `tests/test_design_ui_data.py`.
Verificado en vivo con el navegador (Streamlit real, sin ejecutar el análisis para no gastar cuota).

### Fase 13 — Flujo de entrada de matriz previo a Diseño (TRZ-001), 9 sub-fases
Objetivo: antes de ejecutar el análisis de Diseño, el responsable debe **ver** la matriz de Requerimientos vigente, saber si es original/editada/inválida, y confirmarla explícitamente.
- **FASE 1 (GitLab)**: `integrations/traceability_issue_mapper.py` (nuevo — construcción/parseo de Markdown de TRZ-001), `integrations/gitlab_adapter.py` (+`buscar_issue_por_titulo`, `crear_issue`, `actualizar_descripcion_issue`), `integrations/issue_service.py` (+`obtener_issue_matriz_trazabilidad`, +`crear_o_actualizar_issue_matriz_trazabilidad`, +`construir_matriz_requerimientos_original`; hook automático al final de `procesar_flujo_lote()` — **este hook tenía el bug corregido en la Fase 14**).
- **FASE 2**: `core/design_matrix_input.py` (nuevo) — `ESTADO_MATRIZ_ORIGINAL/EDITADA/INVALIDA`, `validar_matriz_entrada_diseno`, `comparar_matrices_requerimientos`, `preparar_matriz_entrada_diseno`.
- **FASE 3**: `core/traceability_export.py` (+`importar_matriz_xlsx`, +`importar_matriz_csv`).
- **FASE 4**: `core/design_context.py` — parámetro renombrado `matriz_trazabilidad` → `matriz_entrada_diseno` (sin cambio de comportamiento).
- **FASE 5**: `core/state.py` (+8 campos de matriz: `matriz_requerimientos_original`, `matriz_entrada_diseno`, `matriz_estado`, `matriz_fuente`, `matriz_confirmada`, `matriz_validacion`, `matriz_cambios_pre_diseno`, `matriz_diseno_evolucionada`).
- **FASE 6**: 4 tests sin LLM (`test_traceability_issue_mapper.py`, `test_design_matrix_input.py`, `test_traceability_import.py`, `test_traceability_gitlab_sync.py`).
- **FASE 7**: reescritura completa del Bloque A de `core/design_ui.py` — tarjeta de procedencia/estado, tabla de 6 columnas, cambios detectados, botones Editar en GitLab/Excel, carga de matriz modificada, sincronización opcional Excel→GitLab, checkbox de confirmación, snapshot al ejecutar.
- **FASE 8/9**: `core/graph.py` (`matriz_metadata` dentro de `design_summary`), `core/utils.py` (encabezado "Matriz de entrada" opcional en PDF/DOCX).
Verificado en vivo con el navegador: prevalidación, tabla, checkbox de confirmación habilitando correctamente el botón de análisis, y **confirmación real de que DIS-003 se desbloquea** cuando sus referencias existen en la matriz vigente.

### Fase 14 — Corrección de bug real: TRZ-001 con datos inconsistentes
**Síntoma real**: TRZ-001 publicado con `RF-001 = "Validar documento de identidad..."` en vez del contenido real (`RF-001 = "Mostrar únicamente horarios disponibles"`).
**Causa raíz identificada con evidencia**: `renumerar_requerimientos()` (preexistente, sin tocar) reasigna IDs secuenciales sobre el conjunto que se le pase. `construir_matriz_requerimientos_original()` agregaba **todo** `cache_results` (docenas de ejecuciones históricas independientes, cada una ya renumerada por separado) y volvía a renumerar esa mezcla, emparejando IDs con contenido que no les correspondía.
**Corrección**:
- `core/utils.py`: nueva `construir_filas_matriz_requerimientos_final(requerimientos_formalizados, fecha_generacion)` como única función que da forma a una fila oficial; `construir_filas_trazabilidad()` ahora delega en ella internamente (mismo comportamiento externo, cero rupturas).
- `integrations/issue_service.py`: el hook de `procesar_flujo_lote()` ahora construye `filas_matriz_requerimientos_actual` directamente desde `batch_result["issues"]` (en memoria, solo la ejecución actual) y llama a una `crear_o_actualizar_issue_matriz_trazabilidad(project_id, filas_matriz, metadata=None)` **pasiva** (ya no lee `cache_results`). Nueva `validar_consistencia_matriz_publicacion(filas_oficiales, filas_trz)` (round-trip antes de publicar). `construir_matriz_requerimientos_original(resultados_lote_actual)` ahora exige el parámetro explícito (se conserva solo para pruebas/recuperación).
- `integrations/traceability_issue_mapper.py`: cambiado al contrato de 7 columnas (`core.utils.TRACEABILITY_COLUMNS`, reutilizado directamente — antes eran 6 columnas en minúsculas, contrato distinto al de CSV/XLSX).
- Ripple necesario (no pedido explícitamente pero indispensable para no romper la Fase 13): `core/design_ui.py::_cargar_entrada_desde_gitlab` y el botón de sincronización ahora usan un helper local `_todos_los_resultados_cache()` — la comparación de "matriz original" de la UI de Diseño **sigue** usando `cache_results` (limitación conocida, separada, no arreglada en esta fase porque no era el bug reportado).
- Creado: `tests/test_requirements_to_trz_consistency.py` (fixture real de 11 requisitos, confirma que `RF-001` es el correcto, confirma que contenido ajeno —incluida la frase exacta del bug real— nunca aparece, confirma que el round-trip por Markdown no renumera).
- Se corrigieron 2 tests que el cambio de contrato rompía: `tests/test_traceability_issue_mapper.py`, `tests/test_traceability_gitlab_sync.py`, `tests/test_traceability_import.py`.
- **TRZ-001 (#19) fue republicado realmente en GitLab** con el usuario aprobando explícitamente, y se verificó leyendo de vuelta que ahora tiene las 11 filas correctas.

## Archivos nuevos creados en esta conversación

```
agents/design_security_agent.py
agents/design_evaluator_agent.py
prompts/design_security_prompt.txt
prompts/design_evaluator_prompt.txt
core/design_traceability.py
core/traceability_export.py
core/design_matrix_input.py
core/design_ui.py
integrations/traceability_issue_mapper.py
tests/fixtures_diseno.py
tests/test_design_security.py
tests/test_design_evaluator.py
tests/test_design_full_flow.py
tests/test_design_traceability.py
tests/test_traceability_export.py
tests/test_design_gitlab_comment.py
tests/test_design_gitlab_publish.py
tests/test_design_documents.py
tests/test_design_ui_data.py
tests/test_traceability_issue_mapper.py
tests/test_design_matrix_input.py
tests/test_traceability_import.py
tests/test_traceability_gitlab_sync.py
tests/test_requirements_to_trz_consistency.py
```

(Nota: `agents/design_central_agent.py`, `agents/design_quality_agent.py`, `prompts/design_central_prompt.txt`, `prompts/design_quality_prompt.txt`, `core/design_context.py`, `core/design_contract.py`, `core/design_metrics.py`, `integrations/design_issue_mapper.py` y sus tests correspondientes son de la sesión **anterior**, no de esta.)

## Archivos modificados en esta conversación

- `core/state.py` — 17 campos nuevos en total (`design_*` de la sesión anterior no tocados; +9 de integración del grafo; +8 de matriz de entrada).
- `core/graph.py` — 5 nodos de Diseño + `construir_grafo_diseno()` + `matriz_metadata` en `design_summary`.
- `core/utils.py` — CSV de Requerimientos corregido (delimitador), `construir_filas_matriz_requerimientos_final` (nueva, única fuente), `generar_reporte_diseno_pdf`, `generar_documento_formal_diseno_docx` (+parámetro opcional `matriz_metadata`).
- `core/design_context.py` — parámetro renombrado (`matriz_entrada_diseno`).
- `integrations/gitlab_adapter.py` — +`buscar_issue_por_titulo`, +`crear_issue`, +`actualizar_descripcion_issue`.
- `integrations/issue_service.py` — funciones de Diseño (comentario, publicación) + todo el flujo TRZ-001 (creado y luego corregido en la Fase 14).
- `app.py` — 1 import + guard de 7 líneas para la etapa "diseno".
- `requirements.txt` — +`openpyxl`, +`pypdf`.
- `agents/evaluator_agent.py`, `core/llm_factory.py` — de la sesión **anterior** (migración a NVIDIA), no tocados en esta.

## Explícitamente NO hecho todavía (a propósito)

- No se integró la matriz de trazabilidad definitiva (Codificación/Pruebas no existen todavía).
- El botón "Iniciar análisis de Diseño" de la interfaz **nunca se presionó de verdad** en esta sesión (para no gastar la cuota de Groq); todo lo demás del flujo de matriz de entrada sí se verificó en vivo.
- La comparación de "matriz original" dentro de `core/design_ui.py` sigue usando `cache_results` agregado (limitación conocida, deliberadamente fuera del alcance de la Fase 14 porque el bug reportado era específicamente sobre el hook de publicación de TRZ-001, no sobre la UI de Diseño).
- No se ha vuelto a ejecutar una validación real completa del pipeline de Diseño (Central→Calidad→Seguridad→Evaluador) desde que se corrigió el paralelismo de `REMOTE_PACER` combinada con el flujo de matriz de entrada nuevo — las últimas ejecuciones reales completas fueron antes de la Fase 13.
- Pendiente sin resolver de sesiones anteriores: el fallo `SECURITY_DATA_UNCLASSIFIED` del Agente de Seguridad de **Requerimientos** en el Issue #6 (confirmado que no lo causó ningún cambio de Diseño; nunca se investigó a fondo).

## Cómo retomar en la próxima sesión

1. Confirmar la cuota de Groq (si sigue agotada, usar `tests/fixtures_diseno.py` para cualquier prueba de regresión; no repetir corridas reales completas sin necesidad).
2. Si se va a ejecutar el análisis de Diseño real por primera vez desde la interfaz (botón "Iniciar análisis de Diseño"), verificar primero que TRZ-001 sigue correcto (`python -m tests.test_traceability_gitlab_sync`, modo lectura, sin publicar).
3. Todo el trabajo pendiente explícito del usuario está en la sección anterior — no inventar la siguiente fase, esperar instrucciones igual de estrictas y por fases como las de esta sesión.
