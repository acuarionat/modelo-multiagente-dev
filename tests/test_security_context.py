import copy
import unittest

from core.graph import _adjuntar_evidencia_seguridad


class SecurityContextTests(unittest.TestCase):
    def setUp(self):
        self.security_006 = {
            "descripcion": "Datos personales del paciente.",
            "maneja_datos_sensibles": "Sí",
            "tipos_datos_sensibles": ["Nombre", "Documento de identidad"],
            "autenticacion": "Usuario y contraseña",
            "autorizacion_roles": "Rol Paciente",
            "auditoria": "Registro de consultas",
        }
        self.security_007 = {
            "descripcion": "Datos administrativos.",
            "maneja_datos_sensibles": "No",
            "tipos_datos_sensibles": [],
            "autenticacion": "Cuenta administrativa",
            "autorizacion_roles": "Rol Administrador",
            "auditoria": "Registro de altas",
        }
        self.issues = [
            {"id": "7", "seguridad": self.security_007},
            {"id": "6", "seguridad": self.security_006},
            {"id": "8"},
        ]

    def test_each_story_receives_only_its_security_evidence_by_iid(self):
        parsed = {"resultados": [
            {"issue_iid": 6, "historia_id": "HU-006"},
            {"issue_iid": 7, "historia_id": "HU-007"},
        ]}
        _adjuntar_evidencia_seguridad(parsed, self.issues)
        hu006, hu007 = parsed["resultados"]
        self.assertEqual(hu006["evidencia_seguridad"], self.security_006)
        self.assertNotEqual(hu006["evidencia_seguridad"], self.security_007)
        self.assertEqual(hu007["evidencia_seguridad"], self.security_007)

    def test_auth_roles_audit_and_sensitive_data_are_preserved(self):
        parsed = {"resultados": [{"issue_iid": "6"}]}
        _adjuntar_evidencia_seguridad(parsed, self.issues)
        evidence = parsed["resultados"][0]["evidencia_seguridad"]
        self.assertEqual(evidence["autenticacion"], "Usuario y contraseña")
        self.assertEqual(evidence["autorizacion_roles"], "Rol Paciente")
        self.assertEqual(evidence["auditoria"], "Registro de consultas")
        self.assertEqual(evidence["maneja_datos_sensibles"], "Sí")
        self.assertEqual(evidence["tipos_datos_sensibles"], ["Nombre", "Documento de identidad"])

    def test_missing_security_uses_safe_empty_dictionary(self):
        parsed = {"resultados": [{"issue_iid": 8, "historia_id": "HU-008"}]}
        _adjuntar_evidencia_seguridad(parsed, self.issues)
        self.assertEqual(parsed["resultados"][0]["evidencia_seguridad"], {})

    def test_missing_issue_iid_is_not_associated_arbitrarily(self):
        parsed = {"resultados": [{"historia_id": "HU-SIN-ID"}]}
        _adjuntar_evidencia_seguridad(parsed, self.issues)
        self.assertEqual(parsed["resultados"][0]["evidencia_seguridad"], {})

    def test_different_order_does_not_change_association(self):
        parsed = {"resultados": [
            {"issue_iid": 7, "historia_id": "HU-007"},
            {"issue_iid": 6, "historia_id": "HU-006"},
        ]}
        _adjuntar_evidencia_seguridad(parsed, list(reversed(self.issues)))
        self.assertEqual(parsed["resultados"][0]["evidencia_seguridad"], self.security_007)
        self.assertEqual(parsed["resultados"][1]["evidencia_seguridad"], self.security_006)

    def test_central_response_is_identical_except_for_new_field(self):
        parsed = {"agente": "central", "milestone": "Sprint", "resultados": [{
            "issue_iid": 6,
            "historia_id": "HU-006",
            "actor": "Paciente",
            "objetivo": "Consultar horarios",
            "requerimientos": [{"temp_id": "RF-TEMP-01", "nombre": "Consultar"}],
            "restricciones": ["Solo horarios disponibles"],
            "recomendaciones": ["Sin cambios"],
        }]}
        original = copy.deepcopy(parsed)
        _adjuntar_evidencia_seguridad(parsed, self.issues)
        evidence = parsed["resultados"][0].pop("evidencia_seguridad")
        self.assertEqual(evidence, self.security_006)
        self.assertEqual(parsed, original)


if __name__ == "__main__":
    unittest.main()
