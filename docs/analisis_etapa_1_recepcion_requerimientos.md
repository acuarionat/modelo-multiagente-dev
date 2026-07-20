# Análisis de la etapa 1: recepción de requerimientos

Fecha del análisis: 2026-07-19  
Alcance: revisión estática del flujo vigente, sus entradas, procesamiento, métricas, indicadores, evaluación y salidas.  
Restricción aplicada: no se modificó el funcionamiento del proyecto.

## 1. Dictamen ejecutivo

La etapa es **útil como mecanismo de preanálisis y apoyo a la formalización**, pero **todavía no es adecuada como mecanismo autónomo de aceptación de requerimientos**. Su fortaleza principal es transformar historias de GitLab en requerimientos trazables y producir evidencia organizada por historia. Sus debilidades principales son cuatro:

1. La interfaz afirma validar las plantillas, pero el flujo solo filtra issues por estado y etiquetas; los campos esenciales no se validan antes de invocar al modelo.
2. Las métricas tienen nombres pertinentes para calidad funcional y seguridad, pero sus fórmulas miden principalmente presencia de elementos declarados por el propio modelo. No demuestran por sí solas completitud, adecuación ni seguridad real.
3. Los umbrales, ponderaciones y reglas de veredicto no tienen justificación explícita ni una matriz de decisión determinista.
4. Las salidas son amplias y útiles para revisión humana, pero algunos rótulos y estados pueden inducir interpretaciones incorrectas, especialmente `LoT` como “nivel de confianza” y la etiqueta `Analizada` aun cuando el veredicto sea `CORREGIR` o `ALERTA`.

Dictamen general: **proceso parcialmente adecuado**. Es viable para recepción asistida y generación de borradores; requiere revisión humana antes de que sus índices o veredictos se interpreten como aprobación formal.

## 2. Flujo real evaluado

1. Streamlit recibe el nombre del proyecto y la selección opcional de un milestone.
2. GitLab aporta issues abiertos con la etiqueta `Historia de Usuario`.
3. La aplicación conserva únicamente historias con `Pendiente` o `En revisión` y excluye `Analizada`.
4. Un mapeador extrae título, actor, funcionalidad, objetivo, criterios de aceptación, restricciones, prioridad, observaciones y etiquetas mediante expresiones regulares.
5. El agente Central formaliza requerimientos.
6. Calidad calcula evidencia para cobertura y adecuación funcional.
7. Seguridad calcula evidencia de controles y asignación de LoT.
8. El Evaluador emite `APROBADO`, `CORREGIR` o `ALERTA`.
9. Python consolida por `issue_iid`, renumera requerimientos y determina si la salida está estructuralmente completa.
10. El sistema muestra resultados, genera matriz CSV, PDF y DOCX, publica un comentario y actualiza etiquetas en GitLab.

Aunque conceptualmente Calidad y Seguridad son análisis independientes, el grafo vigente los ejecuta de forma secuencial: Central → Calidad → Seguridad → Evaluador → Consolidación.

## 3. Análisis de las entradas

### 3.1 Entradas actuales

Las entradas efectivas son:

- nombre del proyecto;
- milestone seleccionado;
- título y descripción de cada issue;
- etiqueta `Historia de Usuario`;
- estado abierto y etiquetas de flujo (`Pendiente`, `En revisión`, `Analizada`);
- campos extraídos: actor, funcionalidad, objetivo, criterios de aceptación, restricciones, prioridad y observaciones;
- títulos del lote como contexto resumido del sprint.

### 3.2 Aspectos adecuados

- GitLab funciona como fuente única, evitando transcripción manual.
- El `issue_iid` preserva trazabilidad desde la entrada hasta la consolidación.
- Actor, objetivo, criterios de aceptación, restricciones y prioridad son entradas pertinentes para formalizar requerimientos.
- El filtrado por milestone, tipo y estado permite procesar lotes controlados.
- El tamaño máximo de cinco historias limita el contexto de cada ejecución.

### 3.3 Hallazgos y riesgos

**Crítico — no existe una validación previa real de la plantilla.** La interfaz muestra “Validando plantillas ... con Python”, pero antes del análisis solo filtra etiquetas. El mapeador sustituye actor, objetivo y prioridad ausentes por `Desconocido`/`Desconocida`, y admite listas vacías de criterios o restricciones. Por tanto, una historia incompleta puede avanzar y el modelo puede inferir contenido que no estaba en la fuente.

