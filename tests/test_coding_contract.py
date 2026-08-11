import copy

from core.coding_contract import validar_entrada_codificacion

ELEMENTOS_VALIDOS = {"ED-01", "ED-02", "ED-03"}

issue_valido = {
    "issue_iid": 25,
    "codificacion_id": "COD-001",
    "titulo": "COD-001 — Servicio de autenticación",
    "descripcion": "Se implementó el servicio de autenticación.",
    "elementos_diseno_declarados": ["ED-01", "ED-02"],
    "archivos_declarados": [{"ruta": "core/auth_service.py", "descripcion": "..."}],
}

resultado_valido = validar_entrada_codificacion(issue_valido, ELEMENTOS_VALIDOS)
print("\n" + "=" * 70)
print("validar_entrada_codificacion — entrada válida")
print("=" * 70)
print(resultado_valido)
assert resultado_valido["estado"] == "entrada_valida"
assert resultado_valido["entrada_valida"] is True
assert resultado_valido["campos_faltantes"] == []
assert resultado_valido["referencias_invalidas"] == []


# ---------------------------------------------------------
# ED-99 no existe en la matriz heredada de Diseño
# ---------------------------------------------------------

issue_ed_inexistente = copy.deepcopy(issue_valido)
issue_ed_inexistente["elementos_diseno_declarados"] = ["ED-01", "ED-99"]

resultado_ed_invalido = validar_entrada_codificacion(issue_ed_inexistente, ELEMENTOS_VALIDOS)
print("\n" + "=" * 70)
print("validar_entrada_codificacion — ED-99 inexistente")
print("=" * 70)
print(resultado_ed_invalido)
assert resultado_ed_invalido["estado"] == "referencias_invalidas"
assert resultado_ed_invalido["entrada_valida"] is False
assert resultado_ed_invalido["referencias_invalidas"] == ["ED-99"]


# ---------------------------------------------------------
# Información insuficiente (sin archivos declarados)
# ---------------------------------------------------------

issue_sin_archivos = copy.deepcopy(issue_valido)
issue_sin_archivos["archivos_declarados"] = []

resultado_sin_archivos = validar_entrada_codificacion(issue_sin_archivos, ELEMENTOS_VALIDOS)
print("\n" + "=" * 70)
print("validar_entrada_codificacion — sin archivos declarados")
print("=" * 70)
print(resultado_sin_archivos)
assert resultado_sin_archivos["estado"] == "informacion_insuficiente"
assert resultado_sin_archivos["entrada_valida"] is False
assert "archivos_declarados" in resultado_sin_archivos["campos_faltantes"]


# ---------------------------------------------------------
# Sin issue_iid / codificacion_id / descripción
# ---------------------------------------------------------

issue_incompleto = {
    "issue_iid": None,
    "codificacion_id": "",
    "titulo": "",
    "descripcion": "",
    "elementos_diseno_declarados": [],
    "archivos_declarados": [],
}
resultado_incompleto = validar_entrada_codificacion(issue_incompleto, ELEMENTOS_VALIDOS)
print("\n" + "=" * 70)
print("validar_entrada_codificacion — issue incompleto")
print("=" * 70)
print(resultado_incompleto)
assert resultado_incompleto["estado"] == "informacion_insuficiente"
assert set(resultado_incompleto["campos_faltantes"]) >= {
    "issue_iid", "codificacion_id", "titulo", "descripcion", "elementos_diseno_declarados", "archivos_declarados",
}

print("\nTodas las verificaciones de coding_contract pasaron.")
