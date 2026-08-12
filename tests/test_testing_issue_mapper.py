from types import SimpleNamespace

from integrations.testing_issue_mapper import mapear_issue_pruebas

DESCRIPCION_PRU_001 = """
## 1. Implementación evaluada

- COD-001

---

## 2. Descripción general de las pruebas

Se realizaron pruebas sobre la reserva de libros.

---

# 3. Pruebas funcionales realizadas

| ID | Funcionalidad evaluada | Prueba realizada | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|---|
| CP-01 | Registrar una reserva | Se registró una reserva utilizando datos válidos | La reserva debe registrarse correctamente | La reserva fue registrada y se mostró la confirmación | Aprobada |
| CP-02 | Evitar reservas duplicadas | Se intentó registrar dos veces la misma reserva | El sistema debe rechazar la segunda operación | El sistema permitió registrar ambas reservas | Fallida |

---

# 4. Fallos detectados y correcciones

| ID | Fallo detectado | Detectado en | ¿Fue corregido? | ¿Se verificó la corrección? | Resultado de la verificación |
|---|---|---|---|---|---|
| FAL-01 | El sistema permitía registrar dos reservas iguales | CP-02 | Sí | Sí | Se repitió la prueba y la segunda reserva fue rechazada correctamente |

---

# 5. Verificación de seguridad

## 5.1 Controles de seguridad verificados

| ID | Control o medida de seguridad | ¿Aplicable? | ¿Fue verificado? | Forma de verificación | Resultado |
|---|---|---|---|---|---|
| CS-01 | Restringir operaciones administrativas a usuarios autorizados | Sí | Sí | Se intentó acceder utilizando un usuario sin permisos | El acceso fue rechazado |
| CS-02 | Registrar las operaciones importantes realizadas por el usuario | Sí | No | No se realizó una verificación específica | Pendiente de verificación |

## 5.2 Pruebas de seguridad realizadas

| ID | Prueba realizada | Resultado esperado | Resultado obtenido | Estado |
|---|---|---|---|---|
| PS-01 | Intentar acceder a una función administrativa sin autorización | El sistema debe rechazar el acceso | El acceso fue rechazado | Aprobada |

---

# 6. Evidencias de las pruebas

| ID | Prueba o fallo relacionado | Tipo de evidencia | Descripción o ubicación |
|---|---|---|---|
| EV-01 | CP-02 | Captura de pantalla | evidencias/cp-02.png |

---

# 7. Aspectos pendientes

- Verificar el registro de auditoría (CS-02).

---

# 8. Observaciones adicionales

- Ninguna.
"""

issue_pru_001 = SimpleNamespace(
    iid=40,
    title="PRU-001 — Pruebas del módulo de reservas",
    description=DESCRIPCION_PRU_001,
    labels=["Pendiente"],
)

resultado = mapear_issue_pruebas(issue_pru_001)

print("\n" + "=" * 70)
print("mapear_issue_pruebas — PRU-001")
print("=" * 70)
print(resultado)

assert resultado["issue_iid"] == 40
assert resultado["prueba_id"] == "PRU-001"
assert resultado["titulo"] == "PRU-001 — Pruebas del módulo de reservas"
assert resultado["codificaciones_relacionadas"] == ["COD-001"]
assert resultado["descripcion"] == "Se realizaron pruebas sobre la reserva de libros."
assert len(resultado["pruebas_funcionales"]) == 2

assert resultado["pruebas_funcionales"] == [
    {
        "id": "CP-01", "funcionalidad": "Registrar una reserva",
        "prueba_realizada": "Se registró una reserva utilizando datos válidos",
        "resultado_esperado": "La reserva debe registrarse correctamente",
        "resultado_obtenido": "La reserva fue registrada y se mostró la confirmación",
        "estado": "APROBADA",
    },
    {
        "id": "CP-02", "funcionalidad": "Evitar reservas duplicadas",
        "prueba_realizada": "Se intentó registrar dos veces la misma reserva",
        "resultado_esperado": "El sistema debe rechazar la segunda operación",
        "resultado_obtenido": "El sistema permitió registrar ambas reservas",
        "estado": "FALLIDA",
    },
]