**Alto — el parser depende de encabezados y sintaxis exactos.** Las secciones se extraen mediante regex sobre encabezados Markdown y `Como/Quiero/Para`. Variaciones válidas de redacción, acentos, nivel del encabezado o formato de lista pueden producir campos vacíos sin detener el proceso.

**Alto — las entradas son insuficientes para una evaluación sólida de seguridad.** No se reciben explícitamente clasificación y sensibilidad de datos, roles y permisos, límites de confianza, activos, amenazas, impacto, requisitos regulatorios, autenticación, auditoría, retención, integraciones ni superficie expuesta. El agente puede mencionarlos, pero en ese caso se trataría de inferencias, no de evidencia de entrada.

**Medio — faltan atributos de calidad del propio requerimiento.** No se capturan fuente/propietario, versión, dependencias, supuestos, definición de términos, reglas de negocio, escenarios negativos, criterio verificable por requerimiento, método de verificación ni estado de aprobación humana.

**Medio — el contexto del sprint es débil.** Se reduce a proyecto, milestone, número de historias y títulos. No contiene objetivo del sprint, alcance, dependencias o restricciones transversales, por lo que aporta poco para detectar coherencia entre historias.

### 3.4 Dictamen sobre entradas

Las entradas son **buenas como mínimo para formalización inicial**, pero **no son las mejores ni suficientes para evaluar con alta confianza** calidad funcional, seguridad y aprobación. La ausencia de datos debería bloquear o clasificar la historia como “información insuficiente”, no convertirse silenciosamente en una oportunidad de inferencia del modelo.

## 4. Análisis del procesamiento

### 4.1 Aspectos adecuados

- Separación de responsabilidades entre formalización, calidad, seguridad, evaluación y consolidación.
- Salida JSON obligatoria y asociación por `issue_iid` en vez de por posición.
- Reintento único y reparación selectiva de historias incompletas.
- Cálculo numérico en Python, evitando que el modelo invente porcentajes.
- Consolidación final determinista y exclusión de historias con errores de contenido.
- Presupuesto de salida y temperatura configurados por agente.

### 4.2 Hallazgos

**Alto — el proceso evalúa una transformación del modelo, no directamente la fuente.** Calidad y Seguridad reciben la salida formalizada por Central, no la historia original estructurada. Una omisión o invención del Central se propaga como si fuera evidencia original. Esto reduce independencia y puede amplificar errores.

**Alto — la conciliación posicional de IDs protege continuidad, pero puede ocultar una asociación errónea.** Cuando el modelo devuelve todos los elementos con IDs no válidos, el sistema puede reasignarlos según posición. Es una recuperación razonable para formato, pero no garantiza que el contenido corresponda a esa historia.

**Medio — la secuencia no es óptima en tiempo.** Calidad y Seguridad no dependen entre sí, pero se ejecutan una después de otra. Los registros históricos muestran llamadas individuales de varios cientos de segundos. Esto no invalida el resultado, pero sí afecta eficiencia.

**Medio — las reparaciones mejoran completitud de formato, no validez semántica.** El contrato comprueba tipos, presencia y textos genéricos, pero no puede verificar que un requerimiento esté realmente respaldado por el issue.

### 4.3 Dictamen sobre el proceso

El proceso está **bien estructurado técnicamente y es tolerante a fallos de formato**, pero su óptimo es parcial: privilegia continuidad y estructura sobre validez semántica. Es adecuado para producir un borrador revisable, no para reemplazar una inspección de requerimientos.

## 5. Análisis de métricas e indicadores

### 5.1 Cobertura funcional

Fórmula aplicada:

`1 - cantidad(elementos_con_problemas) / cantidad(elementos_evaluados)`

Utilidad: intenta medir funciones ausentes, ambiguas o incompletas, lo cual es pertinente para recepción.

Problemas:

