import re

from core.utils import extraer_porcentaje
from integrations.issue_service import construir_comentario_diseno
from tests.fixtures_diseno import DESIGN_SUMMARY_POR_DISENO, RESULTADOS_CENTRAL_DISENO

CAMPOS_INTERNOS = (
    "diseno_id", "estado_orientativo", "indice_calidad_diseno", "indice_seguridad_diseno",
    "correcciones_necesarias", "precisiones_necesarias", "oportunidades_mejora", "metricas",
)

ED_VALIDOS = {
    "DIS-001": {"ED-01", "ED-02", "ED-03"},
    "DIS-002": {"ED-04", "ED-05", "ED-06"},
}

RF_VALIDOS = {
    resultado["diseno_id"]: {
        item["requisito"] for item in resultado.get("trazabilidad_diseno", [])
    } | {
        item["requisito"] for item in resultado.get("requisitos_sin_relacion_evidente", [])
    }
    for resultado in RESULTADOS_CENTRAL_DISENO
}


def extraer_bullets(texto: str) -> list:
    return [linea[2:].strip() for linea in texto.splitlines() if linea.startswith("- ")]


def validar_comentario_diseno(diseno_id: str) -> None:
    resumen = DESIGN_SUMMARY_POR_DISENO[diseno_id]
    texto = construir_comentario_diseno(resumen)

    print("\n" + "=" * 70)
    print(f"COMENTARIO DE DISEÑO — {diseno_id}")
    print("=" * 70)
    print(texto)

    # ✓ contiene diseno_id
    assert resumen["diseno_id"] in texto

    # ✓ contiene estado orientativo
    assert resumen["estado_orientativo"] in texto

    # ✓ contiene ambos índices
    assert extraer_porcentaje(resumen["indice_calidad_diseno"]) in texto
    assert extraer_porcentaje(resumen["indice_seguridad_diseno"]) in texto

    # ✓ contiene correcciones reales
    for correccion in resumen["correcciones_necesarias"]:
        assert correccion in texto

    # ✓ no contiene JSON
    assert "{" not in texto
    assert "}" not in texto
    assert '"' not in texto

    # ✓ no contiene campos internos (nombres de clave en snake_case crudo)
    for campo in CAMPOS_INTERNOS:
        assert campo not in texto

    # ✓ no inventa RF/ED
    ed_mencionados = set(re.findall(r"\bED-\d+\b", texto))
    rf_mencionados = set(re.findall(r"\bRN?F-\d+\b", texto))
    assert ed_mencionados <= ED_VALIDOS[diseno_id]
    assert rf_mencionados <= RF_VALIDOS[diseno_id]

    # ✓ no repite recomendaciones
    bullets = extraer_bullets(texto)
    assert len(bullets) == len(set(bullets))


validar_comentario_diseno("DIS-001")
validar_comentario_diseno("DIS-002")

print("\nTodas las verificaciones del comentario de Diseño pasaron (texto construido, sin publicar).")
