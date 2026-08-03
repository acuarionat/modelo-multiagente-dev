import io
import json
import tempfile
import unittest
from pathlib import Path

from core.utils import (
    ArtifactGenerationError,
    DocumentModelValidationError,
    deduplicar_textos_estables,
    generar_artefactos_atomicos,
    normalizar_restricciones_documentales,
    preparar_modelo_documental,
    validar_modelo_documental,
    extraer_porcentaje,
)


def _fixture_batch():
    counts = {6: (3, 2), 7: (4, 0), 8: (3, 1), 9: (5, 0), 10: (2, 0)}
    rf_index = rnf_index = 0
    issues = []
    for iid, (rf_count, rnf_count) in counts.items():
        requirements = []
        for _ in range(rf_count):
            rf_index += 1
            requirements.append({
                "id": f"RF-{rf_index:03d}", "nombre": f"Función {rf_index}",
                "descripcion_formal": f"El sistema deberá ejecutar la función {rf_index}.",
                "tipo": "RF", "procedencia": "explícita — funcionalidad",
            })
        for _ in range(rnf_count):
            rnf_index += 1
            requirements.append({
                "id": f"RNF-{rnf_index:03d}", "nombre": f"Condición {rnf_index}",
                "descripcion_formal": f"El sistema deberá cumplir la condición {rnf_index}.",
                "tipo": "RNF", "procedencia": "explícita — restricción",
            })
        security_index = None if iid == 9 else (0.5 if iid == 10 else 1.0)
        verdict = "REVISIÓN REQUERIDA" if iid == 9 else ("CORREGIR" if iid == 10 else "APROBADO")
        issues.append({
            "issue_iid": iid, "status": "ok",
            "central": {
                "historia_id": f"HU-{iid:03d}", "titulo": f"Historia {iid}",
                "actor": "Usuario", "objetivo": f"Objetivo {iid}",
                "restricciones": (
                    [{"regla": "No permitir duplicados.", "procedencia": "criterio"}]
                    if iid == 7 else []
                ),
                "requerimientos": requirements,
            },
            "quality": {"indice": 1.0, "metricas": {}},
            "security": {"indice": security_index, "metricas": {}},
            "evaluation": {"veredicto": verdict, "riesgos_criticos": []},
            "recommendations": (
                ["Clasificar explícitamente los datos identificados: Nombre ficticio, Documento ficticio."]
                if iid == 10 else []
            ),
        })
    return {
        "project": {"name": "Fixture local"},
        "milestone": {"name": "Recepción de Requerimientos"},
        "issues": issues,
        "recommendations": issues[-1]["recommendations"],
        "generated_at": "2026-08-03T00:00:00",
    }


class RestrictionNormalizationTests(unittest.TestCase):
    def test_supported_shapes(self):
        value = [
            " Restricción A ",
            {"restriccion": "Restricción B"},
            {"descripcion": "Restricción C"},
            {"regla": "Restricción D", "procedencia": "observación"},
            {"restricciones": [{"texto": "Restricción E"}]},
        ]
        self.assertEqual(
            normalizar_restricciones_documentales(value),
            ["Restricción A", "Restricción B", "Restricción C", "Restricción D", "Restricción E"],
        )

    def test_empty_and_unrecognized_are_omitted_without_repr(self):
        output = normalizar_restricciones_documentales([None, "", {}, {"metadata": "secreto"}, 9])
        self.assertEqual(output, [])
        self.assertNotIn("{", " ".join(output))

    def test_deduplication_is_stable_after_extraction(self):
        value = ["Primera", {"descripcion": " Primera "}, "Segunda"]
        self.assertEqual(normalizar_restricciones_documentales(value), ["Primera", "Segunda"])
        self.assertEqual(deduplicar_textos_estables(["B", "A", "B"]), ["B", "A"])

    def test_distinct_domains_are_plain_text(self):
        value = [
            {"regla": "No matricular sin prerrequisito."},
            {"condicion": "No aprobar una venta sin saldo."},
            {"detalle": "No cerrar la vacante sin aprobación de RR. HH."},
        ]
        self.assertEqual(len(normalizar_restricciones_documentales(value)), 3)

    def test_sanitized_diagnostic_identifies_issue_without_value(self):
        audit = []
        normalizar_restricciones_documentales(
            [{"metadata": "valor no visible"}],
            {"issue_iid": 77, "historia_id": "HU-077"}, audit,
        )
        self.assertEqual(audit[0]["issue_iid"], 77)
        self.assertEqual(audit[0]["object_keys"], ["metadata"])
        self.assertFalse(audit[0]["extraction_success"])
        self.assertNotIn("valor no visible", json.dumps(audit))


