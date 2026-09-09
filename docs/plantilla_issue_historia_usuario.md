<!--
=====================================================================
PLANTILLA — Historia de Usuario (HU-XXX)  ·  Etapa: Requerimientos
=====================================================================
CÓMO USAR ESTA PLANTILLA:
1. Copia TODO el contenido a un nuevo Issue de GitLab en el milestone "Requerimientos".
2. La PRIMERA línea (sin #) es el TÍTULO del Issue. DEBE contener el código "HU-XXX"
   (p. ej. "HU-001 - ..."), porque la herramienta lo usa como identidad de la historia.
3. Sustituye cada texto entre corchetes [ ... ] por la información real.
4. Los bloques que empiezan con "> Guía:" y "> Ejemplo:" son AYUDA para llenar:
   BÓRRALOS antes de guardar el Issue (si los dejas, se mezclan con el contenido leído).
5. NO cambies los títulos de sección (## Descripción, ## Como, ## Quiero, ## Para,
   # Criterios de aceptación, # Restricciones, # Seguridad, etc.): la herramienta los
   busca por su texto exacto para leer la historia.
=====================================================================
-->

HU-XXX - [Título breve de la historia]

# Historia de Usuario

## Descripción

> **Guía:** Explica en lenguaje natural la necesidad del usuario: qué requiere y por qué,
> dando el contexto suficiente para entender la funcionalidad. 1 a 3 frases.
>
> **Ejemplo:** "El estudiante necesita reservar un ejemplar disponible del catálogo de la
> biblioteca para asegurar su disponibilidad antes de acudir a recogerlo."

[Escribe aquí la descripción de la necesidad]

---

## Como

> **Guía:** El ROL o actor que realiza la acción (quién). Una o dos palabras.
>
> **Ejemplo:** Estudiante

[Rol o actor]

## Quiero

> **Guía:** La FUNCIONALIDAD que el actor desea realizar (qué). Una frase.
>
> **Ejemplo:** Reservar un ejemplar disponible del catálogo de la biblioteca.

[Funcionalidad deseada]

## Para

> **Guía:** El OBJETIVO o beneficio que se busca (para qué). Una frase.
>
> **Ejemplo:** Asegurar la disponibilidad del ejemplar para recogerlo posteriormente.

[Objetivo o beneficio]

---

# Criterios de aceptación

> **Guía:** Condiciones concretas y verificables que deben cumplirse para dar la historia
> por terminada. Redáctalas como comportamientos observables del sistema. Una por viñeta.
>
> **Ejemplo:**
> - Mostrar únicamente los ejemplares que se encuentren disponibles para reserva.
> - Registrar la reserva asociándola al estudiante autenticado.
> - Mostrar una confirmación cuando la reserva se registre correctamente.

- [Criterio de aceptación verificable]
- [Criterio de aceptación verificable]
- [Criterio de aceptación verificable]

---

# Prioridad

> **Guía:** Importancia de la historia. Escribe exactamente una: **Alta**, **Media** o **Baja**.
> (Recomendado: si se omite, la herramienta lo marca como advertencia.)
>
> **Ejemplo:** Alta

[Alta | Media | Baja]

---

# Restricciones

> **Guía:** Reglas o limitaciones obligatorias (de negocio o técnicas) que el sistema debe
> respetar. Una por viñeta.
>
> **Ejemplo:**
> - Solo estudiantes autenticados pueden realizar reservas.
> - Un ejemplar solo puede tener una reserva activa simultáneamente.

- [Restricción obligatoria]
- [Restricción obligatoria]
- [Restricción obligatoria]

---

# Seguridad

## ¿La historia maneja datos sensibles?

> **Guía:** Marca con una **x** una sola opción (deja la otra vacía). Si es "Sí", enumera
> debajo los tipos de datos sensibles involucrados, uno por línea.
>
> **Ejemplo:**
> - [x] Sí
> - [ ] No
>
> Datos personales del estudiante.
> Identificador institucional del estudiante.

- [ ] Sí
- [ ] No

[Si marcaste "Sí", lista aquí los datos sensibles, uno por línea]

---

## Autenticación

> **Guía:** Cómo se identifica al usuario para usar la funcionalidad.
>
> **Ejemplo:** Inicio de sesión institucional.

[Mecanismo de autenticación]

---

## Autorización / Roles

> **Guía:** Qué rol o roles están autorizados a ejecutar la operación.
>
> **Ejemplo:** Estudiante.

[Rol(es) autorizado(s)]

---

## Auditoría

> **Guía:** Indica si las operaciones relevantes se registran para seguimiento (Sí/No) y,
> opcionalmente, qué se registra.
>
> **Ejemplo:** Sí. Se registra el estudiante, el ejemplar y la fecha y hora de la operación.

[Sí | No — qué se registra]

---

# Observaciones

> **Guía:** Notas adicionales, supuestos o pendientes conocidos al registrar la historia.
>
> **Ejemplo:** "La operación de reserva debe utilizar la disponibilidad actual del ejemplar.
> Se debe registrar el estudiante, el ejemplar y la fecha y hora de la operación."

[Escribe aquí las observaciones]
