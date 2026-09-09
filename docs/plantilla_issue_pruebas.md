<!--
=====================================================================
PLANTILLA — Pruebas (PRU-XXX)  ·  Etapa: Pruebas
=====================================================================
CÓMO USAR ESTA PLANTILLA:
1. Copia TODO el contenido a un nuevo Issue de GitLab en el milestone "Pruebas".
2. La PRIMERA línea (sin #) es el TÍTULO del Issue. DEBE contener el código "PRU-XXX"
   (p. ej. "PRU-001 - ..."), porque la herramienta lo usa como identidad de la prueba.
3. Sustituye cada texto entre corchetes [ ... ] por la información real.
4. Los bloques que empiezan con "> Guía:" y "> Ejemplo:" son AYUDA para llenar:
   BÓRRALOS antes de guardar el Issue.
5. NO cambies los títulos de sección numerados (## 1., # 3., ## 5.1, ...): la herramienta
   los busca por su texto para leer la prueba.
6. En las TABLAS conserva el encabezado y la línea de guiones (|---|). Agrega o elimina
   FILAS según necesites, pero no quites columnas.
7. FORMATOS OBLIGATORIOS en las tablas:
   - Columna "Estado": escribe exactamente **Aprobada** o **Fallida**.
   - Columnas de Sí/No (¿Fue corregido?, ¿Aplicable?, ¿Fue verificado?): escribe **Sí** o **No**.
   - La implementación evaluada debe referenciar códigos "COD-XXX" existentes (Codificación).
=====================================================================
-->

PRU-XXX - [Título breve de las pruebas]

# PRU-XXX - [Título breve de las pruebas]

## 1. Implementación evaluada

> **Guía:** Código(s) de la(s) implementación(es) de Codificación que estas pruebas evalúan
> (COD-XXX). Uno por viñeta. Deben existir en la matriz de trazabilidad de Codificación (TRZ-003).
>
> **Ejemplo:**
> * COD-001

* [COD-XXX]

---

## 2. Descripción general de las pruebas

> **Guía:** Explica en 1 o 2 párrafos qué se probó (funcionalidades y controles de seguridad)
> y con qué enfoque. No incluyas resultados detallados aquí (van en las tablas).
>
> **Ejemplo:** "Se realizaron pruebas funcionales y de seguridad sobre el proceso de consulta
> y reserva de libros: consultar ejemplares disponibles, registrar una reserva y evitar
> reservas duplicadas. También se verificaron los controles de autenticación, autorización,
> protección de datos y registro de operaciones."

[Escribe aquí la descripción general de las pruebas]

---

# 3. Pruebas funcionales realizadas

> **Guía:** Una fila por caso de prueba funcional. Columnas: **ID** (CP-01, CP-02, ...),
> **Funcionalidad evaluada**, **Prueba realizada** (qué se hizo), **Resultado esperado**,
> **Resultado obtenido**, **Estado** (exactamente **Aprobada** o **Fallida**).
>
> **Ejemplo:**
> | CP-01 | Consultar ejemplares disponibles | Se consultó el catálogo con un estudiante autenticado | Mostrar solo ejemplares disponibles | Se mostraron solo los disponibles | Aprobada |

| ID | Funcionalidad evaluada | Prueba realizada | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|---|
| CP-01 | [Funcionalidad] | [Qué se hizo] | [Qué debía ocurrir] | [Qué ocurrió] | [Aprobada/Fallida] |
| CP-02 | [Funcionalidad] | [Qué se hizo] | [Qué debía ocurrir] | [Qué ocurrió] | [Aprobada/Fallida] |
| CP-03 | [Funcionalidad] | [Qué se hizo] | [Qué debía ocurrir] | [Qué ocurrió] | [Aprobada/Fallida] |

---

# 4. Fallos detectados y correcciones

> **Guía:** Una fila por fallo encontrado durante las pruebas. Columnas: **ID** (FAL-01, ...),
> **Fallo detectado**, **Detectado en** (ID del caso, p. ej. CP-04), **¿Fue corregido?** (Sí/No),
> **¿Se verificó la corrección?** (Sí/No), **Resultado de la verificación**.
> Si no se detectaron fallos, deja solo el encabezado o escribe una fila indicándolo.
>
> **Ejemplo:**
> | FAL-01 | El ejemplar seguía disponible unos segundos tras reservarlo | CP-04 | Sí | Sí | Se repitió la prueba y el estado cambió de inmediato |

| ID | Fallo detectado | Detectado en | ¿Fue corregido? | ¿Se verificó la corrección? | Resultado de la verificación |
|---|---|---|---|---|---|
| FAL-01 | [Descripción del fallo] | [CP-XX] | [Sí/No] | [Sí/No] | [Resultado de la verificación] |
| FAL-02 | [Descripción del fallo] | [CP-XX] | [Sí/No] | [Sí/No] | [Resultado de la verificación] |

---

# 5. Verificación de seguridad

## 5.1 Controles de seguridad verificados

> **Guía:** Una fila por control de seguridad. Columnas: **ID** (CS-01, ...), **Control o medida
> de seguridad**, **¿Aplicable?** (Sí/No), **¿Fue verificado?** (Sí/No), **Forma de verificación**,
> **Resultado**.
>
> **Ejemplo:**
> | CS-01 | Exigir autenticación antes de reservar | Sí | Sí | Se intentó acceder sin sesión | El sistema impidió el acceso |

| ID | Control o medida de seguridad | ¿Aplicable? | ¿Fue verificado? | Forma de verificación | Resultado |
|---|---|---|---|---|---|
| CS-01 | [Control de seguridad] | [Sí/No] | [Sí/No] | [Cómo se verificó] | [Resultado obtenido] |
| CS-02 | [Control de seguridad] | [Sí/No] | [Sí/No] | [Cómo se verificó] | [Resultado obtenido] |

---

## 5.2 Pruebas de seguridad realizadas

> **Guía:** Una fila por prueba de seguridad ejecutada. Columnas: **ID** (PS-01, ...),
> **Prueba realizada**, **Resultado esperado**, **Resultado obtenido**, **Estado**
> (exactamente **Aprobada** o **Fallida**).
>
> **Ejemplo:**
> | PS-01 | Intentar acceder a la reserva sin autenticación | El sistema debe impedir el acceso | El acceso fue rechazado | Aprobada |

| ID | Prueba realizada | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| PS-01 | [Qué se probó] | [Qué debía ocurrir] | [Qué ocurrió] | [Aprobada/Fallida] |
| PS-02 | [Qué se probó] | [Qué debía ocurrir] | [Qué ocurrió] | [Aprobada/Fallida] |

---

# 6. Evidencias de las pruebas

> **Guía:** Una fila por evidencia que respalda las pruebas. Columnas: **ID** (EV-01, ...),
> **Prueba o fallo relacionado** (IDs CP/PS/FAL, separados por comas), **Tipo de evidencia**
> (Captura de pantalla, Registro del sistema, Observación directa, ...), **Descripción o ubicación**.
>
> **Ejemplo:**
> | EV-01 | CP-01, CP-02 | Captura de pantalla | Catálogo mostrando ejemplares disponibles |

| ID | Prueba o fallo relacionado | Tipo de evidencia | Descripción o ubicación |
|---|---|---|---|
| EV-01 | [CP-XX, PS-XX, FAL-XX] | [Tipo de evidencia] | [Descripción o ubicación] |
| EV-02 | [CP-XX] | [Tipo de evidencia] | [Descripción o ubicación] |

---

# 7. Aspectos pendientes

> **Guía:** Pendientes que quedan tras ejecutar y verificar las pruebas. Una por viñeta.
> Si no queda ninguno, indícalo explícitamente.
>
> **Ejemplo:**
> - No se identificaron aspectos pendientes después de repetir las pruebas de los fallos corregidos.

- [Aspecto pendiente, o indica que no hay ninguno]

---

# 8. Observaciones adicionales

> **Guía:** Notas finales sobre la ejecución (cómo se ejecutaron las pruebas, alcance de la
> verificación, etc.). Una por viñeta.
>
> **Ejemplo:**
> - Todas las funcionalidades registradas en este Issue fueron ejecutadas manualmente.
> - Los fallos encontrados fueron corregidos y verificados repitiendo las pruebas.

- [Observación adicional]
- [Observación adicional]
