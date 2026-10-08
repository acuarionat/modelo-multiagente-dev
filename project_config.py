"""Persistencia y versionado de la configuración general del proyecto."""
import json
import os

from database.connection import conectar

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "database.db")
FIELDS = ("name", "gitlab_url", "gitlab_project", "gitlab_token")


def _connect():
    connection = conectar(DB_PATH)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS project_configuration (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            payload TEXT NOT NULL,
            version_minor INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return connection


def load_project_config():
    with _connect() as connection:
        row = connection.execute("SELECT payload, version_minor FROM project_configuration WHERE id = 1").fetchone()
    if not row:
        return None
    config = json.loads(row[0])
    config["context_version"] = f"v1.{row[1]}"
    return config


def save_project_config(values):
    clean = {field: str(values.get(field, "")).strip() for field in FIELDS}
    current = load_project_config()
    old_values = {field: current.get(field, "") for field in FIELDS} if current else None
    minor = 0 if current is None else int(current["context_version"].split(".")[1])
    if old_values is not None and old_values != clean:
        minor += 1
    with _connect() as connection:
        connection.execute("""
            INSERT INTO project_configuration (id, payload, version_minor, updated_at)
            VALUES (1, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                version_minor=excluded.version_minor, updated_at=CURRENT_TIMESTAMP
        """, (json.dumps(clean, ensure_ascii=False), minor))
    clean["context_version"] = f"v1.{minor}"
    return clean
