# TraceDev — Análisis funcional completo del proceso de uso

**Herramienta:** TraceDev — Control y Trazabilidad del Desarrollo de Software (herramienta multiagente)
**Institución de referencia:** Escuela Militar de Ingeniería (EMI)
**Propósito de este documento:** describir, desde el punto de vista del usuario y sin entrar en detalles técnicos de programación, cómo se usa TraceDev de principio a fin. Está pensado como insumo para redactar posteriormente el Manual de Usuario.
**Fecha del análisis:** 03/10/2026
**Fuente del análisis:** revisión del código fuente de la rama `feature/correccion` (incluye cambios aún no confirmados en el repositorio), de las plantillas de Issues (`docs/plantilla_issue_*.md`) y de la configuración de ejemplo. No se pudo recorrer la aplicación en vivo porque el acceso exige una cuenta institucional de Microsoft 365; por eso, los textos de pantalla citados provienen del código y deben contrastarse con capturas reales al armar el manual (ver sección 23).

---

## Tabla de contenido

1. ¿Qué es TraceDev y para qué sirve?
2. Conceptos y vocabulario clave
3. Visión general del flujo de trabajo
4. Requisitos previos y preparación
5. Acceso a la herramienta (inicio y cierre de sesión)
6. Estructura general de la pantalla
7. Configuración del proyecto
8. Navegación por etapas y fases
9. Cómo preparar los Issues en GitLab (plantillas)
10. Etapa 1 — Requerimientos
11. Etapa 2 — Diseño
12. Etapa 3 — Codificación
13. Etapa 4 — Pruebas
14. Panel del proyecto
15. Matrices de trazabilidad (TRZ-001 a TRZ-004)
16. Estados, etiquetas y reglas de decisión
17. Métricas e índices por etapa
18. Documentos y archivos que genera la herramienta
19. Qué se escribe en GitLab automáticamente
20. Administración, persistencia y reinicio de datos
21. Condiciones que habilitan o bloquean cada acción
22. Mensajes frecuentes y qué hacer
23. Limitaciones y observaciones detectadas
24. Insumos para el Manual de Usuario
- Anexo A — Inventario de botones y controles
- Anexo B — Resumen de estados por etapa
- Anexo C — Ciclo de trabajo recomendado (paso a paso)

---

## 1. ¿Qué es TraceDev y para qué sirve?

TraceDev es una aplicación web (se abre en el navegador) que **apoya el control, el seguimiento y la trazabilidad del desarrollo de software** a lo largo de cuatro etapas: **Requerimientos, Diseño, Codificación y Pruebas**.

La herramienta trabaja **sobre GitLab**: lee los *Issues* (tareas) que el equipo de desarrollo registra en un proyecto de GitLab, los analiza con un conjunto de agentes de inteligencia artificial y herramientas de análisis automático, y devuelve:

- Una **evaluación orientativa** de cada Issue (índices de calidad y de seguridad, hallazgos, correcciones, precisiones y oportunidades de mejora).
- **Retroalimentación escrita directamente en GitLab** (un comentario y el cambio de etiqueta de revisión en cada Issue).
- Una **matriz de trazabilidad** que se va enriqueciendo etapa por etapa y que se publica también en GitLab.
- **Documentos descargables** (reporte ejecutivo en PDF, documento formal en Word y matrices en Excel/CSV).
- Un **Panel del proyecto** de solo lectura con el avance y los indicadores.

### 1.1 Idea central: la cadena de trazabilidad

```
Historia de Usuario (HU)  →  Requerimientos (RF/RNF)  →  Diseño (DIS / ED)  →  Codificación (COD)  →  Pruebas (PRU)
        └──────────────── cada etapa hereda la matriz de la anterior y le agrega su parte ────────────────┘
```

Cada etapa recibe como entrada la **matriz de trazabilidad** que dejó la etapa anterior, valida que los Issues de la etapa actual hagan referencia a elementos que **realmente existen** en esa matriz, y al terminar publica una matriz ampliada para la etapa siguiente.

### 1.2 Principio de uso: apoyo, no reemplazo de la decisión humana

Todos los resultados se presentan como **evaluación asistida**. La herramienta lo recuerda de forma explícita en pantalla, en los comentarios de GitLab y en los documentos: *«La decisión de aceptación corresponde al responsable del proyecto y requiere revisión humana.»*

### 1.3 Perfil de usuario previsto

En la cabecera de la aplicación aparece, junto al nombre de la persona con sesión iniciada, el rol fijo **«Encargado de DNTIC»**. Es un texto fijo de la interfaz (no depende de la cuenta). El usuario típico es la persona encargada de controlar el avance del proyecto de software.

---

## 2. Conceptos y vocabulario clave

| Término | Significado dentro de TraceDev |
|---|---|
| **Issue** | Tarea o ficha registrada en GitLab. Cada historia de usuario, diseño, codificación o prueba es un Issue. |
| **Milestone (hito)** | Agrupador de Issues en GitLab. TraceDev usa cuatro, con estos nombres exactos: **Recepción de Requerimientos**, **Diseño**, **Codificación** y **Pruebas**. |
| **Etiquetas de flujo** | Tres etiquetas de GitLab que indican el estado de revisión de un Issue: **Pendiente** (amarilla), **Revisada** (azul) y **Requiere modificación** (roja). |
| **HU-XXX** | Historia de Usuario (etapa Requerimientos). |
| **RF-XXX / RNF-XXX** | Requerimiento Funcional / No Funcional, generado a partir de las HU. |
| **DIS-XXX** | Issue de Diseño. Contiene varios **Elementos de Diseño**. |
| **ED-XX** | Elemento de Diseño (componente, servicio, interfaz, base de datos…). Es el vínculo entre Diseño, Codificación y Pruebas. |
| **COD-XXX** | Issue de Codificación (describe una implementación y los archivos donde vive). |
| **PRU-XXX** | Issue de Pruebas (documenta las pruebas ejecutadas sobre una o más codificaciones). |
| **TRZ-001 … TRZ-004** | Issues especiales donde TraceDev publica la **Matriz de Trazabilidad** de cada etapa (ver sección 15). |
| **Métrica (MC-/MS-)** | Medición calculada: **MC** = métricas de Calidad, **MS** = métricas de Seguridad (ver sección 17). |
| **Índice de Calidad / de Seguridad** | Promedio de las métricas de cada categoría, expresado en porcentaje. |
| **Umbral de aprobación** | 80 %. Un índice **debe ser mayor que 80 %** para considerarse satisfactorio (80 % exacto **no** aprueba). |
| **Estado orientativo** | Veredicto de TraceDev para un Issue (ej.: CONFORME, CORREGIR). Es una recomendación, no una decisión formal. |
| **LoT (nivel de aseguramiento)** | Nivel de aseguramiento de seguridad recomendado para una historia (LoT-2 o LoT-3). Es **informativo**: no es la confianza del modelo ni una certificación. |
| **Snapshot (copia congelada)** | Al iniciar un análisis, la herramienta congela la matriz de entrada para que todo el análisis use exactamente esa versión. |
| **Versión de matriz (vMAYOR.MENOR)** | Número de versión de cada matriz: MAYOR = etapa (1 Requerimientos, 2 Diseño, 3 Codificación, 4 Pruebas); MENOR sube cuando cambia el contenido real de la matriz. |
| **Versión de contexto (v1.N)** | Versión de la configuración del proyecto; sube cada vez que se cambia el nombre, la URL, el proyecto o el token. |

---

## 3. Visión general del flujo de trabajo

### 3.1 Recorrido completo (de punta a punta)

1. **Preparación (una sola vez):** disponer de un proyecto en GitLab, un token de acceso, credenciales de la herramienta y servicios de IA (sección 4).
2. **Iniciar sesión** con la cuenta institucional de Microsoft 365 (sección 5).
3. **Configurar el proyecto:** nombre, URL de GitLab, proyecto y token; probar la conexión (esto verifica/crea los 4 milestones) y guardar (sección 7).
4. **Etapa 1 — Requerimientos:** el equipo registra Historias de Usuario con la plantilla; TraceDev las lista, las analiza y produce requerimientos formalizados, evaluación, comentarios en GitLab y la matriz **TRZ-001**.
5. **Etapa 2 — Diseño:** el equipo registra Issues DIS que referencian RF/RNF; TraceDev muestra la matriz TRZ-001, pide confirmarla, evalúa cada diseño y publica **TRZ-002**.
6. **Etapa 3 — Codificación:** el equipo registra Issues COD que referencian ED y declaran archivos; TraceDev explora el repositorio, ejecuta herramientas de análisis de código sobre los archivos declarados, evalúa y publica **TRZ-003**.
7. **Etapa 4 — Pruebas:** el equipo registra Issues PRU que referencian COD; TraceDev evalúa la evidencia de pruebas y publica **TRZ-004**.
8. **Seguimiento:** en cualquier momento se consulta el **Panel del proyecto**.
9. **Retrabajo:** los Issues marcados *Requiere modificación* se corrigen en GitLab y se vuelven a analizar (sección 16.4 y Anexo C).

### 3.2 Las cuatro fases internas de cada etapa

En todas las etapas, el trabajo dentro de la pantalla se organiza en fases (se muestran como botones **Ver / Ocultar**):

| Etapa | Fases |
|---|---|
| Requerimientos, Diseño, Pruebas | **A. Revisión de entradas** → **B. Ejecución del análisis** → **C. Resultados y artefactos** |
| Codificación | **A. Entrada de codificación** → **B. Información técnica del repositorio** → **C. Ejecución del análisis** → **D. Resultados y artefactos** |

### 3.3 Dependencias entre etapas

| Para trabajar en… | Debe existir antes… |
|---|---|
| Requerimientos | Issues HU en el milestone *Recepción de Requerimientos* con la etiqueta **Pendiente** (o **Requiere modificación**). |
| Diseño | Haber ejecutado Requerimientos (TRZ-001 publicado). Si TRZ-001 no existe, la matriz de entrada queda vacía/inválida y no se puede analizar. |
| Codificación | Haber ejecutado Diseño (TRZ-002 publicado en GitLab). |
| Pruebas | Haber ejecutado Codificación (TRZ-003 publicado en GitLab). |

La navegación entre etapas es **libre** (se puede entrar a cualquiera en cualquier momento), pero cada una solo funciona cuando la matriz de la anterior está disponible.

---

## 4. Requisitos previos y preparación

> Esta sección es principalmente para la persona que instala o administra la herramienta; el manual de usuario final puede reducirla a «lo que debe estar listo antes de empezar».

### 4.1 En GitLab

| Elemento | Detalle |
|---|---|
| Proyecto GitLab | Con los Issues del equipo. Se identifica por su **ID numérico** o por su ruta `namespace/proyecto`. |
| Token de acceso | Token personal con permiso para **leer y escribir Issues, comentarios, etiquetas y milestones** y **leer el repositorio**. Se ingresa en la configuración. |
| Milestones | Los cuatro nombres exactos indicados en la sección 2. TraceDev **los crea automáticamente** si no existen al presionar «Probar conexión». |
| Etiquetas de flujo | **Pendiente**, **Revisada**, **Requiere modificación**. TraceDev las crea automáticamente la primera vez que actualiza un Issue; sin embargo, **para que un Issue sea listado por primera vez en Requerimientos, Diseño o Pruebas, debe tener ya la etiqueta «Pendiente»**, por lo que conviene crearla de antemano en el proyecto con ese nombre exacto (ver 23.2). |
| Plantillas de Issues | Cada tipo de Issue debe seguir su plantilla (sección 9). |
| Repositorio de código | Necesario solo para Codificación: los archivos que declare cada COD deben existir en la **rama predeterminada** del proyecto. |

### 4.2 Credenciales y servicios

| Elemento | Para qué se usa |
|---|---|
| **Cuenta institucional Microsoft 365** | Inicio de sesión. El acceso se restringe al directorio (tenant) de la organización. |
| **Archivo `.streamlit/secrets.toml`** | Datos del registro de la aplicación en Microsoft Entra ID (redirección, cliente, secreto, metadatos del tenant). |
| **Archivo `.env`** | URL/proyecto/token de GitLab por omisión, claves y modelos de los servicios de IA (por agente), y parámetros de lotes y tiempos de espera. |
| **Servicios de IA** | Los agentes usan modelos remotos (NVIDIA y Groq, asignados por agente en `.env`) y, opcionalmente, un modelo local (Ollama) como respaldo. Si se agota la cuota o el servicio falla, el análisis puede detenerse con un mensaje de error técnico. |

### 4.3 Herramientas de análisis de código (solo para Codificación)

| Herramienta | Qué evalúa | Aplica a |
|---|---|---|
| Radon | Complejidad ciclomática (MC-05) | Python |
| ESLint (complejidad) | Complejidad ciclomática (MC-05) | JavaScript / TypeScript |
| Semgrep | Vulnerabilidades críticas (MS-05) | Multilenguaje |
| pip-audit | Dependencias vulnerables (MS-06) | Python |
| npm audit | Dependencias vulnerables (MS-06) | Node.js |
| Gitleaks | Secretos expuestos (MS-07) | Todos los archivos de código |

Radon, Semgrep y pip-audit se instalan con las dependencias de Python; ESLint se instala con `npm install` (archivo `package.json`); **Gitleaks es un ejecutable externo** que debe estar disponible en el equipo (no figura en `requirements.txt`).

