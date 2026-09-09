<!--
=====================================================================
PLANTILLA — Diseño (DIS-XXX)  ·  Etapa: Diseño
=====================================================================
CÓMO USAR ESTA PLANTILLA:
1. Copia TODO el contenido a un nuevo Issue de GitLab en el milestone "Diseño".
2. La PRIMERA línea (sin #) es el TÍTULO del Issue. DEBE contener el código "DIS-XXX"
   (p. ej. "DIS-001 - ..."), porque la herramienta lo usa como identidad del diseño.
3. Sustituye cada texto entre corchetes [ ... ] por la información real.
4. Los bloques que empiezan con "> Guía:" y "> Ejemplo:" son AYUDA para llenar:
   BÓRRALOS antes de guardar el Issue.
5. NO cambies los títulos de sección numerados (## 1., ## 2., ### 5.1, ...): la
   herramienta los busca por su texto para leer el diseño.
6. En las TABLAS conserva el encabezado y la línea de guiones (|---|). Agrega o elimina
   FILAS de datos según necesites, pero no quites columnas.
7. Los IDs de elementos (ED-01, ED-02, ...) son el enlace hacia Codificación y Pruebas:
   defínelos aquí con cuidado. Los códigos RF-/RNF- deben existir en la matriz de
   Requerimientos (TRZ-001).
=====================================================================
-->

DIS-XXX - [Título breve del diseño]

# Plantilla de Diseño

---

## 1. Requerimientos relacionados

> **Guía:** Lista los códigos de los requerimientos (RF-XXX funcionales, RNF-XXX no
> funcionales) de la etapa anterior que este diseño atiende. Uno por viñeta.
>
> **Ejemplo:**
> - RF-001
> - RF-002
> - RNF-001

- [RF-XXX o RNF-XXX]
- [RF-XXX o RNF-XXX]
- [RF-XXX o RNF-XXX]

---

## 2. Descripción general del diseño

> **Guía:** Explica en 1 o 2 párrafos cómo está estructurado el diseño: qué
> responsabilidades se separan (interfaz, lógica de negocio, datos) y cómo fluye la
> información entre ellas. No incluyas código.
>
> **Ejemplo:** "El diseño separa la interacción con el estudiante, la gestión de reservas,
> la administración de la disponibilidad y la persistencia. La interfaz recibe la solicitud
> y la deriva al gestor de reservas, que verifica la disponibilidad, registra la reserva y
> solicita su actualización. La persistencia se mantiene separada de la lógica de negocio."

[Escribe aquí la descripción general del diseño]

---

## 3. Elementos principales del diseño

> **Guía:** Cada fila es un componente del diseño. Columnas:
> - **ID:** identificador único del elemento (ED-01, ED-02, ...). Es la referencia que
>   usarán Codificación y Pruebas.
> - **Elemento:** nombre del componente.
> - **Tipo:** categoría (Interfaz, Servicio, Componente, Base de datos, ...).
> - **Responsabilidad principal:** qué hace, en una frase.
> - **Requerimientos relacionados:** códigos RF/RNF que cubre.
>
> **Ejemplo:**
> | ED-01 | Interfaz de reserva de libros | Interfaz | Recibir la solicitud y mostrar el resultado de la reserva | RF-001, RF-002 |

| ID | Elemento | Tipo | Responsabilidad principal | Requerimientos relacionados |
|---|---|---|---|---|
| ED-01 | [Nombre del elemento] | [Interfaz/Servicio/Componente/Base de datos] | [Qué hace] | [RF-XXX, RNF-XXX] |
| ED-02 | [Nombre del elemento] | [Tipo] | [Qué hace] | [RF-XXX] |
| ED-03 | [Nombre del elemento] | [Tipo] | [Qué hace] | [RF-XXX] |

---

## 4. Relaciones entre elementos

> **Guía:** Describe cómo interactúan los elementos entre sí. Usa los IDs definidos arriba.
> Columnas: **Origen** (ED que inicia), **Destino** (ED que recibe), **Relación o
> interacción** (nombre corto), **Descripción** (qué ocurre en esa interacción).
>
> **Ejemplo:**
> | ED-01 | ED-02 | Solicita reserva | ED-01 envía al gestor la solicitud del estudiante |

| Origen | Destino | Relación o interacción | Descripción |
|---|---|---|---|
| [ED-XX] | [ED-XX] | [Nombre de la interacción] | [Qué ocurre en esta relación] |
| [ED-XX] | [ED-XX] | [Nombre de la interacción] | [Qué ocurre en esta relación] |
| [ED-XX] | [ED-XX] | [Nombre de la interacción] | [Qué ocurre en esta relación] |

---

## 5. Seguridad considerada en el diseño

### 5.1 Amenazas o situaciones de riesgo identificadas

> **Guía:** Cada fila es un riesgo de seguridad y cómo se mitiga. Columnas:
> - **Amenaza o situación identificada:** el riesgo.
> - **Elemento afectado:** ID(s) del elemento afectado (ED-XX; si son varios, sepáralos por comas).
> - **¿Tiene tratamiento?:** escribe **Sí** o **No**.
> - **Tratamiento previsto:** cómo se mitiga (si aplica).
>
> **Ejemplo:**
> | Un usuario no autenticado podría intentar reservar | ED-01 | Sí | Exigir sesión autenticada antes de permitir el acceso |

| Amenaza o situación identificada | Elemento afectado | ¿Tiene tratamiento? | Tratamiento previsto |
|---|---|---|---|
| [Descripción del riesgo] | [ED-XX] | [Sí/No] | [Cómo se mitiga] |
| [Descripción del riesgo] | [ED-XX, ED-XX] | [Sí/No] | [Cómo se mitiga] |

---

### 5.2 Medidas de seguridad previstas

> **Guía:** Controles de seguridad que el diseño incorpora. Columnas: **Aspecto relacionado**
> (Autenticación, Autorización, Auditoría, Protección de datos, ...), **Medida prevista en el
> diseño** (qué se hace), **Elemento responsable** (ID del ED que la implementa).
>
> **Ejemplo:**
> | Autenticación | Verificar que el estudiante tenga sesión antes de acceder | ED-01 |

| Aspecto relacionado | Medida prevista en el diseño | Elemento responsable |
|---|---|---|
| [Aspecto] | [Medida prevista] | [ED-XX] |
| [Aspecto] | [Medida prevista] | [ED-XX] |

---

## 6. Restricciones y decisiones importantes

### Restricciones del diseño

> **Guía:** Reglas de diseño que deben respetarse obligatoriamente. Una por viñeta.
>
> **Ejemplo:**
> - La interfaz no debe acceder directamente al repositorio de reservas.
> - La disponibilidad debe verificarse nuevamente antes de registrar la reserva.

- [Restricción del diseño]
- [Restricción del diseño]
- [Restricción del diseño]

### Decisiones importantes de diseño

> **Guía:** Decisiones técnicas relevantes que se tomaron y por qué (dónde se concentra la
> lógica, qué se separa, etc.). Una por viñeta.
>
> **Ejemplo:**
> - La lógica de las reservas se concentra en ED-02.
> - ED-04 se limita a las operaciones de persistencia.

- [Decisión importante de diseño]
- [Decisión importante de diseño]
- [Decisión importante de diseño]

---

## 7. Observaciones adicionales

> **Guía:** Notas finales, supuestos o pendientes conocidos al documentar el diseño. Una por
> viñeta. Si no hay pendientes, indícalo.
>
> **Ejemplo:**
> - El diseño mantiene separadas presentación, lógica, disponibilidad y persistencia.
> - No se identificaron aspectos pendientes relevantes.

- [Observación adicional]
- [Observación adicional]
