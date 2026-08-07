CONTEXTO DE CONTINUIDAD – MODELO MULTIAGENTE
Proyecto de Grado – Recepción de Requerimientos
1. Objetivo del sistema

Desarrollar un modelo multiagente híbrido que automatice el control, seguimiento y evaluación del proceso de desarrollo de software durante cuatro etapas:

Recepción de requerimientos.
Diseño.
Codificación.
Pruebas.

Actualmente solo se encuentra implementada y en validación la primera etapa (Recepción de Requerimientos).

El sistema analiza automáticamente historias de usuario provenientes de GitLab, genera requerimientos formales, evalúa calidad y seguridad mediante agentes especializados, emite un veredicto por historia y genera la documentación final (PDF, DOCX y CSV).

2. Arquitectura de agentes

Arquitectura híbrida:

GitLab
   │
   ▼
Agente Central (Ollama - phi4-mini)
   │
   ├── preparación de historias
   ├── recuperación
   ├── reparación selectiva
   └── complementación documental
          │
          ▼
────────────────────────────────────────────
        PARALELO
────────────────────────────────────────────

Agente Calidad
Groq
openai/gpt-oss-120b

Agente Seguridad
Groq
openai/gpt-oss-120b

────────────────────────────────────────────
          │
          ▼

Agente Evaluador
Ollama - phi4-mini

          │
          ▼

Central Final (Python)

          │
          ▼

PDF
DOCX
CSV
JSON

No existe comunicación directa entre Calidad y Seguridad.

Toda la orquestación la realiza LangGraph.

3. Estado de la rama

Rama activa:

feature/hybrid-llm-quality-security

No existen commits pendientes autorizados.

No realizar:

commit
push
merge
rebase

Todos los cambios permanecen únicamente en el repositorio local.

4. Configuración híbrida
Modelos
Central

Proveedor:

Ollama

Modelo:

phi4-mini
Calidad

Proveedor:

Groq

Modelo:

openai/gpt-oss-120b
Seguridad

Proveedor:

Groq

Modelo:

openai/gpt-oss-120b
Evaluador

Proveedor:

Ollama

Modelo:

phi4-mini

Pipeline actual:

Central
      │
      ▼
Calidad
      │
      ▼
Seguridad
      │
      ▼
Evaluador
      │
      ▼
Central Final
5. Cambios ya realizados
Central

Implementado:

recuperación por sublotes 2+2+1.
reparación selectiva por historia.
validación estricta de issue_iid.
validación de historia_id.
recuperación de JSON parcial.
clasificación:
ok
informacion_insuficiente
error
historias trazables.
historias analizables.
historias no evaluables.
conservación del orden.
prohibición de mezcla entre historias.
Calidad

Implementado completamente:

MC-01.
MC-02.
Índice de Calidad.
validación contractual.
validación semántica.
universo funcional.
separación RF/RNF.
funciones principales.
reglas contextuales.
deduplicación canónica.
conciliación de equivalencias.
auditoría.
particiones.
diagnósticos.
validación llm_raw.
validación post_python.
Seguridad

Implementado completamente:

MS-01.
MS-02.
Índice de Seguridad.
LoT.
universo canónico de datos.
clasificación explícita.
clasificación inferida.
extracción estructurada.
validación semántica.
conciliación texto/objeto.
datos canónicos.
rechazo de datos externos.
rechazo de agrupaciones genéricas.
recomendaciones automáticas.
auditoría completa.
Evaluador

Implementado:

veredicto determinista:

APROBADO

REVISIÓN REQUERIDA

CORREGIR

No sustituye métricas.

Solo consolida.

Consolidación documental

Implementado:

consolidación RF.
consolidación RNF.
deduplicación documental.
conservación de procedencias.
recomendaciones limpias.
eliminación de estructuras dict visibles.
consolidación idempotente.
Integridad

Implementado:

historias:

esperadas

trazables

analizables

no evaluables

Ninguna historia desaparece durante el pipeline.

6. Pruebas reales superadas

Se ejecutaron pruebas reales con Groq y Ollama.

Superadas:

Central

✔ recuperación completa

✔ reparación selectiva

✔ identidad

✔ orden