### 4.4 Cómo se inicia la aplicación

Se ejecuta con Streamlit desde la carpeta del proyecto:

```bash
streamlit run app.py
```

Se abre en el navegador (por omisión en `http://localhost:8501`). La dirección de retorno del inicio de sesión de Microsoft debe coincidir con la registrada en Microsoft Entra ID (`…/oauth2callback`).

---

## 5. Acceso a la herramienta (inicio y cierre de sesión)

### 5.1 Pantalla de inicio de sesión

Al abrir la aplicación sin sesión activa se muestra una pantalla completa con fondo institucional y una **tarjeta central** que contiene:

- Logo de la Escuela Militar de Ingeniería.
- Insignia/logo de **TraceDev**.
- Lema: **«Control y Trazabilidad del Desarrollo de Software»**.
- Título **«Bienvenido»** y el texto: *«Inicia sesión con tu cuenta institucional de Microsoft 365 para continuar.»*
- Botón azul **«Iniciar sesión con Microsoft 365»** (con ícono de ventanas).
- Nota al pie: *«Si tienes problemas para iniciar sesión, contacta con el área de Tecnologías de la Información de la EMI.»*

### 5.2 Pasos para ingresar

1. Abrir la dirección de TraceDev en el navegador.
2. Presionar **«Iniciar sesión con Microsoft 365»**.
3. En la ventana de Microsoft, ingresar con la cuenta institucional (solo cuentas del directorio de la organización; una cuenta personal o de otra organización no podrá ingresar).
4. Al volver, aparece la aplicación. Si no hay proyecto configurado, se mostrará la pantalla **Configuración del proyecto**; si ya existe, la pantalla **Evaluación por etapas**.

### 5.3 Cerrar sesión

En el menú lateral, al final, grupo **Sesión**, botón **«Cerrar sesión»**.

---

## 6. Estructura general de la pantalla

Después de iniciar sesión la pantalla tiene tres zonas.

### 6.1 Cabecera (parte superior)

- Logo de la EMI, separador y el logo de **TraceDev** con la leyenda «Herramienta multiagente».
- A la derecha, una **insignia de sesión** con la inicial, el **nombre** (o correo) de la cuenta y el rol «Encargado de DNTIC». En pantallas muy pequeñas la insignia se oculta.

### 6.2 Menú lateral (izquierda, fondo azul)

Se muestra en todas las pantallas posteriores al inicio de sesión.

| Grupo | Elemento | Función |
|---|---|---|
| **Proyecto activo** | Tarjeta informativa | Muestra el **nombre del proyecto**, el estado **GitLab: ● Conectado** (o «Pendiente» si aún no hay configuración) y el **Contexto vX.Y** (versión de la configuración). |
| **Gestión del proyecto** | **Panel del proyecto** | Abre el panel de seguimiento (solo lectura). Deshabilitado si no hay proyecto configurado. |
| | **Configuración del proyecto** | Abre el formulario de configuración. Siempre disponible. |
| | **Evaluación por etapas** | Abre la pantalla de etapas. Deshabilitado sin proyecto. |
| | Requerimientos · Diseño · Codificación · Pruebas | Acceso directo a cada etapa (sub-botones bajo «Evaluación por etapas»). La etapa actual aparece resaltada. Deshabilitados sin proyecto. |
| **Administración** | **Limpiar Base de Seguimiento (Caché e Historial)** | Borra los datos locales de seguimiento (ver sección 20). **No pide confirmación.** |
| **Sesión** | **Cerrar sesión** | Termina la sesión. |

El botón de la vista actual se muestra resaltado (color primario).

### 6.3 Área central

Cambia según la opción elegida: Configuración del proyecto, Panel del proyecto, o una etapa. Cuando se trabaja en una etapa, la parte superior muestra:

1. **Título «Evaluación por etapas»** con el selector de las 4 etapas (sección 8.1).
2. **Tarjeta «Etapa activa»** con el nombre de la etapa y el **milestone asociado** (ej.: *Etapa activa: Diseño — Milestone asociado: Diseño*).
3. **«Fases de la etapa»** con los botones de fase y los paneles de contenido (sección 8.2).

---

## 7. Configuración del proyecto

### 7.1 Cuándo aparece

- **Automáticamente** la primera vez (no existe configuración guardada). En ese caso, el resto de las opciones del menú está deshabilitado.
- **A demanda**, con el botón **«Configuración del proyecto»** del menú lateral, para revisar o modificar los datos.

Salir de la configuración sin guardar: usar cualquier otro botón del menú lateral (por ejemplo «Evaluación por etapas»). Esto **no** borra resultados.

### 7.2 El formulario

Título de pantalla: **«Configuración del proyecto»** — *«Identifica el proyecto y valida la conexión con GitLab para habilitar las etapas.»*

| Sección | Campo | Obligatorio | Detalle |
|---|---|---|---|
| Identificación | **Nombre del proyecto \*** | Sí | Texto libre. Ej.: *Sistema de Gestión de Citas Médicas*. Aparece en el menú, en los documentos y en los reportes. |
| Integración con GitLab | **URL del servidor GitLab \*** | Sí | Dirección del servidor GitLab. Se precarga desde `.env` si existe. |
| | **Proyecto GitLab \*** | Sí | **ID numérico** o ruta `namespace/proyecto`. |
| | **Token de acceso \*** | Sí | Se muestra enmascarado (tipo contraseña). |

Texto de ayuda en pantalla: *«Estos datos se utilizan para consultar los issues y verificar los milestones del flujo.»*

### 7.3 Botones

| Botón | Qué hace |
|---|---|
| **Probar conexión** | Valida URL, proyecto y token conectándose a GitLab y **verifica los 4 milestones**: reutiliza los existentes y **crea los faltantes**. Si todo va bien muestra: *«Conexión verificada con <nombre del proyecto en GitLab>. Milestones verificados sin duplicados.»* Si falla, muestra: *«No se pudo validar la conexión: <motivo>»*. Si faltan campos: *«Completa la URL, el proyecto y el token de GitLab.»* |
| **Guardar e iniciar proyecto** | Guarda la configuración y habilita el resto de la herramienta. |

### 7.4 Panel «Estado del proyecto»

Debajo del formulario, dos tarjetas: **GitLab** (*Conectado* / *Pendiente*) y **Milestones** (*Verificados* / *Pendientes*). Pasan a «Conectado/Verificados» solo después de una prueba de conexión exitosa **con los mismos datos que hay en el formulario** (si se cambia cualquier dato hay que volver a probar).

### 7.5 Reglas al guardar

- Se exige completar los cuatro campos: *«Completa todos los campos obligatorios.»*
- Se exige haber **probado la conexión con exactamente esos datos**: *«Primero debes probar correctamente esta conexión con GitLab.»*
- Al guardar con éxito:
  - La **versión de contexto** sube (v1.0 → v1.1 → …) **solo si cambió** alguno de los cuatro datos; si se guarda sin cambios, la versión se mantiene.
  - Se **reinician los resultados guardados localmente de las cuatro etapas** y las listas de Issues en memoria (no se borra nada en GitLab). Esto ocurre aunque solo se haya cambiado el nombre.
  - La aplicación se recarga y muestra la pantalla de etapas.

---

## 8. Navegación por etapas y fases

### 8.1 Selector de etapas («Evaluación por etapas»)

Título: **«Evaluación por etapas»** — *«Navega libremente entre las etapas del desarrollo de software, aquí o desde el menú lateral. La etapa actual se resalta en ambos lugares.»*

Subtítulo **«Seleccionar etapa»**: cuatro botones circulares en una línea, numerados y con ícono, con el nombre debajo:

| N.º | Ícono | Etapa |
|---|---|---|
| 1 | ☷ | Requerimientos |
| 2 | ◇ | Diseño |
| 3 | `</>` | Codificación |
| 4 | ✓ | Pruebas |

La etapa actual se destaca con un halo. Hacer clic en cualquiera cambia de etapa (equivale a los botones del menú lateral). La etapa por omisión al entrar es **Requerimientos**.

### 8.2 Barra «Fases de la etapa» (Paso a paso)

Debajo del título «Fases de la etapa» hay una fila de botones, uno por fase:

| Botón (cerrado) | Botón (abierto) | Fase |
|---|---|---|
| **Ver entradas** | **Ocultar entradas** | A. Revisión de entradas (en Codificación: «Entrada de codificación») |
| **Ver repositorio** *(solo Codificación)* | **Ocultar repositorio** | B. Información técnica del repositorio |
| **Ver análisis** | **Ocultar análisis** | Ejecución del análisis |
| **Ver resultados** | **Ocultar resultados** | Resultados y artefactos |

Comportamiento:

- Solo **una fase se ve a la vez**. Presionar el botón de la fase abierta la oculta; presionar otro botón abre esa fase.
- La fase abierta tiene el botón en color primario (azul lleno).
- Cada panel muestra un encabezado con una letra (A, B, C, D) y el título de la fase.
- Al final de las fases de entradas, repositorio y análisis aparece, abajo a la derecha, un botón discreto **«Siguiente fase →»** que cierra la fase actual y abre la siguiente.
- **Apertura inicial:** si todavía no hay resultados, se abre la fase de entradas; si ya hay resultados (de una sesión anterior o recién calculados), se abre la fase de **resultados**. Desde que la persona elige una fase manualmente, se respeta su elección.

### 8.3 Selector de resultados

En la fase de resultados, para ver el detalle de **un Issue a la vez** se usa una barra de botones (hasta 4 por fila), uno por Issue, con un círculo de color según su estado:

| Indicador | Estado |
|---|---|
| 🟢 | CONFORME |
| 🟡 | CONFORME CON MEJORAS |
| 🔴 | CORREGIR |
| ⚪ | Cualquier otro estado (REVISAR, APROBADO, ERROR, REVISIÓN HUMANA) |

El botón del Issue seleccionado se muestra resaltado. Si tras un nuevo análisis el Issue elegido ya no existe, vuelve al primero.

### 8.4 Pestañas de la fase de resultados

La fase de resultados (todas las etapas) tiene tres pestañas principales:

1. **Resumen general** — indicadores globales.
2. **Detalle por historia / diseño / codificación / prueba** — un Issue a la vez.
3. **Matriz y documentos** — matriz de trazabilidad y descargas.

Dentro del detalle de cada Issue hay cuatro sub-pestañas: **Resumen**, **Calidad**, **Seguridad** y **Formalización** (ver cada etapa).

---

## 9. Cómo preparar los Issues en GitLab (plantillas)

TraceDev **lee el texto de los Issues buscando títulos de sección exactos**. Por eso cada tipo de Issue tiene una plantilla oficial (carpeta `docs/`). Reglas comunes:

- La **primera línea** (sin `#`) es el **título del Issue** y **debe contener el código** (`HU-001`, `DIS-001`, `COD-001`, `PRU-001`). Sirve como identidad del Issue. Los ceros a la izquierda se normalizan (HU-1 → HU-001).
- **No cambiar los títulos de sección** (se buscan por su texto; en Diseño/Codificación/Pruebas el número delante del título es opcional).
- **Borrar los bloques de ayuda** (`> Guía:` y `> Ejemplo:`) antes de guardar: si se dejan, se mezclan con el contenido leído.
- En las **tablas** conservar el encabezado y la línea de guiones (`|---|`); se pueden agregar o quitar filas, **no columnas**.
- Valores no informativos (vacío, «N/A», «Ninguno», «No especificado», «Sin información», «Desconocido») se tratan como **ausentes**.
- El Issue debe estar **abierto** y asignado al **milestone** correspondiente.
- Para ser listado, el Issue debe tener la etiqueta **Pendiente** o **Requiere modificación** (con la excepción de Codificación, ver 12.2) y **no** estar **Revisada**.

### 9.1 Plantilla de Historia de Usuario (HU) — milestone «Recepción de Requerimientos»

| Sección (título exacto) | Contenido esperado | Observaciones |
|---|---|---|
| Título del Issue | `HU-XXX - Título breve` | Debe llevar el código HU. |
| `## Descripción` | Necesidad del usuario en 1–3 frases. | **Obligatoria**. |
| `## Como` | Rol o actor. | |
| `## Quiero` | Funcionalidad deseada. | |
| `## Para` | Objetivo o beneficio. | Basta con que exista **al menos uno** de Como/Quiero/Para para no ser bloqueada, pero conviene completar los tres. |
| `# Criterios de aceptación` | Viñetas verificables. | Si faltan: advertencia. |
| `# Prioridad` | Exactamente **Alta**, **Media** o **Baja**. | Si falta: advertencia. |
| `# Restricciones` | Viñetas de reglas obligatorias. | Si faltan: advertencia. |
| `# Seguridad` → `## ¿La historia maneja datos sensibles?` | Marcar **una sola** casilla `- [x] Sí` o `- [x] No`; si es Sí, listar debajo los tipos de datos (uno por línea). | |
| `## Autenticación` | Cómo se identifica el usuario. | |
| `## Autorización / Roles` | Roles autorizados. | |
| `## Auditoría` | Sí/No y qué se registra. | |
| `# Observaciones` | Notas, supuestos o pendientes. | Si faltan: advertencia. |

**Clasificación automática de la entrada:**

