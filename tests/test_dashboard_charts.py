import unittest

from core.design_traceability import ETIQUETAS_ESTADO, resumir_trazabilidad_diseno
from core.dashboard_charts import (
    agrupar_ejecuciones,
    construir_porcentajes_trazabilidad,
    describir_cambios,
    etiqueta_cambio,
    historial_desde_resultados,
    normalizar_historial,
)


def registro(iid, fecha, calidad, seguridad, etapa="requerimientos", veredicto="CORREGIR"):
    return {
        "gitlab_iid": iid, "analysis_date": fecha, "quality_index": calidad,
        "security_index": seguridad, "verdict": veredicto, "stage": etapa,
    }


HISTORIAL = [
    # Ejecución 1 de Requerimientos (dos issues con 2 minutos de diferencia).
    registro(1, "2026-10-01 10:00:00", 0.90, 0.85),
    registro(2, "2026-10-01 10:02:00", 0.70, 0.85),
    # Ejecución 1 de Diseño.
    registro(10, "2026-10-01 12:00:00", 0.60, None, etapa="diseno"),
    # Ejecución 2 de Requerimientos (otro día): el issue 2 se corrigió, el 1 empeoró.
    registro(1, "2026-10-02 09:00:00", 0.75, 0.85),
    registro(2, "2026-10-02 09:03:00", 0.95, 0.90),
]


class TendenciaTests(unittest.TestCase):
    def test_cambio_indica_subida_bajada_y_cruce_del_umbral(self):
        self.assertEqual(etiqueta_cambio(90.0, None), "Primer valor evaluable")
        self.assertEqual(etiqueta_cambio(None, 80.0), "Sin índice evaluable")
        self.assertEqual(etiqueta_cambio(85.0, 85.0), "= sin cambio")
        self.assertEqual(etiqueta_cambio(88.0, 80.0), "▲ +8 pts · supera el umbral")
        self.assertEqual(etiqueta_cambio(79.0, 88.0), "▼ −9 pts · cae bajo el umbral")

    def test_ejecuciones_agrupan_por_etapa_y_ventana_de_tiempo(self):
        ejecuciones = agrupar_ejecuciones(normalizar_historial(HISTORIAL))
        self.assertEqual(
            [(e["ejecucion"], e["etapa"], e["issues"]) for e in ejecuciones],
            [(1, "requerimientos", 2), (2, "diseno", 1), (3, "requerimientos", 2)],
        )
        self.assertEqual(ejecuciones[0]["calidad"], 80.0)  # promedio de 90 y 70
        self.assertEqual(ejecuciones[2]["calidad"], 85.0)  # promedio de 75 y 95
        self.assertTrue(ejecuciones[2]["cambio_calidad"].startswith("▲ +5 pts"))
        self.assertIsNone(ejecuciones[1]["seguridad"])  # sin índice evaluable: no es 0
        self.assertEqual(ejecuciones[1]["cambio_seguridad"], "Sin índice evaluable")

    def test_filas_antiguas_sin_etapa_se_toman_como_requerimientos(self):
        filas = normalizar_historial([{"gitlab_iid": 1, "analysis_date": "2026-10-01 10:00:00", "quality_index": 0.5}])
        self.assertEqual(filas[0]["etapa"], "requerimientos")

    def test_lectura_automatica_detecta_cruces_y_extremos(self):
        frases = describir_cambios(agrupar_ejecuciones(normalizar_historial(HISTORIAL)))
        texto = "\n".join(frases)
        self.assertIn("Mayor subida de **calidad**", texto)
        self.assertNotIn("Mayor bajada de **calidad**", texto)  # solo hubo subida entre ejecuciones de la etapa


