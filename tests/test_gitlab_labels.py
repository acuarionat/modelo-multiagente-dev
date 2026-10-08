import unittest

from integrations.gitlab_adapter import GitLabAdapter, es_issue_pendiente, etiquetas_son_analizables


class GitLabLabelWorkflowTests(unittest.TestCase):
    def test_only_pending_non_final_issues_are_eligible(self):
        issue = lambda labels: type("Issue", (), {"labels": labels})()

        self.assertTrue(es_issue_pendiente(issue(["Historia de Usuario", "Pendiente"])))
        self.assertFalse(es_issue_pendiente(issue(["Historia de Usuario", "Revisada"])))
        self.assertFalse(es_issue_pendiente(issue(["Historia de Usuario", "Analizada"])))
        self.assertTrue(es_issue_pendiente(issue(["Historia de Usuario", "Requiere modificación"])))
        self.assertFalse(es_issue_pendiente(issue(["Pendiente", "Revisada"])))

    def test_labels_decide_which_listed_issues_are_analyzed(self):
        self.assertTrue(etiquetas_son_analizables(["Pendiente"]))
        self.assertTrue(etiquetas_son_analizables(["Requiere modificación"]))
        self.assertFalse(etiquetas_son_analizables(["Revisada"]))
        self.assertFalse(etiquetas_son_analizables([]))
        self.assertFalse(etiquetas_son_analizables(None))

    def test_adapter_lists_pending_and_rework_but_not_reviewed(self):
        issue = lambda iid, labels: type("Issue", (), {"iid": iid, "labels": labels})()
        available = [
            issue(1, ["Pendiente"]),
            issue(2, ["Requiere modificación"]),
            issue(3, ["Revisada"]),
        ]
        adapter = object.__new__(GitLabAdapter)
        adapter.listar_issues_abiertos = lambda milestone_title=None: available

        selected = adapter.listar_issues_pendientes("Sprint 1")

        self.assertEqual([item.iid for item in selected], [1, 2])

    def test_adapter_updates_issue_labels_and_creates_missing_workflow_labels(self):
        class Labels:
            def __init__(self):
                self.items = [type("Label", (), {"name": "Pendiente"})()]
                self.created = []

            def list(self, all=False):
                return self.items

            def create(self, data):
                self.created.append(data)

        class Issue:
            def __init__(self):
                self.labels = ["Historia de Usuario", "Pendiente"]
                self.saved = False

            def save(self):
                self.saved = True

        issue = Issue()
        adapter = object.__new__(GitLabAdapter)
        adapter._workflow_labels_ready = False
        adapter.project = type("Project", (), {
            "labels": Labels(),
            "issues": type("Issues", (), {"get": lambda self, iid: issue})(),
        })()

        adapter.actualizar_etiquetas(17, ["Historia de Usuario", "Revisada"])

        self.assertEqual(issue.labels, ["Historia de Usuario", "Revisada"])
        self.assertTrue(issue.saved)
        self.assertEqual(
            {item["name"] for item in adapter.project.labels.created},
            {"Revisada", "Requiere modificación"},
        )


if __name__ == "__main__":
    unittest.main()