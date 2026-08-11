import unittest

from core.coding_contract import validar_entrada_codificacion
from core.coding_matrix_input import extraer_elementos_diseno_validos
from integrations.design_traceability_issue_mapper import (
    construir_markdown_matriz_trazabilidad_diseno,
    mapear_matriz_trazabilidad_diseno,
)


class CodingTRZ002ValidationTests(unittest.TestCase):
    def test_trz002_ed_existente_cod_valido_e_inexistente_invalido(self):
        filas = [{
            "HU origen": "HU-001",
            "Código requisito": "RF-001",
            "Tipo": "Funcional",
            "Nombre del requisito": "Consultar horarios",
            "Descripción": "Consulta de horarios disponibles.",
            "Diseño": "DIS-001",
            "Elementos de Diseño": "ED-01, ED-02",
            "Estado de trazabilidad": "Cubierto en Diseño",
            "Estado de Diseño": "CONFORME",
            "Observación": "Relación identificada con evidencia suficiente.",
        }]
        trz002 = construir_markdown_matriz_trazabilidad_diseno(filas)
        matriz_entrada_codificacion = mapear_matriz_trazabilidad_diseno(trz002)
        elementos_validos = extraer_elementos_diseno_validos(matriz_entrada_codificacion)

        issue_base = {
            "issue_iid": 10,
            "codificacion_id": "COD-001",
            "titulo": "Implementar consulta",
            "descripcion": "Implementación del elemento de diseño.",
            "archivos_declarados": [{"ruta": "src/consulta.py"}],
        }
        valido = validar_entrada_codificacion(
            {**issue_base, "elementos_diseno_declarados": ["ED-01"]}, elementos_validos,
        )
        invalido = validar_entrada_codificacion(
            {**issue_base, "elementos_diseno_declarados": ["ED-99"]}, elementos_validos,
        )

        self.assertTrue(valido["entrada_valida"])
        self.assertFalse(invalido["entrada_valida"])
        self.assertEqual(invalido["referencias_invalidas"], ["ED-99"])


if __name__ == "__main__":
    unittest.main()