| Estado de entrada | Condición | Consecuencia |
|---|---|---|
| **Información insuficiente** | Falta el título, **o** la descripción, **o** no se identifica ninguno de actor/funcionalidad/objetivo. | La HU **no se envía al modelo**. TraceDev comenta en GitLab los campos faltantes y la etiqueta pasa a **Requiere modificación**. |
| **Entrada con advertencias** | Falta algún dato opcional (actor, funcionalidad u objetivo individual, criterios, prioridad, restricciones u observaciones). | Se analiza normalmente. |
| **Entrada válida** | Todo presente. | Se analiza normalmente. |

### 9.2 Plantilla de Diseño (DIS) — milestone «Diseño»

| Sección | Contenido |
|---|---|
| Título | `DIS-XXX - Título breve` |
| 1. Requerimientos relacionados | Lista de códigos **RF-XXX / RNF-XXX** que existan en la matriz TRZ-001. |
| 2. Descripción general del diseño | 1–2 párrafos (sin código). |
| 3. Elementos principales del diseño | Tabla: **ID (ED-01…) · Elemento · Tipo · Responsabilidad principal · Requerimientos relacionados**. Los **ED-XX** son el enlace hacia Codificación y Pruebas. |
| 4. Relaciones entre elementos | Tabla: **Origen · Destino · Relación o interacción · Descripción** (usa los IDs ED). |
| 5.1 Amenazas o situaciones de riesgo | Tabla: **Amenaza · Elemento afectado · ¿Tiene tratamiento? (Sí/No) · Tratamiento previsto**. |
| 5.2 Medidas de seguridad previstas | Tabla: **Aspecto · Medida · Elemento responsable**. |
| 6. Restricciones y decisiones | Dos listas: *Restricciones del diseño* y *Decisiones importantes de diseño*. |
| 7. Observaciones adicionales | Lista. |

Reglas funcionales: si un DIS cita un **RF/RNF que no existe** en la matriz vigente queda **bloqueado** (no se analiza). Las relaciones son opcionales: sin ellas, la métrica MC-04 queda *no evaluable*. La pantalla **solo bloquea por referencias inexistentes**; no verifica por adelantado si las demás secciones están completas (ver 23.4).

### 9.3 Plantilla de Codificación (COD) — milestone «Codificación»

| Sección | Contenido |
|---|---|
| Título | `COD-XXX - Nombre corto de la implementación` |
| 1. Descripción de la implementación | 1–3 párrafos, sin pegar código. **Obligatoria**. |
| 2. Elementos de Diseño implementados | Lista de **ED-XX** que deben existir en TRZ-002. **Obligatoria**. |
| 3. Ubicación de la implementación | Tabla **Archivo o módulo · Descripción**, con las rutas escritas entre comillas invertidas, por ejemplo `app/servicio.py`. Puede declararse una **carpeta** (se expande a todos sus archivos). **Obligatoria**. |
| 4. Decisiones de implementación | Lista. |
| 5. Consideraciones de seguridad implementadas | Lista. |
| 6. Dependencias relevantes utilizadas | Lista de nombres. |
| 7. Observaciones | Texto. |

Clasificación de entrada: **entrada_valida**, **informacion_insuficiente** (falta código, título, descripción, ED declarados o archivos declarados) o **referencias_invalidas** (algún ED no existe en TRZ-002).

### 9.4 Plantilla de Pruebas (PRU) — milestone «Pruebas»

| Sección | Contenido y formato obligatorio |
|---|---|
| Título | `PRU-XXX - Título breve` |
| 1. Implementación evaluada | Códigos **COD-XXX** existentes en TRZ-003 (uno por viñeta). |
| 2. Descripción general de las pruebas | 1–2 párrafos. **Obligatoria**. |
| 3. Pruebas funcionales realizadas | Tabla: **ID (CP-01…) · Funcionalidad evaluada · Prueba realizada · Resultado esperado · Resultado obtenido · Estado**. En **Estado** escribir exactamente **Aprobada** o **Fallida**. |
| 4. Fallos detectados y correcciones | Tabla: **ID (FAL-01…) · Fallo · Detectado en · ¿Fue corregido? · ¿Se verificó la corrección? · Resultado de la verificación**. Sí/No exactamente. |
| 5.1 Controles de seguridad verificados | Tabla: **ID (CS-01…) · Control · ¿Aplicable? · ¿Fue verificado? · Forma de verificación · Resultado**. |
| 5.2 Pruebas de seguridad realizadas | Tabla: **ID (PS-01…) · Prueba · Resultado esperado · Resultado obtenido · Estado (Aprobada/Fallida)**. |
| 6. Evidencias de las pruebas | Tabla: **ID (EV-01…) · Prueba o fallo relacionado · Tipo de evidencia · Descripción o ubicación**. |
| 7. Aspectos pendientes | Lista (o indicar que no hay). |
| 8. Observaciones adicionales | Lista. |

Clasificación de entrada: **VALIDO**, **INFORMACION_INSUFICIENTE** (falta código, título, descripción o COD relacionados), **REFERENCIA_INVALIDA** (algún COD no existe en TRZ-003) y **SIN_PRUEBAS** (no hay ninguna información evaluable: ni pruebas, ni controles, ni fallos). Un Estado distinto de «Aprobada»/«Fallida» se muestra como **«No reconocido»** y no cuenta en las métricas.

---

## 10. Etapa 1 — Requerimientos

**Milestone asociado:** Recepción de Requerimientos.
**Objetivo:** transformar las Historias de Usuario en requerimientos formalizados (RF/RNF), evaluarlos y generar la matriz de trazabilidad inicial **TRZ-001**.

### 10.1 Fase A — Revisión de entradas

Al entrar a la etapa, TraceDev consulta automáticamente GitLab y muestra:

- Botón **«Actualizar desde GitLab»** (vuelve a consultar los Issues del milestone).
- Una línea resumen con etiquetas: **«N issues encontrados»** y el conteo por estado de revisión (**Pendiente**, **Requiere modificación**).
- Una **fila por HU**: `#número` (IID de GitLab) · título · etiqueta de estado.
- Solo se listan los Issues **abiertos** con etiqueta **Pendiente** o **Requiere modificación** y que **no** tengan **Revisada**. Si no hay ninguno: *«No se encontraron issues abiertos en este milestone.»*
- Botón **«Siguiente fase →»**.

### 10.2 Fase B — Ejecución del análisis

1. Presionar **«Iniciar análisis»** (botón azul con ícono de reproducción). Está **deshabilitado si no hay Issues**.
2. La herramienta divide las HU en **lotes de hasta 5** y las procesa **en secuencia**. Se muestra:
   - Título **«Milestone Recepción de Requerimientos»** y *«N issues encontrados.»*
   - Panel **«Progreso del Análisis (Por Agente / Lote)»**: pasos «Cargando N Issues del Sprint ✔» y «Validando plantillas y filtrando Issues con Python ✔», y el avance **«Procesando lote X de Y (n historias)… (Central → Calidad → Seguridad → Evaluador → Formalización final)»**.
   - Línea por cada HU al terminarla: **«HU-xxx ✔ Procesamiento completo · Evaluación: <estado>»**, o una advertencia de *Información insuficiente* (con los campos faltantes), o un error.
   - Tres indicadores en vivo: **Lotes completados (X / Y)**, **Tiempo total** y **Tiempo promedio por historia**.
3. Cierre: **«¡Análisis completo! Todos los lotes procesados.» ✔** y *«¡Análisis del Sprint finalizado!»*; si hubo problemas: *«Análisis incompleto (lotes: …; historias: …).»* y *«El análisis del Sprint terminó con errores.»* Si un lote falla técnicamente, puede mostrarse la ruta de un «resumen parcial sanitizado».
4. **Duración:** cada análisis depende de los servicios de IA (hay pausas configuradas entre llamadas para respetar límites de uso); puede tomar **desde decenas de segundos hasta varios minutos por historia**. No cerrar ni recargar la página durante la ejecución.

**Qué hace TraceDev con cada HU (a nivel funcional):**

| Paso | Agente / proceso | Resultado |
|---|---|---|
| 1 | **Agente Central** | Formaliza la HU en requerimientos RF/RNF (código, nombre, descripción formal, tipo, prioridad, procedencia, pendientes de definición). |
| 2 | **Agente de Calidad** | Mide MC-01 (cobertura funcional) y MC-02 (adecuación funcional). |
| 3 | **Agente de Seguridad** | Mide MS-01 (cobertura de seguridad) y MS-02 (clasificación de datos) y asigna el LoT. |
| 4 | **Agente Evaluador** | Redacta correcciones, precisiones y oportunidades; propone el veredicto. |
| 5 | **Consolidación (cálculo determinista)** | Calcula los índices, fija el veredicto final con el umbral del 80 % (el modelo no puede cambiar los porcentajes), renumera los requerimientos y arma la matriz. |

**Acciones automáticas en GitLab al terminar cada HU:** publica un comentario con el resultado y actualiza la etiqueta (ver sección 19). Al terminar todo el análisis, **crea o actualiza el Issue TRZ-001** con la matriz.

### 10.3 Fase C — Resultados y artefactos

Mientras no haya resultados: *«Ejecuta el análisis para ver resultados.»*

#### Pestaña «Resumen general»

Subtítulo **«Resumen general de resultados»** y una franja de indicadores:

| Indicador | Significado |
|---|---|
| Historias procesadas | HU con resultado (identificadas por el sistema). |
| Requieren corrección | HU con veredicto CORREGIR. |
| Con error | HU con error o información insuficiente. |
| Calidad promedio | Promedio de los índices de calidad evaluables. |
| Seguridad promedio | Promedio de los índices de seguridad evaluables. |
| Requerimientos propuestos | Total de requerimientos generados. |

Línea de detalle: *Milestone · Calidad mínima · Seguridad mínima · Información insuficiente · Historias bajo meta*. («Historias bajo meta» cuenta las HU con calidad menor a 95 % o seguridad menor a 85 %: criterio heredado distinto del umbral de aprobación de 80 %; ver 23.7.)

#### Pestaña «Detalle por historia»

Barra de selección de HU (sección 8.3). Para la HU elegida se muestra:

- Título: `HU-xxx — Título · ESTADO`.
- Recuadro con **Actor** y **Objetivo**.
- Franja: **Calidad %**, **Seguridad %**, **LoT recomendado**, **N.º de requerimientos**.
- Recuadro **«¿Por qué este estado?»** con la explicación en lenguaje natural.
- Sub-pestañas:
  - **Resumen:** tres columnas con conteo y detalle de **Correcciones necesarias**, **Precisiones necesarias** y **Oportunidades de mejora**; y la sección **Retroalimentación** que indica si el comentario se publicó en GitLab (*«Retroalimentación publicada correctamente en GitLab.»* o *«La retroalimentación no fue publicada en GitLab.»*).
  - **Calidad:** despliegues **MC-01 — Cobertura Funcional · %** y **MC-02 — Adecuación Funcional · %** con fórmula, cálculo («x / y = %»), funciones documentadas, funciones necesarias no documentadas (con evidencia, motivo, consecuencia y confianza), funciones alineadas/no alineadas y la **cobertura potencial** si se formalizan las faltantes.
  - **Seguridad:** despliegues **MS-01 — Cobertura de Seguridad** y **MS-02 — Clasificación de Datos** con aspectos documentados/pendientes y datos identificados/pendientes de clasificación; y una nota sobre el **nivel de aseguramiento (LoT)**.
  - **Formalización:** lista de requerimientos formalizados (un despliegue por requerimiento: código — nombre) con descripción formal, **tipo**, **prioridad** (original o *«sugerida, pendiente de validación»*), **procedencia** y los **pendientes de definición** si existen.
- Las HU con *información insuficiente* o *error* **no aparecen en el selector**; se muestran como avisos (amarillo/rojo) con su motivo.

#### Pestaña «Matriz y documentos»

- Despliegue **«Matriz de trazabilidad»**: tabla (Código, Nombre, Tipo, Historia de origen, Estado de revisión) y botón **«Descargar matriz CSV»** (`matriz_trazabilidad.csv`, con las 7 columnas completas, separador `;`, compatible con Excel).
- Subtítulo **«Documentos consolidados»** con dos columnas:
  - **Reporte Ejecutivo:** botón **«Generar Reporte Ejecutivo»** y luego **«Descargar Reporte PDF»** (`Reporte_Ejecutivo_Lote.pdf`).
  - **Documento Formal:** botón **«Generar Documento Formal»** y luego **«Descargar Documento DOCX»** (`Requerimientos_Consolidados.docx`).
  - (En esta etapa, los documentos se **generan bajo demanda en dos pasos**: primero «Generar», luego «Descargar».)

### 10.4 Datos de cada requerimiento formalizado

| Campo | Descripción |
|---|---|
| Código | RF-001, RF-002… / RNF-001… (secuencial por ejecución). |
| Nombre y descripción formal | Redacción del requerimiento. |
| Tipo | Funcional / No funcional. |
| Prioridad | La original de la HU, o una **sugerida** (pendiente de validación). |
| Procedencia | Explícita (estaba en la HU), inferida o propuesta por el modelo para completar la cobertura. |
| Pendientes de definición | Aspectos que aún requieren decisión humana. |
| Estado de revisión (matriz) | «Pendiente de validación» o «Pendiente de definición y validación» (si hay pendientes). |