✔ trazabilidad

Calidad

HU-006

HU-007

HU-008

HU-009

HU-010

Todas:

MC-01 = 1.00

MC-02 = 1.00

Validación semántica:

success
Seguridad

HU-006

HU-007

HU-008

HU-009

HU-010

Resultados esperados.

Especialmente:

HU-010

MS-01 = 1.00

MS-02 = 0.00

Índice = 0.50

LoT-2

No cumple
Pipeline completo

Se ejecutó completamente:

Central

↓

Calidad

↓

Seguridad

↓

Evaluador

↓

Central Final

Los agentes finalizaron correctamente.

No hubo:

fallback
retry
mezcla de historias
errores HTTP
errores JSON
7. Problemas ya corregidos

Corregidos:

✓ reparación selectiva.

✓ historias ausentes.

✓ universos funcionales.

✓ reglas contextuales.

✓ HU-010.

✓ datos canónicos.

✓ agrupaciones "Datos personales".

✓ funciones duplicadas HU-006.

✓ funciones equivalentes HU-008.

✓ estadísticas HU-009.

✓ recomendaciones obsoletas.

✓ estructuras dict en recomendaciones.

✓ consolidación documental.

✓ promedio con métricas None.

✓ exclusión de HU-009 del promedio de Seguridad.

✓ conservación de recomendaciones de HU-010.

✓ redacción:

permitir que el paciente cancele...
8. Problema pendiente actual

Único problema conocido en este momento

La ejecución integral falla durante la generación del DOCX.

Excepción:

TypeError

unhashable type: 'dict'

Ubicación aproximada:

core/utils.py

_write_artifacts()

línea ~398

Campo afectado:

central.restricciones

La generación del DOCX asume:

restricciones = list[str]

pero al menos un elemento llega como:

dict

Por ello:

PDF no se genera.
DOCX falla.
JSON final no se persiste.
solo queda un CSV parcial.

Todo el pipeline previo funciona correctamente.

El problema es exclusivamente documental.

9. Archivos que no deben modificarse

No modificar sin justificación muy fuerte:

prompts/

quality_prompt.txt

security_prompt.txt

No modificar:

fórmulas MC-01

MC-02

MS-01

MS-02

Índice Calidad

Índice Seguridad

No modificar:

arquitectura LangGraph
topología de agentes
modelos
proveedores
sublotes
pacing
contratos JSON
validaciones semánticas ya aprobadas
lógica de Evaluador
10. Siguiente tarea exacta

Implementar únicamente la corrección documental.

Objetivos:

Normalizar

central.restricciones

para que siempre sea una representación documental uniforme antes de escribir artefactos.

Crear un modelo documental común para:

PDF
DOCX
CSV

Todos deben consumir exactamente la misma estructura normalizada.

Validar previamente la estructura documental.

Si hay error:

NO escribir ningún artefacto.

Persistir siempre:

summary.json

aunque falle PDF o DOCX.

Eliminar artefactos parciales.

Nunca debe quedar:

CSV sí

DOCX no

PDF no

Todos o ninguno.

Agregar pruebas unitarias y de integración para la generación documental.

No ejecutar llamadas reales hasta validar localmente.

11. Restricciones del desarrollo

Durante esta fase está prohibido:

commit
push
merge
rebase

No modificar:

prompts
agentes
métricas
modelos
proveedores
arquitectura
LangGraph
contratos JSON
lógica semántica
comportamiento validado de Calidad o Seguridad

No ejecutar Groq, Ollama o GitLab hasta que la corrección documental haya sido validada localmente mediante pruebas.

Estado actual del proyecto

La etapa "Recepción de Requerimientos" se encuentra aproximadamente al 99% de finalización.

Todo el procesamiento multiagente, las validaciones semánticas, las métricas, los veredictos y la consolidación funcionan correctamente. El único bloqueo restante para considerar cerrada la etapa es la capa de generación de artefactos (principalmente el DOCX) y la persistencia robusta del resumen final ante errores documentales. Una vez resuelto ese punto y validado con una nueva ejecución integral, la primera etapa podrá considerarse concluida y servirá como base para implementar las etapas de Diseño, Codificación y Pruebas.