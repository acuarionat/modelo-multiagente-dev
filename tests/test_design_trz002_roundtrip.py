import unittest
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import patch

utils_sin_dependencias_documentales = ModuleType("core.utils")
utils_sin_dependencias_documentales.TRACEABILITY_COLUMNS = [
    "Código", "Nombre", "Descripción", "Tipo", "Historia de origen",
    "Fecha de generación", "Estado de revisión",
]
utils_sin_dependencias_documentales.construir_filas_trazabilidad = lambda *args, **kwargs: []
utils_sin_dependencias_documentales.construir_resultado_lote = lambda *args, **kwargs: {}
utils_sin_dependencias_documentales.extraer_porcentaje = lambda valor: valor
sys.modules["core.utils"] = utils_sin_dependencias_documentales

from integrations.issue_service import (
    crear_o_actualizar_issue_matriz_trazabilidad_diseno,
    obtener_issue_matriz_trazabilidad_diseno,
)


FILAS_DISENO = [
    {
        "HU origen": "HU-001",
        "Código requisito": "RF-001",
        "Tipo": "Funcional",
        "Nombre del requisito": "Consultar horarios",
        "Descripción": "Consultar horarios disponibles | sin alterar el contenido.",
        "Diseño": "DIS-001",
        "Elementos de Diseño": "ED-01, ED-02",
        "Estado de trazabilidad": "Cubierto en Diseño",
        "Estado de Diseño": "CONFORME",
        "Observación": "Relación identificada con evidencia suficiente.",
    },
]


class _GitLabFalso:
    issue = None

    def __init__(self, project_id=None):
        self.project_id = project_id

    def buscar_issue_por_titulo(self, titulo):
        return self.__class__.issue

    def crear_issue(self, titulo, descripcion):
        self.__class__.issue = SimpleNamespace(
            iid=2, title=titulo, description=descripcion, web_url="https://gitlab.test/trz-002",
        )
        return self.__class__.issue

    def actualizar_descripcion_issue(self, issue_iid, descripcion):
        self.__class__.issue.description = descripcion
        return self.__class__.issue


class DesignTRZ002RoundTripTests(unittest.TestCase):
    def test_matriz_diseno_trz002_lectura_misma_matriz(self):
        _GitLabFalso.issue = None
        with patch("integrations.issue_service.GitLabAdapter", _GitLabFalso):
            crear_o_actualizar_issue_matriz_trazabilidad_diseno(
                "proyecto", FILAS_DISENO, metadata={"matriz_version": "2.0"},
            )
            issue, recuperadas = obtener_issue_matriz_trazabilidad_diseno("proyecto")

        self.assertEqual(issue.title, "TRZ-002 - Matriz de Trazabilidad - Etapa Diseño")
        self.assertEqual(recuperadas, FILAS_DISENO)


if __name__ == "__main__":
    unittest.main()