### 10.5 Qué conviene saber de esta etapa

- **Cada ejecución reemplaza TRZ-001** con los requerimientos de las historias procesadas **en esa ejecución** (el Issue se reescribe por completo; GitLab conserva el historial de edición). Como solo se procesan HU Pendientes o que Requieren modificación, ver 23.1 antes de reprocesar solo algunas historias.
- Una HU que quedó **Revisada** deja de aparecer en la lista; para volver a analizarla hay que **volver a marcarla como Pendiente** en GitLab.
- Los resultados se **guardan localmente**: al volver a abrir la herramienta se muestran los de la última ejecución.

---

## 11. Etapa 2 — Diseño

**Milestone asociado:** Diseño.
**Objetivo:** evaluar la calidad y seguridad de cada Issue DIS y relacionar los requerimientos con los Elementos de Diseño, produciendo **TRZ-002**.

### 11.1 Fase A — Revisión de entradas

La fase tiene dos pestañas: **«Matriz de trazabilidad»** y **«Issues de Diseño»**.

#### Pestaña «Matriz de trazabilidad»

1. **Tarjeta de estado «Matriz de trazabilidad · Requerimientos»** con tres etiquetas y una línea de contexto:
   - Estado: **ORIGINAL** (verde), **EDITADA** (ámbar) o **INVALIDA** (rojo).
   - Validación: **VÁLIDA** / **INVÁLIDA**.
   - Tamaño: **«N filas»**.
   - Línea: `Fuente — Versión vX.Y` (ej.: *GitLab — Issue TRZ-001 (#19) · Versión v1.0*; o *Archivo Excel — nombre.xlsx*).
2. **Avisos:**
   - Si la matriz fue editada: *«Cambios respecto a Requerimientos: +N agregados · ~N modificados · −N retirados»*.
   - Si es original: *«Estado: Original. No se detectaron modificaciones respecto a la matriz generada al finalizar Recepción de Requerimientos.»*
   - Si es inválida: *«Estado: INVÁLIDA. Se encontraron errores:»* y la lista de errores.
3. **Tabla** con 6 columnas: **Código, Tipo, Nombre, Descripción, Historia de origen, Estado de revisión**.
4. Si fue editada: despliegue **«Cambios detectados respecto a Requerimientos»** (tabla Código · Tipo de cambio [Agregado / Modificado / Retirado] · Detalle).
5. **Acciones sobre la matriz** (recomendación no bloqueante: *«revise la matriz antes de iniciar el análisis de Diseño; puede realizar ajustes desde GitLab o mediante Excel si los requerimientos han cambiado»*):

| Acción | Qué hace |
|---|---|
| **Actualizar desde GitLab** | Vuelve a leer TRZ-001 y recalcula el estado. Anula la confirmación previa. |
| **Editar en GitLab** | Abre el Issue TRZ-001 en una pestaña nueva de GitLab para editarlo allí. Si TRZ-001 aún no existe se muestra: *«TRZ-001 todavía no existe en GitLab (se publica al finalizar Requerimientos).»* |
| **Editar con Excel** | Descarga `matriz_entrada_diseno.xlsx` para modificarla fuera de la herramienta. |
| **Cargar matriz modificada** | Cuadro para subir un archivo **.xlsx** o **.csv** (CSV con `;` o `,`) con las mismas columnas. La herramienta lo valida y lo usa como matriz de entrada (fuente «EXCEL»); anula la confirmación previa. |
| **Actualizar matriz en GitLab** | Aparece **solo** cuando la matriz proviene de Excel **y** tiene diferencias con la de GitLab. Muestra antes: *«La matriz cargada contiene cambios respecto a la versión de GitLab.»* Al presionarlo actualiza TRZ-001 y confirma: *«TRZ-001 actualizado en GitLab con la matriz cargada.»* |

**Reglas de validación de la matriz de entrada** (si alguna falla, el estado es INVALIDA y no se puede analizar):

- La matriz no puede estar vacía.
- Cada fila debe tener **código** con formato `RF-###` o `RNF-###`, sin duplicados.
- Cada fila debe tener **nombre**, **descripción** e **historia de origen**.
- El **tipo** debe ser Funcional, No funcional, RF o RNF.

#### Pestaña «Issues de Diseño»

- Tarjeta **«Issues de Diseño»**: *N detectados · N válidos · N bloqueados* (los bloqueados en rojo).
- Franja: **Requisitos totales · Referencias válidas · Referencias inválidas**.
- Botón **«Actualizar issues»**.
- Una fila por DIS: **🟢/🔴 DIS-00X · «Entrada válida» o «Trazabilidad incompleta»** · etiqueta de estado de revisión. Si hay referencias inexistentes: *«Referencias inválidas: RF-009, RF-010»*.
- Si no hay Issues: *«No se encontraron Issues de Diseño en el milestone.»* (y no se puede continuar).
- Solo se listan los DIS con etiqueta **Pendiente** o **Requiere modificación**.

### 11.2 Fase B — Ejecución del análisis

1. Casilla de **confirmación obligatoria**: *«Confirmo que la matriz mostrada corresponde a los requerimientos vigentes que deben considerarse en la etapa de Diseño.»* Está **deshabilitada si la matriz es INVALIDA**.
2. Botón **«Iniciar análisis de Diseño»**: habilitado solo si **la matriz es válida, la casilla está marcada y existe al menos un DIS con entrada válida**.
3. Al ejecutar:
   - Se **congela una copia** de la matriz (snapshot) con su versión, fuente y estado.
   - Se procesa **un DIS a la vez** (*«Procesando DIS-001…»*) con la secuencia **Central → Calidad → Seguridad → Evaluador → Consolidación**.
   - Los DIS **bloqueados** (referencias inexistentes) **no se analizan**: se publica en GitLab un aviso (comentario + etiqueta *Requiere modificación*) y la pantalla informa: *«DIS-003: no analizado por referencias inexistentes (RF-009, RF-010). Aviso publicado en GitLab.»*
   - Cierre: *«Análisis completado para: DIS-001, DIS-002.»*
4. Se publica automáticamente **TRZ-002**, se actualiza la etiqueta de cada DIS y se comenta el resultado (sección 19).

**Qué hace cada agente en Diseño:**

| Agente | Función |
|---|---|
| Central de Diseño | Relaciona cada requisito con los Elementos de Diseño del DIS, indicando confianza y justificación; marca los requisitos «sin relación evidente». Descarta cualquier ED que el modelo invente. |
| Calidad de Diseño | Mide **MC-03** (completitud de la descripción) y **MC-04** (acoplamiento de componentes). |
| Seguridad de Diseño | Mide **MS-03** (cobertura de amenazas con tratamiento) y **MS-04** (cobertura de controles definidos). |
| Evaluador de Diseño | Redacta correcciones, precisiones y oportunidades (no puede cambiar los porcentajes). |
| Consolidación (Python) | Calcula índices y estado final. |

### 11.3 Fase C — Resultados y artefactos

- **Resumen general:** indicadores **Diseños evaluados · Requieren corrección · Con error · Calidad promedio · Seguridad promedio** y el aviso de decisión humana: *«Los resultados constituyen apoyo al control y seguimiento del diseño. La aceptación final requiere revisión humana.»*
- **Detalle por diseño** (selector por DIS):
  - Título, **estado** (insignia de color), **Índice de Calidad** e **Índice de Seguridad**, y el recuadro **«¿Por qué este estado?»**.
  - **Resumen:** correcciones / precisiones / oportunidades + estado de la retroalimentación en GitLab.
  - **Calidad:** **MC-03** (elementos evaluados y faltantes, resultado) y **MC-04** (relaciones documentadas, interpretación).
  - **Seguridad:** **MS-03** (amenazas con o sin tratamiento documentado, «x de y = %») y **MS-04** (controles definidos / no definidos, «x de y = %»).
  - **Formalización:** **Propuesta para alcanzar el máximo** y **Trazabilidad de este diseño** (*Cubiertos* y *Pendientes de relación*).
- **Matriz y documentos:**
  - Despliegue **«Matriz de Trazabilidad de la etapa»** (10 columnas) y botón **«Descargar matriz (Excel)»** (`matriz_diseno.xlsx`, con hoja «Resumen»).
  - **Reporte Ejecutivo** → **«Descargar Reporte Ejecutivo»** (`reporte_diseno.pdf`).
  - **Documento Formal** → **«Descargar Documento Formal»** (`documento_formal_diseno.docx`).
  - (Aquí los documentos **ya están listos**: un solo clic para descargar.)

### 11.4 Estado y trazabilidad por requisito (columna «Estado de trazabilidad» de TRZ-002)

| Estado | Cuándo ocurre |
|---|---|
| **Cubierto en Diseño** | Hay relación con un elemento de diseño con confianza **alta**. |
| **Requiere revisión** | Hay relación pero con confianza media o baja. |
| **Pendiente de relación** | No se encontró evidencia suficiente para asociarlo a un elemento. |
| **No evaluado** | Ningún DIS analizado contextualizó ese requisito. |

---

## 12. Etapa 3 — Codificación

**Milestone asociado:** Codificación.
**Objetivo:** comprobar que lo que cada COD declara (qué elementos de diseño implementa y en qué archivos) está **realmente respaldado por el código del repositorio**, y medir su calidad y seguridad con herramientas automáticas. Produce **TRZ-003**.

### 12.1 Fase A — Entrada de codificación

Pestañas **«Matriz de trazabilidad»** e **«Issues de Codificación»**.

#### Matriz

- Tarjeta **«Matriz de trazabilidad · Diseño»** con estado (ORIGINAL / EDITADA / INVALIDA), validación, N filas y `Fuente — Versión`.
- La matriz de entrada es **TRZ-002**, leída de GitLab. Si no existe: *«TRZ-002 no está disponible en GitLab. Ejecute primero la etapa de Diseño o cargue la matriz de trazabilidad exportada desde Diseño.»* y aparece un cuadro **«Cargar matriz de Diseño (Excel)»** (xlsx/csv). Mientras no se cargue una matriz, la fase no continúa (ver la limitación 23.3 sobre esta carga).
- El estado se calcula **comparando con la matriz cargada al inicio de la sesión** («Cambios respecto a la carga inicial: +/~/−»). Es INVALIDA si faltan columnas obligatorias (*Código requisito, Diseño, Elementos de Diseño, Estado de trazabilidad*) o está vacía.
- Tabla completa con las 10 columnas de TRZ-002.
- Acciones: **Actualizar desde GitLab**, **Editar en GitLab** (abre TRZ-002), **Editar con Excel** (descarga `matriz_entrada_codificacion.xlsx`) y **Cargar matriz de Diseño modificada** (xlsx/csv).

#### Issues de Codificación

- Tarjeta *N detectados · N válidos · N bloqueados*; franja **«Elementos de Diseño vigentes»**; botón **«Actualizar issues»**.
- Una fila por COD con su estado de entrada (**entrada_valida / informacion_insuficiente / referencias_invalidas**) y avisos: *«Campos faltantes: …»* y *«Elementos de Diseño inexistentes en la matriz heredada: ED-0X»*.
- Si no hay Issues: *«No se encontraron Issues de Codificación en el milestone.»*

### 12.2 Fase B — Información técnica del repositorio

Esta fase **es obligatoria antes de analizar** y no usa modelos de IA: solo explora el repositorio.

1. Botón **«Analizar repositorio»** (después de la primera vez se llama **«Actualizar repositorio»**). Mientras trabaja: *«Descubriendo estructura y tecnologías del repositorio…»*
2. Resultados:
   - Cuatro indicadores: **Rama analizada · Archivos detectados · Archivos de código · Directorios**. (Se analiza la **rama predeterminada** del proyecto de GitLab.)
   - Despliegues: **Lenguajes detectados** (porcentaje por lenguaje), **Ecosistemas y gestores de dependencias**, **Tecnologías y frameworks**, **Manifiestos y lockfiles**, **Archivos de configuración**, **Estructura del repositorio** (primeros 20 archivos).
   - **Análisis técnico planificado:**
     - Estado **BLOQUEADO** (rojo) si ningún COD tiene rutas y ED válidos: se listan los problemas por COD (rutas inexistentes en el repositorio o ED inexistentes).
     - Estado **CON ADVERTENCIAS** (amarillo) si algunos COD tienen problemas pero otros son válidos.
     - Tabla **Métrica · Tipo · Herramienta · Aplica a · Estado «🟡 PENDIENTE»** con las herramientas seleccionadas automáticamente (ver tabla 12.4).
     - Mensaje final: *«Descubrimiento completado. Las herramientas se ejecutarán en la siguiente fase cuando confirmes e inicies el análisis.»*
   - Si el descubrimiento falla: *«Error al descubrir el repositorio: …»*

> Nota: en Codificación el listado de COD incluye **todos los Issues abiertos del milestone**, tengan o no etiqueta de flujo (ver 23.2).

### 12.3 Fase C — Ejecución del análisis

1. Casilla de confirmación: *«Confirmo que la Matriz de Trazabilidad — Etapa Diseño mostrada corresponde a la versión vigente que debe considerarse en la etapa de Codificación.»* (deshabilitada si la matriz es INVALIDA).
2. Botón **«Iniciar análisis de Codificación»**, habilitado solo si se cumplen **todas** estas condiciones:
   - la matriz de entrada es **válida**;
   - la casilla está **marcada**;
   - existe **al menos un COD con entrada válida**;
   - el repositorio fue **analizado** en la fase B;
   - el estado del repositorio **no es BLOQUEADO**.
3. Al ejecutar, por **cada COD válido** (*«Localizando código y ejecutando herramientas para COD-001…»*):
   - Se congelan: la matriz, el perfil del repositorio, las herramientas seleccionadas y los Issues.
   - Se **descargan solo los archivos declarados** en el COD (y el manifiesto de dependencias de la raíz, si existe) a un espacio temporal que se borra al terminar.
   - Se ejecutan las herramientas de análisis seleccionadas.
   - Se invoca la secuencia de agentes: **Central → Calidad → Seguridad → Evaluador → Consolidación**.
4. Los COD con **ED inexistentes** no se analizan: se publica el aviso en GitLab (comentario + *Requiere modificación*). Los COD con información insuficiente quedan bloqueados en pantalla (sin aviso en GitLab; ver 23.5).
5. Cierre: *«Análisis completado para: COD-001, COD-002.»* Se publica **TRZ-003** y se retroalimenta cada COD.

### 12.4 Herramientas de análisis por métrica

| Métrica | Se elige según… | Herramienta |
|---|---|---|
| MC-05 Complejidad ciclomática | Lenguaje | Radon (Python) y/o ESLint (JavaScript/TypeScript). Si el repositorio es Java u otro, MC-05 puede quedar *no evaluable*. |
| MS-05 Vulnerabilidades críticas | Siempre | Semgrep |
| MS-06 Dependencias seguras | Ecosistema | pip-audit (Python) y/o npm audit (Node). Sin manifiesto reconocible puede quedar *no evaluable*. |
| MS-07 Código sin secretos expuestos | Siempre | Gitleaks |

Los manifiestos Python reconocidos en la raíz son: `requirements.txt`, `pyproject.toml`, `Pipfile`, `Pipfile.lock`, `poetry.lock`, `setup.py`. Los lenguajes reconocidos por extensión al declarar archivos son `.py`, `.js`, `.ts` y `.java`.

### 12.5 Fase D — Resultados y artefactos

- **Resumen general:** **Codificaciones evaluadas · Requieren corrección · Con error · Calidad promedio · Seguridad promedio**, con el aviso de decisión humana.
- **Detalle por codificación:**
  - Estado, índices y **«¿Por qué este estado?»**.
  - Despliegue **«Evidencia técnica utilizada»**: tabla con las herramientas ejecutadas (**OK / NO_APLICA / ERROR**) y su detalle (funciones analizadas, hallazgos y críticos, dependencias analizadas y vulnerables, archivos con secretos).
  - **Resumen:** correcciones, precisiones, oportunidades y estado de retroalimentación.
  - **Calidad:** **MC-05** (resultado, herramienta, funciones con complejidad no aceptable con archivo, nombre, CC, problema y recomendación).
  - **Seguridad:** **MS-05** (número de críticas y detalle), **MS-06** (dependencias inseguras) y **MS-07** (archivos con secretos).
  - **Formalización:** **Propuesta para alcanzar el máximo** y **Trazabilidad de esta Codificación** (*Implementados* / *Declarados sin confirmar*).
- **Matriz y documentos:** matriz de 15 columnas, **«Descargar matriz (Excel)»** (`matriz_codificacion.xlsx`), **Reporte Ejecutivo** (`reporte_codificacion.pdf`) y **Documento Formal** (`documento_formal_codificacion.docx`).

### 12.6 Estado de implementación por elemento (columna de TRZ-003)

| Estado | Significado |
|---|---|
| **Implementado en Codificación** | El análisis confirmó evidencia real de implementación en el código. |
| **Declarado sin confirmar en el código** | El COD declara el elemento, pero el código disponible no lo sustenta. |
| **No evaluado** | Ningún COD analizado hace referencia a ese elemento de diseño. |

---

## 13. Etapa 4 — Pruebas

**Milestone asociado:** Pruebas.
**Objetivo:** evaluar la evidencia de pruebas documentada en cada Issue PRU y verificar qué codificaciones quedaron probadas. Produce **TRZ-004**.

### 13.1 Fase A — Revisión de entradas

- **Matriz** (pestaña «Matriz de trazabilidad»): tarjeta **«Matriz de trazabilidad · Codificación»** con estado fijo **ORIGINAL · VÁLIDA**, N filas y *Fuente (GitLab — TRZ-003) · Versión*. La matriz se usa **tal como la dejó Codificación (solo lectura)**; no hay edición por Excel. Para modificarla, editar TRZ-003 en GitLab y presionar **«Actualizar desde GitLab»**. Botón **«Ver TRZ-003 en GitLab»**.
- Si TRZ-003 no existe: *«TRZ-003 no está disponible en GitLab todavía. Ejecute primero la etapa de Codificación para generarla.»*
- **Issues de Pruebas:** tarjeta *N detectados · N válidos · N bloqueados*, botón **«Actualizar issues»**, y una fila por PRU con su estado de entrada (**VALIDO, INFORMACION_INSUFICIENTE, REFERENCIA_INVALIDA, SIN_PRUEBAS**), etiqueta de revisión y avisos (*«Campos faltantes: …»*, *«Codificaciones inexistentes en TRZ-003: COD-00X»*). Solo se listan los PRU **Pendiente / Requiere modificación**.

### 13.2 Fase B — Ejecución del análisis

1. Casilla: *«Confirmo que la Matriz de Trazabilidad — Etapa Codificación mostrada corresponde a la versión vigente que debe considerarse en la etapa de Pruebas.»*
2. Botón **«Iniciar análisis de Pruebas»**: habilitado si la casilla está marcada y hay al menos un PRU en estado **VALIDO**.
3. Por cada PRU válido: *«Ejecutando el análisis multiagente para PRU-001…»*. Los PRU con **COD inexistentes** reciben el aviso en GitLab (comentario + *Requiere modificación*); los de información insuficiente o sin pruebas **no se analizan** y no reciben aviso.
4. Cierre: *«Análisis completado para: PRU-001…»*. Se publica **TRZ-004** y se retroalimenta cada PRU.

### 13.3 Fase C — Resultados y artefactos

- **Resumen general:** **Pruebas evaluadas · Requieren corrección · Con error · Calidad promedio · Seguridad promedio**. (Aquí la calidad promedio resume MC-07 y MC-08; la seguridad, MS-08 y MS-09.)
- **Detalle por prueba:** estado, índices, **«¿Por qué este estado?»** y sub-pestañas:
  - **Resumen:** correcciones, precisiones, oportunidades, retroalimentación.
  - **Calidad:** **MC-07 Corrección Funcional** (funcionalidades con brecha) y **MC-08 Corrección de Fallos** (fallos detectados/corregidos/verificados y fallos pendientes).
  - **Seguridad:** **MS-08 Cobertura de Verificación de Controles** (controles no verificados) y **MS-09 Pruebas de Seguridad Satisfactorias** (pruebas fallidas).
  - **Formalización:** **Recomendación de revisión** y **Trazabilidad heredada de esta Prueba** (por cada COD: elementos de diseño, requisitos e historias).
- **Matriz y documentos:** matriz de 18 columnas (**«Descargar matriz (Excel)»** → `matriz_pruebas.xlsx`), **Reporte Ejecutivo** (`reporte_pruebas.pdf`) y **Documento Formal** (`documento_formal_pruebas.docx`).

### 13.4 Estado de pruebas por codificación (columna «Estado de Pruebas» de TRZ-004)

| Estado | Equivale a |
|---|---|
| **Verificado** | PRU con estado APROBADO |
| **Fallo pendiente** | PRU con estado CORREGIR |
| **Pendiente de revisión** | PRU con estado REVISAR |
| **Error técnico** | PRU con estado ERROR |
| — | Ningún PRU evaluado hace referencia a esa codificación |

Si una misma codificación aparece con varios resultados, **prevalece el más desfavorable** (Fallo pendiente › Pendiente de revisión › Error técnico › Verificado) al resumir.

---

## 14. Panel del proyecto

**Cómo se abre:** menú lateral → **Panel del proyecto**. Es una vista **de solo lectura**: no modifica Issues, no publica comentarios y no ejecuta análisis. Título: **«Panel del proyecto»** — *«<Proyecto> · Vista de solo lectura: agrega información del proyecto desde la base de seguimiento local y GitLab. No modifica Issues ni ejecuta análisis.»* Al estar en el panel no se muestra el selector de etapas; se vuelve con **«Evaluación por etapas»**.

Botón superior: **«Actualizar datos de GitLab»** (recarga avance y trazabilidad).

| Sección | Contenido | Fuente |
|---|---|---|
| **Salud del proyecto** | Cuatro tarjetas: **Versión de contexto**, **Análisis registrados**, **Calidad promedio**, **Seguridad promedio**; y una línea con **tiempo promedio por análisis** y **último análisis registrado**. | Base local (historial). |
| **Avance por etapa** | Por cada etapa: tarjeta **«Revisadas n/total»** con porcentaje y el detalle *Requiere modificación · Pendiente · Sin estado*; más un **gráfico de barras apiladas** por etapa y estado. Si GitLab falla en una etapa se muestra «No disponible» con el motivo, sin afectar a las demás. | GitLab (Issues abiertos de cada milestone, excluyendo los TRZ). |
| **Tendencia de calidad y seguridad** | Gráfico de líneas con los índices de cada análisis registrado (valores 0 a 1; los no evaluables se omiten). Si no hay datos: *«Aún no hay análisis registrados en el historial. Ejecuta al menos un análisis de Requerimientos.»* | Base local. |
| **Trazabilidad por matriz** | Tres tarjetas: **Diseño (TRZ-002)** — requisitos con diseño; **Codificación (TRZ-003)** — elementos de diseño implementados; **Pruebas (TRZ-004)** — codificaciones verificadas. Formato «cubiertos / total (porcentaje)» más detalle de pendientes/no confirmados/no evaluados. «No disponible» si la matriz no existe. | GitLab. |
| **Versiones de las matrices** | Tabla: **Matriz** (TRZ-001 … TRZ-004) · **Versión** (vX.Y) · **Última modificación**. | Base local. |

**Estados de revisión del avance (cómo se clasifica cada Issue):**

| Estado | Condición (etiquetas del Issue) |
|---|---|
| Revisada | Tiene **Revisada** (o las antiguas «Analizada/Analizado»). |
| Requiere modificación | Tiene **Requiere modificación**. |
| Pendiente | Tiene **Pendiente**. |
| Sin estado | Ninguna de las anteriores. |

> El **historial** (análisis registrados, calidad/seguridad promedio, tendencia) se alimenta **únicamente de los análisis de Requerimientos** (ver 23.6).

---

## 15. Matrices de trazabilidad (TRZ-001 a TRZ-004)

### 15.1 Qué son y dónde viven

Cada matriz se guarda como **un Issue de GitLab** con tabla en Markdown. Se crean automáticamente la primera vez y se **actualizan** (se reescribe la descripción) en cada publicación. Se localizan por su título:

| Matriz | Título del Issue | Publicada por | Columnas |
|---|---|---|---|
| **TRZ-001** | TRZ-001 - Matriz de Trazabilidad | Etapa Requerimientos | 7 |
| **TRZ-002** | TRZ-002 - Matriz de Trazabilidad - Etapa Diseño | Etapa Diseño | 10 |
| **TRZ-003** | TRZ-003 - Matriz de Trazabilidad - Etapa Codificación | Etapa Codificación | 15 |
| **TRZ-004** | TRZ-004 - Matriz de Trazabilidad - Etapa Pruebas | Etapa Pruebas | 18 |

Estos Issues se crean **sin milestone ni etiquetas**, por lo que no se confunden con los Issues de trabajo.

### 15.2 Columnas de cada matriz

| Matriz | Columnas |
|---|---|
| TRZ-001 | Código · Nombre · Descripción · Tipo · Historia de origen · Fecha de generación · Estado de revisión |
| TRZ-002 (añade a una vista por requisito) | HU origen · Código requisito · Tipo · Nombre del requisito · Descripción · **Diseño** · **Elementos de Diseño** · **Estado de trazabilidad** · **Estado de Diseño** · **Observación** |
| TRZ-003 (TRZ-002 + 5) | … + **Codificación** · **Estado de implementación** · **Ubicación de implementación** · **Estado de Codificación** · **Observación de Codificación** |
| TRZ-004 (TRZ-003 + 3) | … + **Pruebas** · **Estado de Pruebas** · **Observación de Pruebas** |

Una fila por cada combinación requisito–diseño (TRZ-002), requisito–elemento (TRZ-003) y requisito–elemento–prueba (TRZ-004), de modo que un requisito con varios diseños, elementos o pruebas aparece en varias filas.

### 15.3 Versionado

- Formato **vMAYOR.MENOR**: MAYOR = 1 (Requerimientos), 2 (Diseño), 3 (Codificación), 4 (Pruebas).
- MENOR parte en 0 y **sube solo si el contenido cambió** respecto a la última publicación (las fechas no cuentan). Si se republica la misma matriz, la versión no cambia.
- La versión se muestra en la tarjeta de estado de cada etapa, en el Panel del proyecto y en el «Control del documento» de los documentos generados.
- «Limpiar Base de Seguimiento» reinicia el registro de versiones.

### 15.4 Edición de matrices

| Etapa | Editar en GitLab | Editar con Excel / cargar archivo | Sincronizar a GitLab |
|---|---|---|---|
| Diseño (entrada = TRZ-001) | Sí | Sí | Sí (botón «Actualizar matriz en GitLab») |
| Codificación (entrada = TRZ-002) | Sí | Disponible, pero con limitación (ver 23.3) | No |
| Pruebas (entrada = TRZ-003) | Solo lectura en la herramienta (editar en GitLab y actualizar) | No | No |

---

## 16. Estados, etiquetas y reglas de decisión

### 16.1 Regla del umbral

**Aprobado = índice > 80 %. Corregir = índice ≤ 80 %.** La comparación se hace con el porcentaje redondeado a 2 decimales, el mismo que ve el usuario (un valor mostrado como «80,0 %» **no** aprueba). Los porcentajes los calcula el sistema con fórmulas fijas; **los agentes de IA no pueden alterarlos**. Una métrica **no evaluable** no se convierte en 0 %.

### 16.2 Estados orientativos por etapa

| Etapa | Estados posibles | Regla |
|---|---|---|
| **Requerimientos** | CONFORME · CONFORME CON MEJORAS · CORREGIR · REVISIÓN HUMANA | Se parte del veredicto: **APROBADO** si los índices de calidad y de seguridad superan el 80 %; **CORREGIR** si alguno es ≤ 80 %; **REVISIÓN REQUERIDA** (se muestra como *REVISIÓN HUMANA*) si hay información insuficiente o una métrica esencial no es evaluable. Un APROBADO con oportunidades de mejora se muestra como *CONFORME CON MEJORAS*; sin mejoras, *CONFORME*. |
| **Diseño** | CONFORME · CONFORME CON MEJORAS · CORREGIR · ERROR | **CORREGIR** si algún índice evaluable es ≤ 80 % o ningún índice es evaluable. Si todos superan 80 %: *CONFORME*, o *CONFORME CON MEJORAS* si el Evaluador dejó hallazgos. |
| **Codificación** | CONFORME · CONFORME CON MEJORAS · CORREGIR · ERROR | Misma regla que Diseño. |
| **Pruebas** | APROBADO · REVISAR · CORREGIR · ERROR | **CORREGIR** si alguna métrica evaluada es ≤ 80 %; **REVISAR** si alguna métrica es *no evaluable* (evidencia insuficiente; «No aplica» no cuenta como brecha); **APROBADO** si todas las evaluables superan 80 %. |

Cualquier etapa puede mostrar **ERROR** cuando hay un fallo técnico (en ese caso no se publica comentario ni cambia la etiqueta). En la práctica, un fallo técnico durante la ejecución suele manifestarse como un **mensaje de error** en pantalla (ver sección 22).

### 16.3 Cómo se traduce el estado a etiquetas de GitLab

| Resultado del análisis | Etiqueta resultante en el Issue |
|---|---|
| Requerimientos: APROBADO (CONFORME / CONFORME CON MEJORAS) | **Revisada** |
| Requerimientos: CORREGIR, REVISIÓN REQUERIDA, información insuficiente | **Requiere modificación** |
| Diseño / Codificación: CONFORME, CONFORME CON MEJORAS | **Revisada** |
| Diseño / Codificación: CORREGIR | **Requiere modificación** |
| Pruebas: APROBADO | **Revisada** |
| Pruebas: CORREGIR, REVISAR | **Requiere modificación** |
| Cualquier etapa: ERROR | Sin cambio |
| Issue bloqueado por referencias inexistentes | **Requiere modificación** (más comentario de aviso) |

Al actualizar, TraceDev **quita** las etiquetas de flujo anteriores (Pendiente, Revisada, Requiere modificación, y las antiguas «En revisión», «Analizado/a», «Error de análisis») y **conserva las demás etiquetas** del Issue.

### 16.4 Ciclo de vida de un Issue

```
 [Pendiente] ──análisis──▶ [Revisada]               (cumple: sale de la lista de pendientes)
      ▲        └─────────▶ [Requiere modificación]  (no cumple)
      │                              │
      │      el equipo corrige el Issue en GitLab
      └──────────────────────────────┘
        (puede dejarse en «Requiere modificación», que sigue siendo elegible,
         o volver a marcarse «Pendiente» como indican los comentarios)
```

- Los Issues en **Pendiente** o **Requiere modificación** son elegibles para análisis.
- Un Issue **Revisada** deja de aparecer; para reanalizarlo hay que ponerlo de nuevo en **Pendiente**.

---

## 17. Métricas e índices por etapa

### 17.1 Requerimientos

| Código | Métrica | Fórmula | Qué significa |
|---|---|---|---|
| **MC-01** | Cobertura Funcional | Funciones necesarias **documentadas** ÷ Total de funciones necesarias identificadas | ¿La HU documenta las funciones que realmente necesita? Muestra además las funciones faltantes con su justificación y confianza. |
| **MC-02** | Adecuación Funcional | Funciones **alineadas** con el objetivo ÷ Funciones documentadas evaluables | ¿Lo documentado sirve al objetivo declarado? |
| **MS-01** | Cobertura de Seguridad | Aspectos de seguridad documentados ÷ Aspectos aplicables | ¿Se documentaron los aspectos de seguridad que aplican (autenticación, autorización, auditoría, etc.)? |
| **MS-02** | Clasificación de Datos | Datos clasificados explícitamente ÷ Datos sensibles identificados | ¿Los datos sensibles tienen clasificación? **No aplica** si la HU no maneja datos sensibles. |
| — | **Índice de Calidad** | Promedio de MC-01 y MC-02 | |
| — | **Índice de Seguridad** | Promedio de MS-01 y MS-02 (si una *no aplica*, se usa la otra) | |
| — | **LoT** | LoT-2 por defecto; LoT-3 solo ante evidencia explícita de alto impacto/criticidad | Dato informativo; no entra en el veredicto. |

### 17.2 Diseño

| Código | Métrica | Fórmula |
|---|---|---|
| **MC-03** | Completitud de la Descripción | Elementos documentados ÷ (documentados + faltantes de confianza **alta**) |
| **MC-04** | Acoplamiento de Componentes | Componentes con acoplamiento **aceptable** ÷ componentes **evaluables**. Sin relaciones documentadas queda *no evaluable*. |
| **MS-03** | Cobertura de Amenazas con Tratamiento | Amenazas con tratamiento ÷ (amenazas identificadas + faltantes de confianza alta) |
| **MS-04** | Cobertura de Controles de Seguridad Definidos | Controles definidos ÷ controles aplicables de confianza alta |
| — | **Índice de Calidad de Diseño** | Promedio de MC-03 y MC-04 (evaluables) |
| — | **Índice de Seguridad de Diseño** | Promedio de MS-03 y MS-04 (evaluables) |

### 17.3 Codificación

| Código | Métrica | Fórmula |
|---|---|---|
| **MC-05** | Adecuación de la Complejidad Ciclomática | Funciones con complejidad aceptable ÷ funciones analizadas |
| **MS-05** | Vulnerabilidades Críticas Detectadas | Conteo de hallazgos críticos (resultado deseado: **0**). Para el índice se normaliza: 100 % si no hay críticas, 0 % si hay al menos una. |
| **MS-06** | Cobertura de Dependencias Seguras | Dependencias seguras ÷ dependencias analizadas |
| **MS-07** | Cobertura de Código sin Secretos Expuestos | Archivos de código sin secretos ÷ archivos de código analizados |
| — | **Índice de Calidad del Código** | = MC-05 (MC-06 está fuera del alcance actual) |
| — | **Índice de Seguridad del Código** | Promedio de MS-05 (normalizado), MS-06 y MS-07 evaluables |

### 17.4 Pruebas

| Código | Métrica | Fórmula |
|---|---|---|
| **MC-07** | Corrección Funcional | Funcionalidades cuyas pruebas están **todas Aprobadas** ÷ funcionalidades evaluables (se agrupa por «Funcionalidad evaluada») |
| **MC-08** | Corrección de Fallos | Fallos corregidos **y verificados** ÷ fallos detectados. Sin fallos: **No aplica** (no cuenta 100 %). |
| **MS-08** | Cobertura de Verificación de Controles | Controles verificados ÷ controles **aplicables** (los marcados «No aplicable» quedan fuera) |
| **MS-09** | Pruebas de Seguridad Satisfactorias | Pruebas de seguridad Aprobadas ÷ pruebas ejecutadas con estado reconocido. Sin pruebas: *No aplica* (si tampoco hay controles aplicables) o *No evaluable* (si había controles aplicables). |

Estados de cálculo de una métrica: **Evaluado / Calculada**, **No aplica** (legítimo, no penaliza) y **No evaluable** (evidencia insuficiente: en Pruebas produce REVISAR).

---

## 18. Documentos y archivos que genera la herramienta

### 18.1 Documentos por etapa

| Etapa | Reporte Ejecutivo (PDF) | Documento Formal (Word) | Matriz |
|---|---|---|---|
| Requerimientos | `Reporte_Ejecutivo_Lote.pdf` (generar → descargar) | `Requerimientos_Consolidados.docx` (generar → descargar) | `matriz_trazabilidad.csv` |
| Diseño | `reporte_diseno.pdf` | `documento_formal_diseno.docx` | `matriz_diseno.xlsx` (+ `matriz_entrada_diseno.xlsx` en entradas) |
| Codificación | `reporte_codificacion.pdf` | `documento_formal_codificacion.docx` | `matriz_codificacion.xlsx` (+ `matriz_entrada_codificacion.xlsx`) |
| Pruebas | `reporte_pruebas.pdf` | `documento_formal_pruebas.docx` | `matriz_pruebas.xlsx` |

Además, la herramienta guarda una copia de las matrices en la carpeta `output/xlsx/` del equipo donde corre, con la fecha en el nombre (ej.: `matriz_diseno_20261003.xlsx`).

### 18.2 Contenido del Reporte Ejecutivo (PDF)

- Título, proyecto, milestone y fecha; **resumen global**.
- Para cada Issue: estado orientativo, índices, y el **detalle de cada métrica** (fórmula, cálculo, elementos considerados) separado en **Calidad** y **Seguridad**.
- **Correcciones necesarias, precisiones y oportunidades de mejora**; propuesta para alcanzar el máximo; trazabilidad del Issue.
- En Diseño/Codificación/Pruebas: apartado **«Matriz de entrada»** (versión, fuente y estado de la matriz heredada).

### 18.3 Contenido del Documento Formal (Word)

| Etapa | Secciones |
|---|---|
| Requerimientos | Información general · 1. Introducción · 2. Alcance · 3. Actores · 4. Objetivos · 5. Requerimientos formalizados por HU (funcionales, no funcionales, propuestos para completar cobertura, restricciones) · 6. Matriz de trazabilidad · 7. Control de revisión |
| Diseño | 1. Introducción · 2. Alcance · por cada DIS: 3. Elementos · 4. Relaciones · 5. Restricciones · 6. Decisiones · 7. Seguridad (7.1 medidas, 7.2 amenazas y tratamientos, 7.3 aspectos pendientes) · 8. Matriz de trazabilidad · 9. Control del documento |
| Codificación | 1. Introducción · 2. Alcance · por cada COD: 3. Implementaciones · 4. Elementos de diseño implementados · 5. Archivos y módulos · 6. Estructura técnica · 7. Dependencias · 8. Seguridad (8.1 vulnerabilidades críticas, 8.2 secretos) · 9. Aspectos pendientes · 10. Matriz evolucionada · 11. Control del documento |
| Pruebas | 1. Información general · 2. Implementaciones evaluadas · por cada PRU: 3. Resumen · 4. Pruebas funcionales · 5. Fallos y correcciones · 6. Verificación de seguridad · 7. Evidencias · 8. Hallazgos · 9. Aspectos pendientes · 10. Recomendaciones · 11. Observaciones · 12. Trazabilidad final · 13. Control del documento |

Principio de redacción: los aspectos sin evidencia se marcan como **pendientes de revisión**; nunca se afirma que algo está documentado si no lo está. Los documentos incluyen siempre el aviso de decisión humana.

---

## 19. Qué se escribe en GitLab automáticamente

Al terminar un análisis, **sin que el usuario pulse nada más**, TraceDev modifica GitLab así:

| Acción | Dónde | Cuándo |
|---|---|---|
| **Comentario de retroalimentación** | En cada Issue analizado | Siempre que no haya ERROR. |
| **Cambio de etiqueta de flujo** | En cada Issue analizado | Según la tabla 16.3. |
| **Comentario de aviso por referencias inexistentes** + etiqueta *Requiere modificación* | En cada Issue bloqueado (Diseño, Codificación, Pruebas) | Al iniciar el análisis de la etapa (una vez por Issue y sesión). |
| **Comentario de información insuficiente** + etiqueta *Requiere modificación* | En cada HU incompleta | Solo en Requerimientos. |
| **Creación/actualización de TRZ-00x** | Issue de la matriz de la etapa | Al terminar el análisis, **si no hubo errores globales**. |
| **Creación de milestones** | Proyecto | Al «Probar conexión». |
| **Creación de etiquetas de flujo** | Proyecto | La primera vez que se actualiza un Issue. |
| **Actualización de TRZ-001 desde Excel** | Issue TRZ-001 | Solo al presionar «Actualizar matriz en GitLab» (Diseño). |

### 19.1 Formato del comentario (Diseño / Codificación / Pruebas)

```
Resultado del análisis de <Etapa> — <ID>

Estado orientativo: <estado>
Índice de Calidad ...: xx %
Índice de Seguridad ...: xx %

Correcciones necesarias:
- ...        (o «- Ninguna.»)

Precisiones:
- ...

Oportunidades de mejora:
- ...

Próxima acción:
<Actualizar el Issue ... y volver a marcarlo como Pendiente. | El Issue queda marcado como Revisado y puede continuar con la siguiente etapa.>

Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.
```

El comentario de **Requerimientos** es más detallado: *Resultado del análisis multiagente*, estado orientativo, **MC-01/MC-02**, índice de seguridad, gap funcional identificado (con «Por qué afecta MC-01» y «Sugerencia para alcanzar el 100 %»), precisiones recomendadas, oportunidades adicionales y **Próxima acción**.

El comentario de **aviso por referencias inexistentes** comienza con *«Revisar — Trazabilidad incompleta (<ID>)»*, lista las referencias inexistentes y pide corregirlas (o actualizar la matriz) y volver a ejecutar.

El comentario de **información insuficiente** (Requerimientos) dice que la historia no se envió al modelo, lista los campos faltantes e indica que quedará como *Requiere modificación* hasta corregirla y volver a marcarla como *Pendiente*.

---

## 20. Administración, persistencia y reinicio de datos

### 20.1 Qué se guarda y dónde

| Dato | Dónde | Notas |
|---|---|---|
| Configuración del proyecto (nombre, URL, proyecto, **token**) | Base de datos local del servidor de TraceDev | El token queda almacenado localmente. |
| Resultados del último análisis de cada etapa (con la matriz y los Issues congelados) | Base de datos local | Se recuperan al volver a abrir la herramienta. |
| Historial de análisis (índices, veredicto, tiempo) | Base de datos local | Solo lo alimenta Requerimientos. |
| Caché de resultados de Requerimientos | Base de datos local | |
| Versiones de matrices | Base de datos local | |
| Matrices y documentos | GitLab (TRZ) y carpeta `output/` | |

### 20.2 «Limpiar Base de Seguimiento (Caché e Historial)»

- Ubicación: menú lateral → **Administración**.
- **Qué borra (solo local):** seguimiento de Issues, historial, caché de resultados, registro de versiones de matrices y los resultados guardados de todas las etapas. Muestra: *«Base de datos limpia.»*
- **Qué NO borra:** la configuración del proyecto ni nada en GitLab (Issues, comentarios, etiquetas, TRZ).
- **No pide confirmación.** Los resultados que ya estén cargados en la pantalla actual pueden seguir visibles hasta recargar la página.
- Efectos prácticos: el Panel pierde historial y versiones; **Diseño puede mostrar su matriz como EDITADA o INVÁLIDA** porque pierde la referencia local «original» (ver 23.8). Úsese solo para reiniciar el seguimiento del proyecto.

### 20.3 Cambio de configuración

Guardar la configuración también **reinicia los resultados locales de las etapas** (ver 7.5).

### 20.4 Datos en pantalla vs. datos guardados

Mientras la sesión del navegador esté abierta, los resultados se mantienen en memoria; además se guardan en la base local, por lo que sobreviven al cierre del navegador y al reinicio de la aplicación.

---

## 21. Condiciones que habilitan o bloquean cada acción

| Acción | Se habilita cuando… |
|---|---|
| Botones del menú (excepto Configuración, Limpiar, Cerrar sesión) | Existe un proyecto configurado. |
| **Guardar e iniciar proyecto** | Los 4 campos están completos **y** la prueba de conexión fue exitosa con esos mismos datos. |
| **Iniciar análisis** (Requerimientos) | Hay al menos un Issue pendiente en el milestone. |
| Casilla de confirmación (Diseño y Codificación) | La matriz de entrada **no** es INVALIDA. (En Pruebas siempre está disponible.) |
| **Iniciar análisis de Diseño** | Matriz válida + casilla marcada + ≥ 1 DIS con entrada válida. |
| **Iniciar análisis de Codificación** | Matriz válida + casilla marcada + ≥ 1 COD con entrada válida + repositorio analizado + estado del repositorio distinto de BLOQUEADO. |
| **Iniciar análisis de Pruebas** | Casilla marcada + ≥ 1 PRU en estado VALIDO. |
| **Actualizar matriz en GitLab** (Diseño) | Matriz cargada desde Excel con diferencias respecto a GitLab. |
| **Editar en GitLab / Ver TRZ en GitLab** | El Issue TRZ correspondiente existe. |
| Descargas de Reporte/Documento (Diseño, Codificación, Pruebas) | Hay resultados. |
| Descarga de Reporte/Documento (Requerimientos) | Tras presionar «Generar…» en esa misma sesión. |

---

## 22. Mensajes frecuentes y qué hacer

| Mensaje / situación | Causa probable | Qué hacer |
|---|---|---|
| *«No se pudo validar la conexión: …»* | URL, proyecto o token incorrectos; sin permisos; sin red. | Revisar los datos y los permisos del token; volver a probar. |
| *«Primero debes probar correctamente esta conexión con GitLab.»* | Se cambió algún dato después de probar, o no se probó. | Presionar «Probar conexión» otra vez. |
| *«No se encontraron issues abiertos en este milestone.»* (Requerimientos) | No hay HU abiertas con etiqueta Pendiente/Requiere modificación en el milestone *Recepción de Requerimientos*; o están Revisadas. | Verificar milestone, estado abierto y etiquetas en GitLab; presionar «Actualizar desde GitLab». |
| *«No se encontraron Issues de Diseño/Codificación/Pruebas en el milestone.»* | Idem para cada milestone. | Idem. |
| *«Información insuficiente: titulo, descripcion…»* (HU) | La HU no tiene los mínimos. | Completar la HU con la plantilla y marcarla **Pendiente**. |
| Matriz **INVALIDA** en Diseño | TRZ-001 vacío o con códigos/campos incorrectos; o Requerimientos no se ejecutó. | Corregir en GitLab o Excel, o ejecutar Requerimientos; presionar «Actualizar desde GitLab». |
| *«TRZ-001 todavía no existe en GitLab…»* | Requerimientos no fue ejecutado. | Ejecutar la etapa 1 primero. |
| *«TRZ-002 no está disponible en GitLab…»* | Diseño no fue ejecutado. | Ejecutar la etapa 2 primero. |
| *«TRZ-003 no está disponible en GitLab todavía…»* | Codificación no fue ejecutada. | Ejecutar la etapa 3 primero. |
| DIS/COD/PRU con 🔴 y «referencias inválidas» | Cita RF/RNF, ED o COD que no existen en la matriz vigente. | Corregir las referencias en el Issue (o la matriz) y actualizar. Si la matriz cambia y el código pasa a existir, el Issue se desbloquea. |
| Botón «Iniciar análisis…» deshabilitado | Falta alguna condición de la sección 21. | Revisar casilla de confirmación, matriz, Issues válidos y (Codificación) análisis del repositorio. |
| Codificación: estado **BLOQUEADO** | Ningún COD tiene rutas y ED válidos. | Revisar rutas (deben existir en la rama predeterminada) y ED declarados. |
| *«Error al descubrir el repositorio: …»* | Problemas de acceso al repositorio. | Revisar token/permisos y la rama predeterminada. |
| *«No se pudo publicar la retroalimentación en GitLab (…)»* | Fallo al escribir en GitLab. | El resultado sigue visible en pantalla; revisar permisos del token y reintentar. |
| *«La retroalimentación no fue publicada en GitLab.»* | El comentario no se pudo publicar. | Ídem. |
| Mensaje de error técnico en rojo durante el análisis (p. ej. límite de uso del servicio de IA, tiempo de espera o respuesta inválida del modelo) | Cuota o caída del proveedor de IA, o respuesta del modelo fuera de formato. | Esperar el tiempo indicado por el proveedor y volver a ejecutar. Los resultados de los Issues ya terminados quedan en memoria durante la sesión, pero se guardan de forma permanente solo cuando el análisis de la etapa concluye. |
| Métrica «No evaluable» en Codificación | Herramienta no aplicable al lenguaje o sin manifiesto/archivos analizables. | Revisar «Evidencia técnica utilizada» y la declaración de archivos. |
| Un Issue ya analizado desapareció de la lista | Quedó **Revisada**. | Volver a marcarlo **Pendiente** si se desea reanalizar. |

---

## 23. Limitaciones y observaciones detectadas

Estas observaciones surgen de leer el código y son importantes para el manual (advertencias, notas o decisiones a confirmar con el equipo). Las marcadas **[Verificado]** se comprobaron ejecutando la función correspondiente.

### 23.1 TRZ-001 se reescribe con lo procesado en cada ejecución

Cada análisis de Requerimientos construye TRZ-001 **solo con las historias procesadas en esa ejecución** y reemplaza la matriz anterior; además los códigos RF/RNF se numeran de nuevo por ejecución. Si se reprocesan solo algunas HU (por ejemplo, las que *Requieren modificación*) mientras otras ya están *Revisadas*, TRZ-001 podría quedar con un subconjunto de requerimientos y con códigos que no coinciden con los publicados antes. **Recomendación para el manual:** analizar todas las HU del milestone en una misma ejecución antes de pasar a Diseño, o documentar el procedimiento de reproceso aprobado por el equipo.

### 23.2 Diferencias en cómo cada etapa lista los Issues

- Requerimientos, Diseño y Pruebas listan solo Issues con etiqueta **Pendiente** o **Requiere modificación**: un Issue **sin ninguna etiqueta de flujo no aparece**.
- Codificación lista **todos los Issues abiertos** del milestone, incluidos los Revisados y los sin etiqueta.
- Las etiquetas de flujo se crean solas únicamente la primera vez que la herramienta actualiza un Issue; antes de eso, hay que crearlas (o al menos «Pendiente») manualmente en GitLab.

### 23.3 [Verificado] Carga de matriz modificada en Codificación

Al cargar un Excel/CSV en Codificación (tanto el cuadro «Cargar matriz de Diseño modificada» como el cuadro inicial cuando TRZ-002 no existe), el archivo se interpreta con el formato de la matriz de **Requerimientos** y se pierden las columnas propias de TRZ-002. Probado con una matriz exportada: el resultado es **INVALIDA** («Fila sin columna requerida: 'Código requisito'»). En la práctica, en Codificación la matriz debe tomarse de GitLab (TRZ-002); la edición por Excel no es utilizable hasta corregirse. En Pruebas no existe esta carga. *Sugerencia: no documentar este flujo como válido en el manual, o corregirlo antes.*

### 23.4 Diseño solo bloquea por referencias inexistentes

La pantalla de Diseño marca un DIS como «válido» o «bloqueado» únicamente según sus referencias a RF/RNF. No comprueba por adelantado que existan elementos de diseño, descripción u otras secciones. Un DIS incompleto puede enviarse al análisis y terminar en un error técnico o con resultados pobres. Se recomienda en el manual insistir en completar la plantilla.

### 23.5 Avisos en GitLab solo para referencias inexistentes

En Diseño, Codificación y Pruebas, el comentario de aviso + etiqueta *Requiere modificación* se publica **solo** para Issues con referencias inexistentes. Los Issues con información insuficiente (Codificación, Pruebas) o sin pruebas (Pruebas) quedan sin analizar **sin aviso en GitLab**, solo se ven en la pantalla de entradas. En Requerimientos la información insuficiente sí se comunica en GitLab.

### 23.6 El historial y el panel reflejan solo Requerimientos

«Análisis registrados», «Calidad promedio», «Seguridad promedio», «Tiempo promedio», «Último análisis» y la gráfica de tendencia se calculan con el historial que escribe únicamente la etapa de Requerimientos. Las etapas de Diseño, Codificación y Pruebas no lo alimentan (sí aparecen en «Avance por etapa» y «Trazabilidad por matriz»).

### 23.7 Criterios de «meta» distintos al umbral de aprobación

En el Resumen de Requerimientos, «Historias bajo meta» usa 95 % (calidad) y 85 % (seguridad), mientras que la aprobación usa 80 %. Una HU puede estar *CONFORME* y a la vez contarse «bajo meta». Conviene explicarlo o unificar el criterio.

### 23.8 La «matriz original» de Diseño depende del historial local

El estado ORIGINAL/EDITADA de la matriz de entrada de Diseño se calcula comparando con una «matriz original» reconstruida desde el historial local de Requerimientos. Si ese historial se limpia (o contiene ejecuciones antiguas), la matriz puede aparecer como **EDITADA** (o **INVALIDA** si TRZ-001 no existe) aunque nadie la haya modificado.

### 23.9 Nomenclatura de métricas de Pruebas

En pantalla y documentos las métricas de Pruebas son **MC-07 Corrección Funcional** y **MC-08 Corrección de Fallos**, pero el comentario que se publica en GitLab las rotula **«MC-06 Corrección Funcional»** y **«MC-07 Corrección de Fallos»**. Es una inconsistencia de rotulado a corregir o aclarar.

### 23.10 Acciones sin confirmación

«Limpiar Base de Seguimiento» y «Guardar e iniciar proyecto» (que reinicia resultados locales) no piden confirmación previa.

### 23.11 Tiempos y dependencias externas

La duración y el éxito del análisis dependen de la disponibilidad y cuota de los servicios de IA y de GitLab; no hay cola ni reintento manual: si falla, se vuelve a presionar «Iniciar análisis…». Mientras se ejecuta no hay botón para cancelar.

### 23.12 Rol fijo en la cabecera

El rol «Encargado de DNTIC» es un texto fijo; no se obtiene de la cuenta ni cambia por usuario.

### 23.13 Estado «ERROR»

El estado ERROR está previsto en pantalla y documentos, pero un fallo técnico del análisis normalmente se manifiesta como un mensaje de error de la aplicación (no como un resultado con estado ERROR). Confirmar con pruebas en vivo antes de describirlo en el manual.

---

## 24. Insumos para el Manual de Usuario

### 24.1 Estructura sugerida del manual

1. Introducción (qué es TraceDev, a quién va dirigido, aviso de decisión humana) — *secciones 1 y 2*.
2. Antes de empezar (requisitos y preparación en GitLab) — *secciones 4 y 9*.
3. Ingreso y recorrido por la pantalla — *secciones 5, 6 y 8*.
4. Configuración del proyecto — *sección 7*.
5. Guía por etapa (una por capítulo, con el mismo esquema: preparar Issues → entradas → ejecutar → resultados → documentos → qué se publica en GitLab) — *secciones 10 a 13*.
6. Panel del proyecto — *sección 14*.
7. Cómo interpretar los resultados (estados, índices y métricas) — *secciones 16 y 17*.
8. Matrices de trazabilidad — *sección 15*.
9. Administración y buenas prácticas — *sección 20 y Anexo C*.
10. Solución de problemas — *sección 22*.
11. Glosario — *sección 2*.

### 24.2 Capturas de pantalla sugeridas

| N.º | Pantalla |
|---|---|
| 1 | Pantalla de inicio de sesión con el botón de Microsoft 365. |
| 2 | Cabecera con la insignia de sesión y el menú lateral completo (con proyecto configurado). |
| 3 | Formulario de configuración, antes y después de «Probar conexión» exitosa (tarjetas Conectado/Verificados). |
| 4 | Selector de las cuatro etapas y tarjeta «Etapa activa». |
| 5 | Barra «Fases de la etapa» con una fase abierta y el botón «Siguiente fase». |
| 6 | Requerimientos — fase de entradas (lista de HU con etiquetas). |
| 7 | Requerimientos — progreso del análisis en curso. |
| 8 | Requerimientos — Resumen general, detalle de una HU (pestañas Resumen, Calidad, Seguridad, Formalización) y pestaña «Matriz y documentos». |
| 9 | Diseño — tarjeta de matriz (estados ORIGINAL / EDITADA / INVALIDA) y las cinco acciones sobre la matriz. |
| 10 | Diseño — pestaña «Issues de Diseño» con un DIS bloqueado (🔴). |
| 11 | Diseño/Codificación/Pruebas — casilla de confirmación y botón de inicio habilitado/deshabilitado. |
| 12 | Codificación — fase «Información técnica del repositorio» (indicadores, lenguajes y tabla de herramientas). |
| 13 | Codificación — «Evidencia técnica utilizada» y métricas MC-05, MS-05, MS-06, MS-07. |
| 14 | Pruebas — resultados con MC-07, MC-08, MS-08, MS-09. |
| 15 | Panel del proyecto completo (salud, avance, tendencia, trazabilidad, versiones). |
| 16 | En GitLab: un Issue con el comentario de retroalimentación y la etiqueta cambiada; el Issue TRZ-00x con la matriz. |
| 17 | Plantillas de Issues (HU, DIS, COD, PRU) completadas de ejemplo. |

### 24.3 Preguntas a confirmar con el equipo antes de cerrar el manual

1. ¿Qué procedimiento oficial se seguirá para **reprocesar historias** sin perder requerimientos en TRZ-001 (ver 23.1)?
2. ¿Se corregirá la carga de Excel en Codificación (23.3) o se retira del manual?
3. ¿El manual debe cubrir la instalación y la configuración de credenciales (Microsoft Entra ID, `.env`, servicios de IA, Gitleaks) o solo el uso?
4. ¿Se unificará el criterio «Historias bajo meta» con el umbral de 80 % (23.7) y el rotulado MC-06/MC-07 de Pruebas (23.9)?
5. ¿Hay roles distintos al «Encargado de DNTIC» que usen la herramienta (p. ej. líderes de equipo que solo consultan el Panel)?
6. ¿Quién crea y mantiene las etiquetas y milestones, y quién asigna la etiqueta inicial **Pendiente** a los Issues?

---

## Anexo A — Inventario de botones y controles

| Pantalla | Control | Tipo | Acción |
|---|---|---|---|
| Inicio de sesión | Iniciar sesión con Microsoft 365 | Botón primario | Abre el acceso de Microsoft. |
| Menú lateral | Panel del proyecto | Botón | Abre el panel. |
| Menú lateral | Configuración del proyecto | Botón | Abre la configuración. |
| Menú lateral | Evaluación por etapas | Botón | Abre la pantalla de etapas. |
| Menú lateral | Requerimientos / Diseño / Codificación / Pruebas | Botones | Abren la etapa. |
| Menú lateral | Limpiar Base de Seguimiento (Caché e Historial) | Botón | Borra datos locales. |
| Menú lateral | Cerrar sesión | Botón | Cierra la sesión. |
| Configuración | Nombre del proyecto / URL del servidor GitLab / Proyecto GitLab / Token de acceso | Campos de texto | Datos del proyecto. |
| Configuración | Probar conexión | Botón | Valida GitLab y verifica/crea milestones. |
| Configuración | Guardar e iniciar proyecto | Botón primario | Guarda la configuración. |
| Etapas | Botones circulares 1–4 | Botones | Cambian de etapa. |
| Fases | Ver/Ocultar entradas · repositorio · análisis · resultados | Botones | Muestran/ocultan fases. |
| Fases | Siguiente fase → | Botón | Avanza a la siguiente fase. |
| Requerimientos / Entradas | Actualizar desde GitLab | Botón | Reconsulta las HU. |
| Requerimientos / Análisis | Iniciar análisis | Botón primario | Ejecuta el análisis de las HU. |
| Requerimientos / Resultados | Selector de HU | Botones | Elige la HU a detallar. |
| Requerimientos / Resultados | Descargar matriz CSV | Descarga | `matriz_trazabilidad.csv`. |
| Requerimientos / Resultados | Generar Reporte Ejecutivo → Descargar Reporte PDF | Botones | PDF del lote. |
| Requerimientos / Resultados | Generar Documento Formal → Descargar Documento DOCX | Botones | Word del lote. |
| Diseño y Codificación / Entradas | Actualizar desde GitLab | Botón | Relee TRZ-001 / TRZ-002. |
| Diseño y Codificación / Entradas | Editar en GitLab | Enlace | Abre el Issue de la matriz. |
| Diseño y Codificación / Entradas | Editar con Excel | Descarga | Matriz de entrada en Excel. |
| Diseño y Codificación / Entradas | Cargar matriz modificada | Carga de archivo | xlsx / csv. |
| Diseño / Entradas | Actualizar matriz en GitLab | Botón | Sube la matriz de Excel a TRZ-001. |
| Pruebas / Entradas | Actualizar desde GitLab · Ver TRZ-003 en GitLab | Botón · Enlace | Relee / abre TRZ-003. |
| Diseño, Codificación, Pruebas / Entradas | Actualizar issues | Botón | Reconsulta los Issues del milestone. |
| Codificación / Repositorio | Analizar repositorio / Actualizar repositorio | Botón | Explora el repositorio. |
| Diseño, Codificación, Pruebas / Análisis | Casilla de confirmación | Casilla | Confirma la matriz vigente. |
| Diseño, Codificación, Pruebas / Análisis | Iniciar análisis de Diseño / Codificación / Pruebas | Botón primario | Ejecuta el análisis. |
| Diseño, Codificación, Pruebas / Resultados | Selector de Issue | Botones | Elige el Issue a detallar. |
| Diseño, Codificación, Pruebas / Resultados | Descargar matriz (Excel) · Descargar Reporte Ejecutivo · Descargar Documento Formal | Descargas | Artefactos de la etapa. |
| Panel | Actualizar datos de GitLab | Botón | Recarga avance y trazabilidad. |

---

## Anexo B — Resumen de estados por etapa

| Concepto | Requerimientos | Diseño | Codificación | Pruebas |
|---|---|---|---|---|
| Issue de trabajo | HU-XXX | DIS-XXX | COD-XXX | PRU-XXX |
| Milestone | Recepción de Requerimientos | Diseño | Codificación | Pruebas |
| Matriz de entrada | — | TRZ-001 | TRZ-002 | TRZ-003 |
| Matriz que publica | TRZ-001 | TRZ-002 | TRZ-003 | TRZ-004 |
| Confirmación previa | No | Sí | Sí | Sí |
| Fases | 3 | 3 | 4 (con repositorio) | 3 |
| Métricas de calidad | MC-01, MC-02 | MC-03, MC-04 | MC-05 | MC-07, MC-08 |
| Métricas de seguridad | MS-01, MS-02 (+ LoT) | MS-03, MS-04 | MS-05, MS-06, MS-07 | MS-08, MS-09 |
| Estados | CONFORME · CONFORME CON MEJORAS · CORREGIR · REVISIÓN HUMANA | CONFORME · CONFORME CON MEJORAS · CORREGIR · ERROR | CONFORME · CONFORME CON MEJORAS · CORREGIR · ERROR | APROBADO · REVISAR · CORREGIR · ERROR |
| Estado de entrada del Issue | Entrada válida · con advertencias · información insuficiente | Entrada válida · Trazabilidad incompleta | entrada_valida · informacion_insuficiente · referencias_invalidas | VALIDO · INFORMACION_INSUFICIENTE · REFERENCIA_INVALIDA · SIN_PRUEBAS |
| Edición de la matriz de entrada | — | GitLab / Excel | GitLab / Excel (con limitación) | Solo GitLab |
| Documentos | Generar y luego descargar | Descarga directa | Descarga directa | Descarga directa |

---

## Anexo C — Ciclo de trabajo recomendado (paso a paso)

**Preparación (una vez)**
1. Confirmar que el proyecto de GitLab, el token, las credenciales de Microsoft 365 y los servicios de IA están listos.
2. Iniciar sesión y completar la **Configuración del proyecto** (Probar conexión → Guardar).
3. En GitLab, crear las etiquetas **Pendiente**, **Revisada** y **Requiere modificación** (si no existen) y confirmar los cuatro milestones.

**Etapa 1 — Requerimientos**
4. El equipo registra las HU con la plantilla en el milestone *Recepción de Requerimientos*, con etiqueta **Pendiente**.
5. En TraceDev: *Requerimientos* → **Ver entradas** → **Actualizar desde GitLab** → revisar la lista.
6. **Ver análisis** → **Iniciar análisis**; esperar a que termine (no recargar).
7. **Ver resultados**: revisar el Resumen general y el detalle de cada HU; descargar la matriz, el reporte y el documento formal.
8. Atender las HU *Requiere modificación*: corregirlas en GitLab, ponerlas en **Pendiente** y repetir los pasos 5–7 (ver 23.1 sobre el reproceso).

**Etapa 2 — Diseño**
9. El equipo registra los DIS con sus RF/RNF y elementos ED, en el milestone *Diseño*, etiqueta **Pendiente**.
10. En TraceDev: *Diseño* → **Ver entradas**: revisar la tarjeta de la matriz (idealmente ORIGINAL/VÁLIDA) y los DIS (🟢). Corregir lo que esté en 🔴.
11. **Ver análisis** → marcar la casilla de confirmación → **Iniciar análisis de Diseño**.
12. **Ver resultados**: revisar índices, hallazgos y matriz TRZ-002; descargar los documentos.
13. Corregir los DIS *Requiere modificación* y repetir.

**Etapa 3 — Codificación**
14. El equipo sube el código al repositorio (rama predeterminada) y registra los COD con ED y archivos, en el milestone *Codificación*.
15. En TraceDev: *Codificación* → **Ver entradas** (matriz TRZ-002 y COD válidos) → **Ver repositorio** → **Analizar repositorio** (verificar que no esté BLOQUEADO).
16. **Ver análisis** → casilla → **Iniciar análisis de Codificación**.
17. **Ver resultados**: revisar evidencia técnica y métricas MC-05, MS-05, MS-06, MS-07; descargar documentos. Corregir y repetir según sea necesario.

**Etapa 4 — Pruebas**
18. El equipo registra los PRU (formato exacto de Estado y Sí/No) con COD existentes, en el milestone *Pruebas*.
19. En TraceDev: *Pruebas* → **Ver entradas** (TRZ-003 y PRU válidos) → **Ver análisis** → casilla → **Iniciar análisis de Pruebas**.
20. **Ver resultados**: revisar MC-07, MC-08, MS-08, MS-09 y la matriz TRZ-004; descargar documentos.

**Seguimiento permanente**
21. Consultar el **Panel del proyecto** para ver el avance por etapa, la cobertura de trazabilidad y las versiones de las matrices.
22. Recordar que toda decisión de aceptación final corresponde al responsable del proyecto.
