"""Diagnóstico controlado y de solo lectura de la conexión con GitLab.

Este archivo no modifica la configuración, el adaptador ni recursos de GitLab.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

import gitlab
from dotenv import load_dotenv
import requests


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DB_PATH = ROOT / "database" / "database.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _redact(value: Any, *secrets: str | None) -> str:
    text = str(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<REDACTED>")
    return text


def _status_http(exc: BaseException) -> Any:
    for candidate in (exc, exc.__cause__, exc.__context__):
        if candidate is None:
            continue
        response_code = getattr(candidate, "response_code", None)
        if response_code is not None:
            return response_code
        response = getattr(candidate, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if status_code is not None:
                return status_code
    return None


def _report_error(prefix: str, exc: BaseException, *secrets: str | None) -> None:
    print(f"{prefix}_ESTADO: ERROR")
    print(f"{prefix}_EXCEPCION_TIPO: {type(exc).__module__}.{type(exc).__name__}")
    print(f"{prefix}_EXCEPCION_MENSAJE: {_redact(exc, *secrets)}")
    print(f"{prefix}_STATUS_HTTP: {_status_http(exc)}")


def _load_saved_config_readonly() -> dict[str, Any] | None:
    if not DB_PATH.is_file():
        return None
    connection = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'project_configuration'"
        ).fetchone()
        if table is None:
            return None
        row = connection.execute(
            "SELECT payload FROM project_configuration WHERE id = 1"
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        connection.close()


def main() -> int:
    os.chdir(ROOT)
    dotenv_loaded = load_dotenv()
    env_url = os.getenv("GITLAB_URL")
    env_token = os.getenv("GITLAB_TOKEN")
    env_project_id = os.getenv("GITLAB_PROJECT_ID")

    print(f"ENV_FILE_PRESENTE: {ENV_PATH.is_file()}")
    print(f"LOAD_DOTENV_RESULT: {dotenv_loaded}")
    print(f"GITLAB_URL: {env_url}")
    print(f"GITLAB_TOKEN_PRESENTE: {bool(env_token)}")
    print(f"PROJECT_ID_PRESENTE: {bool(env_project_id)}")

    if not env_url:
        print("DIAGNOSTICO_ABORTADO: falta GITLAB_URL")
        return 2

    try:
        response = requests.get(env_url, timeout=15)
        print("REQUESTS_ESTADO: OK")
        print(f"REQUESTS_STATUS_HTTP: {response.status_code}")
    except Exception as exc:
        _report_error("REQUESTS", exc, env_token)
        return 1

    if not env_token:
        print("PYTHON_GITLAB_ESTADO: NO_EJECUTADO_TOKEN_AUSENTE")
        return 2

    try:
        gl = gitlab.Gitlab(env_url, private_token=env_token, timeout=15)
        gl.auth()
        print("PYTHON_GITLAB_ESTADO: OK")
        print("PYTHON_GITLAB_AUTENTICACION: OK")
        print(f"PYTHON_GITLAB_USUARIO: {gl.user.username}")
    except Exception as exc:
        _report_error("PYTHON_GITLAB", exc, env_token)
        return 1

    saved_config = _load_saved_config_readonly()
    app_url = (saved_config or {}).get("gitlab_url", env_url)
    app_token = (saved_config or {}).get("gitlab_token", env_token)
    app_project_id = (saved_config or {}).get("gitlab_project", env_project_id)
    print(f"APP_CONFIG_FUENTE: {'SQLITE' if saved_config else 'ENV'}")
    print(f"APP_GITLAB_URL: {app_url}")
    print(f"APP_GITLAB_TOKEN_PRESENTE: {bool(app_token)}")
    print(f"APP_PROJECT_ID_PRESENTE: {bool(app_project_id)}")
    print(f"APP_Y_ENV_URL_EQUIVALENTES: {app_url == env_url}")
    print(f"APP_Y_ENV_TOKEN_EQUIVALENTES: {app_token == env_token}")
    print(f"APP_Y_ENV_PROJECT_ID_EQUIVALENTES: {str(app_project_id) == str(env_project_id)}")

    if not all((app_url, app_token, app_project_id)):
        print("GITLAB_ADAPTER_ESTADO: NO_EJECUTADO_CONFIGURACION_INCOMPLETA")
        return 2

    from integrations.gitlab_adapter import GitLabAdapter

    try:
        adapter = GitLabAdapter(app_url, app_token, app_project_id)
        print("GITLAB_ADAPTER_ESTADO: OK")
        print("GITLAB_ADAPTER_CONEXION: OK")
        print("GITLAB_ADAPTER_AUTENTICACION: OK")
        print(f"GITLAB_ADAPTER_PROJECT_ID: {adapter.project_id}")
        print(f"GITLAB_ADAPTER_PROYECTO: {adapter.project.name}")
    except Exception as exc:
        _report_error("GITLAB_ADAPTER", exc, app_token, env_token)
        return 1

    for attempt in range(1, 4):
        prefix = f"CONEXION_{attempt}"
        try:
            repeated_adapter = GitLabAdapter(app_url, app_token, app_project_id)
            print(f"{prefix}: OK")
            print(f"{prefix}_PROYECTO_RECUPERADO: {bool(repeated_adapter.project)}")
        except Exception as exc:
            _report_error(prefix, exc, app_token, env_token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