- Numerador y denominador no tienen un universo claramente definido. El prompt llama “funciones esperadas” a `elementos_evaluados`, mientras los ausentes pueden no estar contenidos en esa lista.
- Las listas las genera el mismo modelo que evalúa; no existe un catálogo independiente de funciones esperadas.
- No se valida identidad, unicidad ni relación de subconjunto entre ambas listas.
- Con listas vacías, el divisor artificial es 1 y la cobertura resulta 1.0 si no hay problemas, premiando potencialmente la ausencia de evidencia.
- Todos los problemas pesan igual, sin considerar severidad o criticidad.

Dictamen: **concepto pertinente, operacionalización insuficiente**. El valor representa una razón de elementos declarados, no una prueba confiable de completitud funcional.

### 5.2 Adecuación funcional

Fórmula aplicada:

`cantidad(elementos_alineados) / cantidad(elementos_evaluados)`

Utilidad: relacionar funciones con el objetivo del usuario es apropiado para detectar requerimientos innecesarios o desalineados.

Problemas:

- La alineación es un juicio del LLM sin criterio verificable o referencia independiente.
- No se valida que los alineados pertenezcan a los evaluados.
- La lista `elementos_con_problemas` solicitada por el prompt no participa en la fórmula.
- Una función puede estar alineada con el objetivo y aun ser incorrecta, ambigua o no verificable.
- La entrada puede contener objetivo `Desconocido`; en ese caso no debería emitirse un porcentaje de adecuación.

Dictamen: **útil como indicador cualitativo asistido**, pero débil como métrica cuantitativa.

### 5.3 Índice de calidad

Fórmula aplicada:

`(cobertura_funcional + adecuacion_funcional) / 2`, meta `>= 0.95`.

Problemas:

- La ponderación 50/50 y el umbral de 95 % no están justificados por riesgo, norma, datos históricos ni decisión de negocio.
- El promedio permite compensación: una dimensión baja puede ocultarse con otra alta.
- No incluye características esenciales de calidad del requerimiento: claridad, ausencia de ambigüedad, consistencia, atomicidad, verificabilidad, factibilidad, necesidad, priorización y trazabilidad.
- La denominación “basado en ISO/IEC 25023” es demasiado fuerte si se interpreta como conformidad. La implementación usa conceptos inspirados en calidad funcional, pero no demuestra un procedimiento de medición completo ni validado contra esa norma.

Dictamen: **no suficiente para afirmar calidad global del requerimiento**. Es un índice parcial de dos señales.

### 5.4 Cobertura de controles de seguridad

Fórmula aplicada:

`cantidad(requerimientos_con_controles) / cantidad(requerimientos_evaluados)`

Utilidad: comprobar presencia de controles explícitos es pertinente cuando la historia involucra seguridad.

Problemas:

- No todo requerimiento necesita un control de seguridad explícito; exigirlo a todos puede penalizar historias sin exposición relevante.
- Contar presencia no mide idoneidad, efectividad, cobertura de amenazas ni verificabilidad del control.
- No se valida que el numerador sea subconjunto del denominador; el límite superior de 1 puede ocultar inconsistencias.
- Si la historia carece de datos de amenaza o sensibilidad, el agente debe inferir controles.

Dictamen: **indicador de documentación de controles**, no indicador de nivel de seguridad.

### 5.5 Asignación de LoT

Fórmula aplicada:

`cantidad(requerimientos_con_lot_justificado) / cantidad(requerimientos_evaluados)`

Utilidad: exigir justificación del nivel de confianza/aseguramiento puede apoyar el tratamiento proporcional al riesgo.

Problemas:

- La fórmula mide cuántos requerimientos recibieron una justificación, no si el nivel LoT-1/2/3 es correcto.
- No existe una matriz determinista que relacione impacto, exposición, sensibilidad y probabilidad con el LoT.
- Un único `lot_recomendado` por historia convive con un porcentaje por requerimientos, mezclando dos niveles de agregación.
- En las salidas se presenta LoT como “Nivel de confianza”; semánticamente puede confundirse con confianza del modelo. En este contexto debería entenderse como nivel de aseguramiento requerido para la aplicación/requerimiento.

Dictamen: **la salida categórica puede ser útil si se acompaña de criterios**, pero el porcentaje actual solo mide completitud de asignación.

### 5.6 Índice de seguridad

Fórmula aplicada:

`(cobertura_controles + cobertura_lot) / 2`, meta `>= 0.85`.

