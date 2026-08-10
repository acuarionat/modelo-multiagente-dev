import os

from integrations.issue_service import construir_comentario_diseno, publicar_comentario_diseno
from tests.fixtures_diseno import DESIGN_SUMMARY_POR_DISENO


PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

resumen_dis001 = DESIGN_SUMMARY_POR_DISENO["DIS-001"]
issue_iid_dis001 = resumen_dis001["issue_iid"]


# ---------------------------------------------------------
# Construcción y validación del texto (siempre, sin publicar)
# ---------------------------------------------------------

comentario = construir_comentario_diseno(resumen_dis001)

print("\n" + "=" * 70)
print("COMENTARIO A PUBLICAR — DIS-001")
print("=" * 70)
print(comentario)

assert "Resultado del análisis de Diseño" in comentario
assert "Estado orientativo" in comentario
assert "Índice de Calidad de Diseño" in comentario
assert "Índice de Seguridad de Diseño" in comentario
assert "Correcciones necesarias" in comentario
assert "Precisiones" in comentario
assert "Oportunidades de mejora" in comentario
assert "Próxima acción" in comentario
assert "Evaluación asistida" in comentario
assert "{" not in comentario
assert "}" not in comentario


# ---------------------------------------------------------
# Protecciones obligatorias
# ---------------------------------------------------------

try:
    publicar_comentario_diseno(PROJECT_ID, issue_iid_dis001, {})
    raise AssertionError("Debía rechazar un resumen de Diseño vacío.")
except ValueError:
    pass

try:
    publicar_comentario_diseno(
        PROJECT_ID, issue_iid_dis001, {**resumen_dis001, "estado_orientativo": "ERROR"},
    )
    raise AssertionError("Debía rechazar un resumen de Diseño con estado_orientativo ERROR.")
except ValueError:
    pass

print("\nValidación del texto y de las protecciones: OK.")


# ---------------------------------------------------------
# Publicación real — solo si se activa explícitamente
# ---------------------------------------------------------

if os.getenv("PUBLISH_GITLAB_TEST") != "1":
    print("\nPublicación real omitida (PUBLISH_GITLAB_TEST != '1').")
else:
    nota = publicar_comentario_diseno(PROJECT_ID, issue_iid_dis001, resumen_dis001)
    print("\nComentario publicado realmente en GitLab.")
    print("Issue:", issue_iid_dis001)
    print("Nota creada, id:", getattr(nota, "id", nota))
