import project_config


def test_context_version_only_increments_when_values_change(tmp_path, monkeypatch):
    monkeypatch.setattr(project_config, "DB_PATH", str(tmp_path / "config.db"))
    values = {field: f"value-{field}" for field in project_config.FIELDS}

    assert project_config.save_project_config(values)["context_version"] == "v1.0"
    assert project_config.save_project_config(values)["context_version"] == "v1.0"

    values["scope"] = "new scope"
    assert project_config.save_project_config(values)["context_version"] == "v1.1"
    assert project_config.load_project_config()["scope"] == "new scope"


def test_milestones_are_not_duplicated():
    from integrations.gitlab_adapter import GitLabAdapter

    class Milestones:
        def __init__(self):
            self.items = [type("M", (), {"title": "Diseño"})()]
            self.created = []

        def list(self, all=False):
            return self.items

        def create(self, data):
            self.created.append(data)

    adapter = object.__new__(GitLabAdapter)
    adapter.project = type("Project", (), {"milestones": Milestones()})()
    result = adapter.asegurar_hitos(["Diseño", "Pruebas"])

    assert result == {"Diseño": "reutilizado", "Pruebas": "creado"}
    assert adapter.project.milestones.created == [{"title": "Pruebas"}]