Problemas:

- Promedia dos medidas de presencia/documentación correlacionadas.
- El peso 50/50 y el umbral de 85 % no están justificados.
- Puede otorgar un valor alto aunque exista un riesgo crítico sin control, porque no incorpora severidad ni una regla de veto.
- No distingue aplicabilidad: ausencia justificada y ausencia peligrosa pueden afectar igual.

Dictamen: **no debe interpretarse como porcentaje de seguridad**. Es, como máximo, un índice de cobertura documental de seguridad.

### 5.7 Veredicto del Evaluador

El Evaluador recibe los reportes y devuelve `APROBADO`, `CORREGIR` o `ALERTA`.

Aspectos adecuados:

- categorías comprensibles;
- obligación de explicar la decisión;
- correcciones limitadas a problemas hallados previamente;
- temperatura 0 para reducir variabilidad.

Problemas:

- No existe una regla explícita que conecte índices, metas, riesgos y veredicto.
- No se exige que `APROBADO` implique metas cumplidas ni ausencia de riesgos/correcciones.
- `CORREGIR` y `ALERTA` no tienen criterios de severidad diferenciados.
- La validación solo comprueba que el texto pertenece al conjunto permitido y que hay conclusión; no verifica coherencia interna.
- El veredicto sigue siendo probabilístico aunque los porcentajes se calculen en Python.

Dictamen: **útil como síntesis narrativa, inadecuado como decisión automática de aceptación**.

## 6. Análisis de las salidas

### 6.1 Salidas correctas y útiles

- requerimientos formalizados con ID, tipo, descripción, origen, justificación y prioridad;
- ambigüedades, información faltante, restricciones y observaciones;
- evidencia y recomendaciones separadas por calidad y seguridad;
- veredicto, riesgos y correcciones;
- asociación por historia y estado de procesamiento;
- resumen global, comentario en GitLab, etiquetas, matriz CSV, PDF y DOCX;
- consolidación determinista y exclusión de historias incompletas de los promedios.

Estas salidas son útiles para analistas, product owners y revisores porque concentran la información y mantienen trazabilidad básica.

### 6.2 Limitaciones

**Alto — “status: ok” significa contrato completo, no requerimiento correcto.** Puede interpretarse erróneamente como aprobación semántica.

**Alto — la etiqueta `Analizada` se aplica también con `CORREGIR` o `ALERTA`.** El comentario propone marcar esas historias `En revisión`, pero el código les asigna `Analizada`; existe una contradicción operativa.

**Alto — no se conserva una distinción explícita entre texto fuente e inferencia.** El documento puede presentar como requerimiento formal contenido generado por el modelo sin marcar qué parte fue inferida.

**Medio — la matriz de trazabilidad no expone toda la trazabilidad disponible.** Incluye historia, requerimiento y justificación, pero no muestra el campo textual `origen`, criterio de aceptación relacionado, ambigüedad, método de verificación, responsable ni estado de aprobación.

**Medio — los promedios globales pueden ocultar historias críticas.** Un promedio de calidad o seguridad no refleja distribución, mínimo, cantidad bajo meta ni riesgos bloqueantes.

**Medio — documentos y comentario usan los índices como porcentajes.** La presentación favorece interpretarlos como medidas objetivas y comparables, aunque dependen de listas generadas por el LLM.

### 6.3 Dictamen sobre salidas

Las salidas son **correctas desde el contrato técnico y útiles como artefactos de revisión**, pero necesitan interpretación cautelosa. No constituyen evidencia suficiente de aprobación, cumplimiento normativo ni seguridad real.

## 7. Matriz resumida de adecuación

