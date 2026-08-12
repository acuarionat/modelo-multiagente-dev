from types import SimpleNamespace

from integrations.coding_issue_mapper import mapear_issue_codificacion

DESCRIPCION_COD_001 = """
## 1. Descripción de la implementación

Se implementó el servicio de autenticación de usuarios mediante tokens JWT.

## 2. Elementos de Diseño implementados

- ED-01
- ED-02

## 3. Ubicación de la implementación

| Archivo/Módulo | Descripción |
|---|---|
| core/auth_service.py | Lógica principal de autenticación (ED-01). |
| core/token_repository.py | Persistencia de tokens (ED-02). |

## 4. Decisiones de implementación

- Se usó bcrypt para el hash de contraseñas.
- Los tokens expiran a las 24 horas.

## 5. Observaciones

- Pendiente configurar rotación de claves en producción.
"""

issue_cod_001 = SimpleNamespace(
    iid=25,
    title="COD-001 — Servicio de autenticación",
    description=DESCRIPCION_COD_001,
    labels=["Pendiente"],
)

resultado = mapear_issue_codificacion(issue_cod_001)

print("\n" + "=" * 70)
print("mapear_issue_codificacion — COD-001")
print("=" * 70)
print(resultado)

assert resultado["issue_iid"] == 25
assert resultado["codificacion_id"] == "COD-001"
assert resultado["titulo"] == "COD-001 — Servicio de autenticación"
assert "autenticación de usuarios" in resultado["descripcion"]
assert resultado["elementos_diseno_declarados"] == ["ED-01", "ED-02"]
assert resultado["archivos_declarados"] == [
    {"ruta": "core/auth_service.py", "descripcion": "Lógica principal de autenticación (ED-01)."},
    {"ruta": "core/token_repository.py", "descripcion": "Persistencia de tokens (ED-02)."},
]
assert resultado["decisiones"] == [
    "Se usó bcrypt para el hash de contraseñas.",
    "Los tokens expiran a las 24 horas.",
]
assert resultado["observaciones"] == ["Pendiente configurar rotación de claves en producción."]
assert resultado["validacion_entrada"] == {"estado": "", "campos_faltantes": [], "advertencias": []}


# ---------------------------------------------------------
# Issue sin numerar en el título / secciones vacías
# ---------------------------------------------------------

issue_sin_datos = SimpleNamespace(
    iid=26,
    title="Implementación sin identificador claro",
    description="## 1. Descripción de la implementación\n\nNinguna.\n",
    labels=[],
)

resultado_vacio = mapear_issue_codificacion(issue_sin_datos)
print("\n" + "=" * 70)
print("mapear_issue_codificacion — sin datos")
print("=" * 70)
print(resultado_vacio)

assert resultado_vacio["codificacion_id"] == ""
assert resultado_vacio["descripcion"] == "Ninguna."
assert resultado_vacio["elementos_diseno_declarados"] == []
assert resultado_vacio["archivos_declarados"] == []


# ---------------------------------------------------------
# Rutas declaradas con formato de código inline (backticks)
# ---------------------------------------------------------

DESCRIPCION_COD_BACKTICKS = """
## 3. Ubicación de la implementación

| Archivo o módulo | Descripción |
|---|---|
| `src/App.tsx` | Componente principal |
| `src/App.css` | Estilos |
| `package.json` | Dependencias |
"""

issue_cod_backticks = SimpleNamespace(
    iid=27,
    title="COD-003 — Prueba de backticks",
    description=DESCRIPCION_COD_BACKTICKS,
    labels=["Pendiente"],
)

resultado_backticks = mapear_issue_codificacion(issue_cod_backticks)
print("\n" + "=" * 70)
print("mapear_issue_codificacion — rutas con backticks")
print("=" * 70)
print(resultado_backticks)

assert resultado_backticks["archivos_declarados"][0]["ruta"] == "src/App.tsx"
assert resultado_backticks["archivos_declarados"][1]["ruta"] == "src/App.css"
assert resultado_backticks["archivos_declarados"][2]["ruta"] == "package.json"
assert "`" not in resultado_backticks["archivos_declarados"][0]["ruta"]

print("\nTodas las verificaciones de coding_issue_mapper pasaron.")
