import copy
import inspect
import unittest

from core.batch_contract import completar_requerimientos_explicitos_faltantes


def req(nombre, descripcion, tipo="RF"):
    return {
        "nombre": nombre,
        "descripcion_formal": descripcion,
        "tipo": tipo,
        "origen": "",
        "justificacion": "Formalizado por Central.",
        "prioridad": "Alta",
    }


ISSUES = {
    6: {
        "id": 6, "historia_id": "HU-006", "funcionalidad": "Consultar horarios disponibles",
        "criterios_aceptacion": [
            "Mostrar únicamente horarios disponibles.",
            "Mostrar nombre y especialidad del médico.",
            "Actualizar la disponibilidad después de programar la cita.",
        ],
        "restricciones": ["El tiempo de respuesta deberá ser menor a tres segundos."],
        "observaciones": "La información de disponibilidad deberá mostrarse en tiempo real.",
        "prioridad": "Alta",
    },
    7: {
        "id": 7, "historia_id": "HU-007", "funcionalidad": "Registrar pacientes",
        "criterios_aceptacion": [
            "Validar el documento del paciente.",
            "Registrar la información del paciente.",
            "Impedir registros duplicados por documento.",
        ],
        "restricciones": [], "observaciones": "Permitir editar la información del paciente.",
        "prioridad": "Alta",
    },
    8: {
        "id": 8, "historia_id": "HU-008", "funcionalidad": "Consultar agenda médica",
        "criterios_aceptacion": ["Mostrar las citas del día.", "Mostrar el nombre del paciente en cada cita."],
        "restricciones": [], "observaciones": "La agenda deberá actualizarse en tiempo real.",
        "prioridad": "Alta",
    },
    9: {
        "id": 9, "historia_id": "HU-009", "funcionalidad": "Generar reportes de citas",
        "criterios_aceptacion": [
            "Filtrar los reportes por fecha.", "Exportar los reportes en PDF.",
            "Mostrar estadísticas de citas.",
        ],
        "restricciones": [], "observaciones": "Los reportes deben poder imprimirse.",
        "prioridad": "Media",
    },
    10: {
        "id": 10, "historia_id": "HU-010", "funcionalidad": "Cancelar una cita médica",
        "criterios_aceptacion": [
            "El paciente puede cancelar una cita.",
            "No se podrá cancelar una cita con menos de 24 horas de anticipación.",
        ],
        "restricciones": [], "observaciones": [], "prioridad": "Alta",
    },
}


RAW = {
    6: [
        req("Consulta Horarios Médicos Disponibles", "El sistema deberá mostrar únicamente horarios disponibles."),
        req("Mostrar Nombre y Especialidad del Médico", "El sistema deberá mostrar el nombre y la especialidad del médico."),
        req("Actualizar Disponibilidad Después de Programar Cita", "El sistema deberá actualizar la disponibilidad después de que el paciente programe una cita."),
    ],
    7: [
        req("Validar Documento del Paciente", "El sistema deberá validar el documento del paciente."),
        req("Registrar Información del Paciente", "El sistema deberá registrar la información del paciente."),
        req("Impedir Registros Duplicados", "El sistema deberá impedir registros duplicados por documento."),
    ],
    8: [
        req("Consulta del Calendario Médico", "El sistema deberá mostrar las citas del día."),
        req("Mostrar Nombres de Pacientes", "El sistema deberá mostrar el nombre del paciente en cada cita."),
    ],
    9: [
        req("Generar Reportes de Citas", "El sistema deberá generar reportes de citas."),
        req("Exportación PDF", "El sistema deberá exportar los reportes en PDF."),
        req("Filtrar por Fecha", "El sistema deberá filtrar los reportes por fecha."),
    ],
    10: [req("Permitir la cancelación de una cita médica", "El sistema deberá permitir que el paciente cancele una cita médica.")],
}


def completed(iid):
    return completar_requerimientos_explicitos_faltantes(copy.deepcopy(RAW[iid]), copy.deepcopy(ISSUES[iid]))


def text(item):
    return " ".join(str(item.get(key, "")) for key in ("nombre", "descripcion_formal", "origen")).casefold()