| Componente | Utilidad | Adecuación actual | Riesgo principal |
|---|---|---|---|
| Fuente GitLab y filtros | Alta | Adecuada | Dependencia de etiquetas exactas |
| Campos de historia | Alta | Parcial | Faltantes no bloquean el flujo |
| Parser Markdown | Media | Parcial | Fragilidad ante variaciones |
| Formalización Central | Alta | Parcial | Inferencias no distinguidas de la fuente |
| Validación estructural | Alta | Adecuada | Valida forma, no verdad semántica |
| Cobertura funcional | Media | Parcial/baja | Universo de conteo circular |
| Adecuación funcional | Media | Parcial | Juicio subjetivo cuantificado |
| Índice de calidad | Media | No suficiente | Omite atributos esenciales |
| Controles de seguridad | Media | Parcial | Mide presencia, no efectividad |
| LoT | Media | Parcial/baja | Mide asignación, no corrección |
| Índice de seguridad | Media | No suficiente | Puede ocultar riesgos críticos |
| Veredicto | Alta como resumen | Parcial/baja como decisión | Sin reglas deterministas |
| Salidas documentales | Alta | Adecuadas para revisión | Apariencia de resultado definitivo |
| Publicación/etiquetado | Alta | Parcial | Estado contradice el veredicto |

## 8. Recomendaciones de mejora (sin implementación)

### Prioridad crítica

1. Definir una puerta de calidad de entrada con campos obligatorios y estado “información insuficiente”.
2. Establecer una matriz de decisión explícita para `APROBADO`, `CORREGIR` y `ALERTA`, incluyendo reglas de veto por riesgo crítico.
3. Aclarar que los índices actuales representan cobertura documental estimada y no cumplimiento de ISO, calidad total ni seguridad efectiva.
4. Exigir revisión y aprobación humana antes de considerar aceptado un requerimiento formalizado.

### Prioridad alta

5. Definir el universo de cada métrica desde la fuente, reglas de pertenencia, duplicados, aplicabilidad y tratamiento de listas vacías.
6. Incorporar claridad, ambigüedad, consistencia, verificabilidad, atomicidad, factibilidad, trazabilidad y completitud de criterios de aceptación a la evaluación de calidad.
7. Incorporar datos, activos, roles, amenazas, impacto, exposición, regulaciones y criterios objetivos de LoT a la entrada de seguridad.
8. Separar en la salida “extraído de la historia”, “inferido” y “recomendado”.
9. Alinear las etiquetas de GitLab con el veredicto y la próxima acción.

### Prioridad media

10. Evaluar Calidad y Seguridad también contra la historia original, no únicamente contra la transformación del Central.
11. Mostrar mínimo, distribución, historias bajo meta y riesgos bloqueantes, además de promedios.
12. Ampliar la matriz de trazabilidad con origen textual, criterio de aceptación, método de verificación, responsable y aprobación.
13. Calibrar umbrales y ponderaciones con casos etiquetados por expertos y medir concordancia, falsos aprobados, falsos rechazos y estabilidad entre ejecuciones.
14. Considerar ejecución paralela de Calidad y Seguridad si la capacidad del modelo local lo permite.

## 9. Evidencia y cobertura de pruebas

La revisión incluyó `app.py`, el adaptador y mapeador de GitLab, el grafo, agentes, prompts, contrato de lote, utilidades de salida, registros de ejecución y pruebas unitarias.

Las 11 pruebas de `tests/test_batch_contract.py` pasan. Cubren contrato JSON, consolidación por IID, faltantes, rango del índice, reconciliación de IDs, cálculo básico de calidad, rechazo de placeholders, recomendaciones, presupuesto de salida y recuperación de JSON. No cubren:

- validación de la plantilla de entrada;
- exactitud semántica contra historias reales;
- pertenencia/duplicidad de elementos en métricas;
- casos vacíos y no aplicables;
- coherencia entre métricas, metas y veredicto;
- asignación correcta de LoT;
- consistencia de etiquetas según el veredicto;
- reproducibilidad y concordancia con evaluadores humanos.

## 10. Conclusión final

La primera etapa cumple una función valiosa: centraliza la recepción desde GitLab, formaliza historias y genera material trazable para revisión. Técnicamente, el contrato, la consolidación y el manejo de salidas incompletas están bien planteados. Sin embargo, la validez de evaluación es menor que la solidez estructural del software: las entradas no garantizan información suficiente, las métricas cuantifican listas producidas por el propio modelo, los umbrales no están fundamentados y el veredicto no tiene reglas deterministas.

Por ello, el resultado buscado es alcanzable **si se define como “borrador formalizado y diagnóstico preliminar para revisión humana”**. No es todavía adecuado si el resultado buscado es “requerimiento aprobado automáticamente, con calidad y seguridad demostradas”.
