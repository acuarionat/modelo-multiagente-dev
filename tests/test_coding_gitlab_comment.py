from integrations.issue_service import construir_comentario_codificacion

resumen_con_correcciones = {
    "codificacion_id": "COD-001",
    "estado_orientativo": "CORREGIR",
    "indice_calidad_codigo": 0.6666666666666666,
    "indice_seguridad_codigo": 0.9,
    "correcciones_necesarias": ["La función autenticar tiene complejidad 12, por encima del umbral aceptable."],
    "precisiones_necesarias": [],
    "oportunidades_mejora": ["Agregar pruebas unitarias adicionales."],
}

comentario = construir_comentario_codificacion(resumen_con_correcciones)
print("\n" + "=" * 70)
print("construir_comentario_codificacion — con correcciones")
print("=" * 70)
print(comentario)

assert "COD-001" in comentario
assert "CORREGIR" in comentario
assert "complejidad 12" in comentario
assert "Actualizar el Issue de Codificación" in comentario
assert "Ninguna." in comentario  # precisiones vacías

resumen_conforme = {
    "codificacion_id": "COD-002",
    "estado_orientativo": "CONFORME",
    "indice_calidad_codigo": 1.0,
    "indice_seguridad_codigo": 1.0,
    "correcciones_necesarias": [],
    "precisiones_necesarias": [],
    "oportunidades_mejora": [],
}
comentario_conforme = construir_comentario_codificacion(resumen_conforme)
print("\n" + "=" * 70)
print("construir_comentario_codificacion — conforme")
print("=" * 70)
print(comentario_conforme)
assert "queda marcado como Revisado" in comentario_conforme

print("\nTodas las verificaciones de coding_gitlab_comment pasaron.")