class SemanticTraceabilityTests(unittest.TestCase):
    def test_raw_central_can_be_incomplete_and_explicit_sources_are_recovered(self):
        self.assertEqual(len(RAW[6]), 3)
        self.assertEqual(len(completed(6)), 6)

    def test_hu006_recovers_explicit_rf_and_rnf(self):
        result = completed(6)
        self.assertEqual([item["tipo"] for item in result].count("RF"), 4)
        self.assertEqual([item["tipo"] for item in result].count("RNF"), 2)
        self.assertTrue(any("tres segundos" in text(item) for item in result))
        self.assertTrue(any("tiempo real" in text(item) for item in result))

    def test_hu007_recovers_editing_without_duplicate_registration(self):
        result = completed(7)
        self.assertTrue(any("editar" in text(item) for item in result))
        self.assertEqual(sum("registr" in text(item) and "información" in text(item) for item in result), 1)
        self.assertEqual(len(result), 4)

    def test_hu008_deduplicates_agenda_and_daily_appointments(self):
        result = completed(8)
        self.assertEqual(sum("citas del día" in text(item) for item in result), 1)
        self.assertEqual(sum("tiempo real" in text(item) for item in result), 1)

    def test_hu009_recovers_statistics_and_printing_without_duplicate_export(self):
        result = completed(9)
        self.assertTrue(any("estadísticas" in text(item) for item in result))
        self.assertTrue(any("imprimir" in text(item) for item in result))
        self.assertEqual(sum("export" in text(item) and "pdf" in text(item) for item in result), 1)
        self.assertEqual(len(result), 5)

    def test_hu010_recovers_24_hour_rule_as_rf_and_merges_evidence(self):
        result = completed(10)
        self.assertEqual(len(result), 2)
        rule = next(item for item in result if "24 horas" in text(item))
        self.assertEqual(rule["tipo"], "RF")
        cancellation = next(item for item in result if item is not rule)
        self.assertIn("Cancelar una cita médica", cancellation["origen"])
        self.assertIn("puede cancelar", cancellation["origen"])

    def test_every_requirement_has_explicit_provenance(self):
        for iid in ISSUES:
            for item in completed(iid):
                self.assertTrue(item.get("procedencia", "").startswith("explícita —"), (iid, item))

    def test_placeholders_and_checkboxes_do_not_become_requirements(self):
        issue = {
            "funcionalidad": "Ninguna", "criterios_aceptacion": ["Sí", "No"],
            "restricciones": [], "observaciones": "[x] Sí\n[ ] No", "prioridad": None,
        }
        self.assertEqual(completar_requerimientos_explicitos_faltantes([], issue), [])

    def test_equivalent_functionality_and_criterion_share_one_requirement(self):
        issue = {
            "funcionalidad": "Generar reportes", "criterios_aceptacion": ["Permitir la generación de reportes."],
            "restricciones": [], "observaciones": [], "prioridad": "Media",
        }
        result = completar_requerimientos_explicitos_faltantes([], issue)
        self.assertEqual(len(result), 1)
        self.assertIn("Generar reportes", result[0]["origen"])
        self.assertIn("generación de reportes", result[0]["origen"])

    def test_other_domains_use_structural_not_medical_rules(self):
        education = completar_requerimientos_explicitos_faltantes([], {
            "funcionalidad": "Editar una matrícula", "criterios_aceptacion": [],
            "restricciones": ["Responder en menos de dos segundos."], "observaciones": [],
        })
        self.assertEqual({item["tipo"] for item in education}, {"RF", "RNF"})
        self.assertTrue(any("dos segundos" in text(item) for item in education))

        commercial = completar_requerimientos_explicitos_faltantes([], {
            "funcionalidad": "Actualizar inventario", "criterios_aceptacion": ["Imprimir una factura."],
            "restricciones": [], "observaciones": "El inventario deberá actualizarse en tiempo real.",
        })
        self.assertEqual(sum(item["tipo"] == "RF" for item in commercial), 2)
        self.assertEqual(sum(item["tipo"] == "RNF" for item in commercial), 1)

        human_resources = completar_requerimientos_explicitos_faltantes([], {
            "funcionalidad": "Aprobar vacaciones", "criterios_aceptacion": ["Impedir aprobar vacaciones sin saldo disponible."],
            "restricciones": [], "observaciones": [],
        })
        rule = next(item for item in human_resources if "impedir" in text(item))
        self.assertEqual(rule["tipo"], "RF")

        timed_human_resources = completar_requerimientos_explicitos_faltantes([], {
            "funcionalidad": "Consultar solicitudes", "criterios_aceptacion": [],
            "restricciones": [], "observaciones": "La consulta debe responder en un máximo de cinco segundos.",
        })
        self.assertEqual(sum(item["tipo"] == "RF" for item in timed_human_resources), 1)
        self.assertEqual(sum(item["tipo"] == "RNF" for item in timed_human_resources), 1)
        self.assertTrue(any("cinco segundos" in text(item) for item in timed_human_resources))

    def test_descriptive_observation_without_action_is_not_formalized(self):
        result = completar_requerimientos_explicitos_faltantes([], {
            "funcionalidad": "Consultar registros", "criterios_aceptacion": [],
            "restricciones": [], "observaciones": "Coordinar posteriormente con el área responsable.",
        })
        self.assertEqual(len(result), 1)

    def test_central_init_structure_is_not_changed(self):
        central = {"agente": "central", "resultados": [{"issue_iid": 6, "requerimientos": copy.deepcopy(RAW[6])}]}
        snapshot = copy.deepcopy(central)
        completar_requerimientos_explicitos_faltantes(copy.deepcopy(central["resultados"][0]["requerimientos"]), ISSUES[6])
        self.assertEqual(central, snapshot)

    def test_completion_has_no_external_provider_calls(self):
        source = inspect.getsource(completar_requerimientos_explicitos_faltantes)
        for forbidden in ("invoke(", "analizar_calidad", "analizar_seguridad", "gitlab", "ollama", "groq"):
            self.assertNotIn(forbidden, source.casefold())


if __name__ == "__main__":
    unittest.main()
