"""Genera artefactos locales desde un fixture; no invoca agentes ni servicios."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.utils import generar_artefactos_atomicos
from tests.test_document_artifacts import _fixture_batch


def main():
    execution_id = datetime.now().strftime("document-fixture-%Y%m%d-%H%M%S-%f")
    output_dir = Path(os.getenv("TEMP", "C:/tmp")) / execution_id
    summary = {
        "execution_id": execution_id,
        "estado_tecnico": "fixture_local",
        "resultados": [
            {
                "issue_iid": item["issue_iid"],
                "quality_index": item["quality"]["indice"],
                "security_index": item["security"]["indice"],
                "veredicto": item["evaluation"]["veredicto"],
            }
            for item in _fixture_batch()["issues"]
        ],
        "external_calls": 0,
        "git_operations": 0,
    }
    model, paths, summary_path = generar_artefactos_atomicos(
        _fixture_batch(), output_dir, execution_id, summary,
        expected_issue_ids=[6, 7, 8, 9, 10], expected_rf=17, expected_rnf=3,
    )
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    print(json.dumps({
        "execution_id": execution_id,
        "output_dir": str(output_dir),
        "paths": paths,
        "summary": str(summary_path),
        "validation": persisted.get("validacion_documental"),
        "documentary_audit": persisted.get("auditoria_documental"),
        "issues": len(model["issues"]),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