class ResultadosGuardadosTests(unittest.TestCase):
    def test_etapas_sin_historial_aportan_su_ultimo_resultado(self):
        diseno = {"diseno_resultados": {
            "DIS-002": {"design_context": [{"issue_iid": 8}], "design_summary": {
                "estado_orientativo": "CORREGIR", "indice_calidad_diseno": 0.7, "indice_seguridad_diseno": None}},
            "DIS-001": {"design_context": [{"issue_iid": 7}], "design_summary": {
                "estado_orientativo": "CONFORME", "indice_calidad_diseno": 1.0, "indice_seguridad_diseno": 1.0}},
            "DIS-003": {"design_context": [{"issue_iid": 9}], "design_summary": {"estado_orientativo": "ERROR"}},
        }}
        filas = historial_desde_resultados("diseno", diseno, "2026-10-04 20:14:30")
        self.assertEqual([(f["gitlab_iid"], f["quality_index"], f["stage"]) for f in filas], [(7, 1.0, "diseno"), (8, 0.7, "diseno")])
        self.assertEqual(normalizar_historial(filas)[0]["etapa_nombre"], "Diseño")

    def test_pruebas_promedia_solo_metricas_evaluadas(self):
        pruebas = {"pruebas_resultados": {"PRU-001": {
            "testing_context": [{"issue_iid": 19}],
            "testing_summary": {"estado_orientativo": "APROBADO", "metricas": {
                "MC-07": {"valor": 0.8, "estado": "EVALUADO"}, "MC-08": {"valor": None, "estado": "NO_APLICA"},
                "MS-08": {"valor": 1.0, "estado": "EVALUADO"}, "MS-09": {"valor": 0.5, "estado": "EVALUADO"}}},
        }}}
        fila = historial_desde_resultados("pruebas", pruebas, "2026-10-04 07:07:47")[0]
        self.assertEqual((fila["quality_index"], fila["security_index"]), (0.8, 0.75))

    def test_sin_resultados_o_etapa_desconocida_no_aporta_filas(self):
        self.assertEqual(historial_desde_resultados("diseno", None, "x"), [])
        self.assertEqual(historial_desde_resultados("requerimientos", {"a": 1}, "x"), [])


class TrazabilidadTests(unittest.TestCase):
    def test_porcentaje_de_cumplimiento_por_etapa(self):
        filas = construir_porcentajes_trazabilidad({
            "diseno": {"resumen": {"requisitos_totales": 10, "cubiertos": 8, "pendientes_relacion": 1,
                                   "requieren_revision": 1, "no_evaluados": 0}},
            "codificacion": {"resumen": {"elementos_diseno_totales": 4, "implementados": 1, "no_confirmados": 2,
                                         "no_evaluados": 0}},
            "pruebas": None,
        })
        por_etapa = {f["etapa"]: f for f in filas}
        self.assertEqual(set(por_etapa), {"diseno", "codificacion"})
        self.assertEqual(por_etapa["diseno"]["pct_cubierto"], 80.0)
        self.assertEqual(por_etapa["diseno"]["etiqueta"], "Diseño cubre requisitos")
        codificacion = por_etapa["codificacion"]
        self.assertEqual((codificacion["cubierto"], codificacion["atencion"], codificacion["pendiente"]), (1, 2, 1))
        self.assertEqual(codificacion["cubierto"] + codificacion["atencion"] + codificacion["pendiente"], codificacion["total"])


class CoherenciaTrazabilidadDisenoTests(unittest.TestCase):
    def test_resumen_cuenta_requisitos_unicos_y_coincide_con_el_porcentaje_del_grafico(self):
        def fila(codigo, estado):
            return {"Código requisito": codigo, "Estado de trazabilidad": ETIQUETAS_ESTADO[estado]}

        # RF-01 lo cubren dos Diseños y uno más lo deja en revisión: sigue siendo UN requisito cubierto.
        filas = [
            fila("RF-01", "CUBIERTO"), fila("RF-01", "CUBIERTO"), fila("RF-01", "REQUIERE_REVISION"),
            fila("RF-02", "REQUIERE_REVISION"), fila("RF-02", "PENDIENTE_RELACION"),
            fila("RF-03", "NO_EVALUADO"), fila("RF-04", "CUBIERTO"),
        ]
        resumen = resumir_trazabilidad_diseno(filas)
        self.assertEqual(resumen["requisitos_totales"], 4)
        self.assertEqual(
            (resumen["cubiertos"], resumen["requieren_revision"], resumen["pendientes_relacion"], resumen["no_evaluados"]),
            (2, 1, 0, 1),
        )
        fila_grafico = construir_porcentajes_trazabilidad({"diseno": {"resumen": resumen}})[0]
        self.assertEqual((fila_grafico["cubierto"], fila_grafico["total"], fila_grafico["pct_cubierto"]), (2, 4, 50.0))


if __name__ == "__main__":
    unittest.main()