assert resultado["fallos"] == [
    {
        "id": "FAL-01", "fallo": "El sistema permitía registrar dos reservas iguales",
        "detectado_en": "CP-02", "corregido": True, "verificado": True,
        "resultado_verificacion": "Se repitió la prueba y la segunda reserva fue rechazada correctamente",
    },
]

assert resultado["controles_seguridad"] == [
    {
        "id": "CS-01", "control": "Restringir operaciones administrativas a usuarios autorizados",
        "aplica": True, "verificado": True,
        "forma_verificacion": "Se intentó acceder utilizando un usuario sin permisos",
        "resultado": "El acceso fue rechazado",
    },
    {
        "id": "CS-02", "control": "Registrar las operaciones importantes realizadas por el usuario",
        "aplica": True, "verificado": False,
        "forma_verificacion": "No se realizó una verificación específica",
        "resultado": "Pendiente de verificación",
    },
]

assert resultado["pruebas_seguridad"] == [
    {
        "id": "PS-01", "prueba_realizada": "Intentar acceder a una función administrativa sin autorización",
        "resultado_esperado": "El sistema debe rechazar el acceso",
        "resultado_obtenido": "El acceso fue rechazado", "estado": "APROBADA",
    },
]

assert resultado["evidencias"] == [
    {
        "id": "EV-01", "prueba_o_fallo_relacionado": "CP-02",
        "tipo_evidencia": "Captura de pantalla", "descripcion": "evidencias/cp-02.png",
    },
]

assert resultado["pendientes"] == ["Verificar el registro de auditoría (CS-02)."]
assert resultado["observaciones"] == []
assert resultado["validacion_entrada"] == {"estado": "", "campos_faltantes": [], "advertencias": []}


# ---------------------------------------------------------
# Varias codificaciones (con y sin coma, con guion suelto)
# ---------------------------------------------------------

issue_varias_cod = SimpleNamespace(
    iid=41,
    title="PRU-002 — Pruebas del módulo de catálogo",
    description="""
## 1. Implementación evaluada

- COD-002

---

## 2. Descripción general de las pruebas

Se probó el catálogo de libros disponibles.
""",
    labels=[],
)

resultado_varias = mapear_issue_pruebas(issue_varias_cod)
print("\n" + "=" * 70)
print("mapear_issue_pruebas — PRU-002")
print("=" * 70)
print(resultado_varias)

assert resultado_varias["prueba_id"] == "PRU-002"
assert resultado_varias["codificaciones_relacionadas"] == ["COD-002"]
assert resultado_varias["descripcion"] == "Se probó el catálogo de libros disponibles."


# ---------------------------------------------------------
# Issue sin numerar en el título / secciones vacías
# ---------------------------------------------------------

DESCRIPCION_SIN_DATOS = """
## 1. Implementación evaluada

## 2. Descripción general de las pruebas

# 3. Pruebas funcionales realizadas

**No se realizaron pruebas funcionales porque:** el módulo aún no está listo.

# 7. Aspectos pendientes

**No se identificaron aspectos pendientes.**

# 8. Observaciones adicionales

-
"""

issue_sin_datos = SimpleNamespace(
    iid=42,
    title="Pruebas sin identificador claro",
    description=DESCRIPCION_SIN_DATOS,
    labels=[],
)

resultado_vacio = mapear_issue_pruebas(issue_sin_datos)
print("\n" + "=" * 70)
print("mapear_issue_pruebas — sin datos")
print("=" * 70)
print(resultado_vacio)

assert resultado_vacio["prueba_id"] == ""
assert resultado_vacio["codificaciones_relacionadas"] == []
assert resultado_vacio["descripcion"] == ""
assert resultado_vacio["pruebas_funcionales"] == []
assert resultado_vacio["pendientes"] == []
assert resultado_vacio["observaciones"] == []

print("\nTodas las verificaciones de testing_issue_mapper pasaron.")