class DocumentModelTests(unittest.TestCase):
    def test_real_fixture_shape_normalizes_dict_and_preserves_requirements(self):
        batch = _fixture_batch()
        before = sum(len(x["central"]["requerimientos"]) for x in batch["issues"])
        model = preparar_modelo_documental(batch)
        result = validar_modelo_documental(
            model, expected_issue_ids=[6, 7, 8, 9, 10], expected_rf=17, expected_rnf=3,
        )
        self.assertEqual(result["rf"], 17)
        self.assertEqual(result["rnf"], 3)
        self.assertEqual(model["issues"][1]["central"]["restricciones"], ["No permitir duplicados."])
        self.assertEqual(before, sum(len(x["central"]["requerimientos"]) for x in model["issues"]))
        self.assertIsNone(model["issues"][3]["security"]["indice"])
        self.assertEqual(model["issues"][3]["evaluation"]["veredicto"], "REVISIÓN REQUERIDA")
        self.assertEqual(model["issues"][4]["evaluation"]["veredicto"], "CORREGIR")
        self.assertTrue(model["issues"][4]["recommendations"])

    def test_non_normalized_textual_dict_is_rejected(self):
        model = preparar_modelo_documental(_fixture_batch())
        model["issues"][0]["central"]["restricciones"] = [{"descripcion": "X"}]
        with self.assertRaises(DocumentModelValidationError):
            validar_modelo_documental(model)

    def test_none_metric_is_presented_as_not_evaluated(self):
        self.assertEqual(extraer_porcentaje(None), "No evaluado")

    def test_hu010_recommendation_survives_shared_model(self):
        model = preparar_modelo_documental(_fixture_batch())
        self.assertIn("Clasificar explícitamente", model["issues"][4]["recommendations"][0])

    def test_duplicate_code_is_rejected(self):
        model = preparar_modelo_documental(_fixture_batch())
        model["issues"][1]["central"]["requerimientos"][0]["id"] = "RF-001"
        with self.assertRaises(DocumentModelValidationError):
            validar_modelo_documental(model)


class AtomicArtifactTests(unittest.TestCase):
    @staticmethod
    def _bytes(_model):
        return io.BytesIO(b"valid")

    @staticmethod
    def _rows(model_issues, _date):
        rows = []
        for result in model_issues:
            for requirement in result["central"]["requerimientos"]:
                rows.append({
                    "Código": requirement["id"], "Nombre": requirement["nombre"],
                    "Descripción": requirement["descripcion_formal"],
                    "Tipo": "Funcional" if requirement["tipo"] == "RF" else "No funcional",
                    "Historia de origen": result["central"]["historia_id"],
                    "Fecha de generación": "03/08/2026",
                    "Estado de cumplimiento": "Pendiente de revisión",
                })
        return rows

    def _run(self, root, **kwargs):
        return generar_artefactos_atomicos(
            _fixture_batch(), root / "final", "fixture-artifacts", {"resultados": ["conservados"]},
            expected_issue_ids=[6, 7, 8, 9, 10], expected_rf=17, expected_rnf=3,
            pdf_generator=kwargs.get("pdf", self._bytes),
            docx_generator=kwargs.get("docx", self._bytes),
            csv_rows_builder=kwargs.get("csv", self._rows),
        )

    def test_success_publishes_all_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _model, paths, summary_path = self._run(root)
            self.assertEqual(set(paths), {"pdf", "docx", "csv"})
            self.assertTrue(all(Path(path).is_file() for path in paths.values()))
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["documents_generated"])
            self.assertEqual(summary["status"], "success")

    def test_pdf_failure_publishes_nothing_and_persists_summary(self):
        def fail(_model):
            raise RuntimeError("pdf failure")
        self._assert_failure(pdf=fail, expected_type="pdf")

    def test_docx_failure_removes_temporary_pdf(self):
        def fail(_model):
            raise RuntimeError("docx failure")
        self._assert_failure(docx=fail, expected_type="docx")

    def test_csv_failure_removes_temporary_documents(self):
        def fail(_issues, _date):
            raise RuntimeError("csv failure")
        self._assert_failure(csv=fail, expected_type="csv")

    def _assert_failure(self, expected_type, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ArtifactGenerationError) as raised:
                self._run(root, **kwargs)
            self.assertEqual(raised.exception.artifact_type, expected_type)
            self.assertFalse((root / "final").exists())
            self.assertFalse((root / ".building-fixture-artifacts").exists())
            summary = json.loads((root / "fixture-artifacts-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "error")
            self.assertFalse(summary["documents_generated"])
            self.assertTrue(summary["auditoria_documental"]["temporary_artifacts_removed"])
            self.assertEqual(summary["resultados"], ["conservados"])


if __name__ == "__main__":
    unittest.main()
