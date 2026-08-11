"""
Test de diagnóstico para visualizar cómo el mapper recupera
las Historias de Usuario desde GitLab.

NO ejecuta LLM.
NO ejecuta agentes.
NO genera métricas.
NO modifica Issues.
"""

import json
from pprint import pprint

from integrations.gitlab_adapter import GitLabAdapter

# IMPORTANTE:
# Sustituir este import únicamente por la función REAL que actualmente
# usa el flujo de Recepción de Requerimientos para mapear Issues.
from integrations.issue_mapper import mapear_issue


PROJECT_ID = "TU_PROJECT_ID"
MILESTONE = "Recepción de Requerimientos"


def imprimir_separador(titulo: str):
    print("\n")
    print("=" * 100)
    print(titulo)
    print("=" * 100)


def main():
    imprimir_separador("1. CONEXIÓN A GITLAB")

    adapter = GitLabAdapter(project_id=PROJECT_ID)

    print(f"Proyecto conectado: {PROJECT_ID}")
    print(f"Milestone buscado: {MILESTONE}")

    # Usar aquí el método REAL que tu aplicación ya utiliza
    # para recuperar Issues por milestone.
    issues = adapter.obtener_issues_por_milestone(MILESTONE)

    print(f"Issues encontrados: {len(issues)}")

    resultados = []

    for indice, issue in enumerate(issues, start=1):

        imprimir_separador(
            f"2.{indice} ISSUE GITLAB #{issue.iid}"
        )

        print(f"IID: {issue.iid}")
        print(f"Título: {issue.title}")

        print("\n--- MARKDOWN ORIGINAL ---\n")
        print(issue.description or "[SIN DESCRIPCIÓN]")

        imprimir_separador(
            f"3.{indice} RESULTADO DEL MAPPER"
        )

        try:
            hu = mapear_issue(issue)

        except Exception as exc:
            print("❌ ERROR DURANTE EL MAPEO")
            print(f"Tipo: {type(exc).__name__}")
            print(f"Detalle: {exc}")
            continue

        pprint(hu, sort_dicts=False)

        imprimir_separador(
            f"4.{indice} CAMPOS IMPORTANTES RECUPERADOS"
        )

        if isinstance(hu, dict):

            print(f"issue_iid : {hu.get('issue_iid')}")
            print(f"titulo    : {hu.get('titulo')}")

            print("\nACTOR / ACCIÓN / OBJETIVO")
            print(f"Como   : {hu.get('como') or hu.get('actor')}")
            print(f"Quiero : {hu.get('quiero') or hu.get('accion')}")
            print(f"Para   : {hu.get('para') or hu.get('objetivo')}")

            print("\nCRITERIOS DE ACEPTACIÓN")
            pprint(
                hu.get("criterios_aceptacion")
                or hu.get("criterios")
                or []
            )

            print("\nRESTRICCIONES")
            pprint(
                hu.get("restricciones") or []
            )

            print("\nSEGURIDAD")
            pprint(
                hu.get("seguridad") or {}
            )

            print("\nOBSERVACIONES")
            pprint(
                hu.get("observaciones")
            )

        resultados.append(hu)

    imprimir_separador(
        "5. JSON FINAL QUE PRODUJO EL MAPPER"
    )

    print(
        json.dumps(
            resultados,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    imprimir_separador("FIN DEL TEST")

    print(
        f"Historias recuperadas correctamente: "
        f"{len(resultados)} / {len(issues)}"
    )


if __name__ == "__main__":
    main()