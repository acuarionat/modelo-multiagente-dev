<!--
=====================================================================
PLANTILLA — Issue de Codificación (COD-XXX)
=====================================================================
CÓMO USAR ESTA PLANTILLA:
1. Copia TODO el contenido a un nuevo Issue de GitLab en el milestone "Codificación".
2. La PRIMERA línea (sin #) es el TÍTULO del Issue. El resto (desde "# COD-XXX...")
   es la DESCRIPCIÓN del Issue.
3. Sustituye cada texto entre corchetes [ ... ] por la información real.
4. Los bloques que empiezan con "> Guía:" y "> Ejemplo:" son AYUDA para llenar:
   BÓRRALOS antes de guardar el Issue.
5. NO cambies los títulos de sección (## 1., ## 2., ...): la herramienta TraceDev
   los usa para leer el Issue.
=====================================================================
-->

COD-XXX - [Nombre corto de la implementación]

# COD-XXX - [Nombre corto de la implementación]

<!-- Ejemplo de título: COD-001 - Implementación de Reserva de Libros -->

## 1. Descripción de la implementación

> **Guía:** Describe en 1 a 3 párrafos QUÉ se implementó y CÓMO se organizó a alto
> nivel (qué flujo cubre, qué responsabilidades se separaron). No pegues código aquí.
>
> **Ejemplo:** "Se implementó el flujo de consulta y reserva de libros, incluyendo la
> consulta de ejemplares disponibles, la validación previa al registro, la creación de
> la reserva y la actualización de la disponibilidad. La implementación separa la
> interacción con el usuario, la lógica de negocio y la persistencia."

[Escribe aquí la descripción de la implementación]

---

## 2. Elementos de Diseño implementados

> **Guía:** Lista los identificadores de los Elementos de Diseño (ED-XX) que esta
> implementación cubre. Deben existir en la Matriz de Trazabilidad de Diseño (TRZ-002);
> si referencias un ED inexistente, el Issue no será analizado.
>
> **Ejemplo:**
> - ED-01
> - ED-02
> - ED-03

- [ED-XX]
- [ED-XX]
- [ED-XX]

---

## 3. Ubicación de la implementación

> **Guía:** Indica los archivos o módulos donde vive la implementación y, en una frase,
> la responsabilidad de cada uno. Usa comillas invertidas `` ` `` para las rutas.
> Agrega o elimina filas según necesites; conserva el encabezado y la línea de guiones.
>
> **Ejemplo:**
> | Archivo o módulo | Descripción |
> |---|---|
> | `app/reservations/service.py` | Contiene la lógica de consulta, validación y registro de reservas |

| Archivo o módulo | Descripción |
|---|---|
| `[ruta/al/archivo.ext]` | [Responsabilidad de este archivo] |
| `[ruta/al/archivo.ext]` | [Responsabilidad de este archivo] |
| `[ruta/al/archivo.ext]` | [Responsabilidad de este archivo] |

---

## 4. Decisiones de implementación

> **Guía:** Enumera las decisiones técnicas relevantes (dónde se concentró la lógica,
> qué separaciones se respetaron, validaciones importantes, orden de las operaciones).
> Una decisión por viñeta, en frases afirmativas y concretas.
>
> **Ejemplo:**
> - La lógica de negocio relacionada con reservas se concentra en `reservation_service`.
> - La interfaz no accede directamente al repositorio de reservas.
> - La disponibilidad se verifica nuevamente inmediatamente antes de registrar la reserva.

- [Decisión de implementación]
- [Decisión de implementación]
- [Decisión de implementación]

---

## 5. Consideraciones de seguridad implementadas

> **Guía:** Enumera los controles de seguridad efectivamente aplicados (autenticación,
> origen confiable de los datos, auditoría, mínima exposición de información, manejo de
> credenciales). Una consideración por viñeta.
>
> **Ejemplo:**
> - Las operaciones de reserva requieren un usuario autenticado.
> - El identificador del estudiante se obtiene de la sesión autenticada, no del cliente.
> - Los datos de conexión y credenciales se obtienen desde variables de entorno.

- [Consideración de seguridad]
- [Consideración de seguridad]
- [Consideración de seguridad]

---

## 6. Dependencias relevantes utilizadas

> **Guía:** Lista las librerías o dependencias externas usadas por la implementación.
> Solo el nombre (opcionalmente la versión). Una por viñeta.
>
> **Ejemplo:**
> - `Flask`
> - `SQLAlchemy`
> - `python-dotenv`

- `[dependencia]`
- `[dependencia]`
- `[dependencia]`

---

## 7. Observaciones

> **Guía:** Anota el estado de la implementación y cualquier pendiente o aclaración
> conocida al registrar el Issue. Si no hay pendientes, indícalo explícitamente.
>
> **Ejemplo:** "La implementación se encuentra funcional y lista para análisis estático.
> No se identificaron pendientes conocidos al momento de registrar este Issue."

[Escribe aquí las observaciones]
