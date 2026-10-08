"""
Recuperación de Issues PRU-xxx desde GitLab para la etapa de Pruebas, y
publicación de retroalimentación y de la Matriz de Trazabilidad — Etapa
Pruebas (TRZ-004). Solo obtiene, mapea y publica; no valida, no calcula
métricas ni construye la matriz: eso corresponde a
core/testing_validation.py, core/testing_traceability.py y
core/testing_metrics.py.
"""

import logging

from integrations.gitlab_adapter import GitLabAdapter
from integrations.testing_issue_mapper import mapear_issue_pruebas
from integrations.testing_traceability_issue_mapper import (
    TESTING_TRACEABILITY_COLUMNS,
    construir_markdown_matriz_trazabilidad_pruebas,
    mapear_matriz_trazabilidad_pruebas,
)
from core.batch_contract import construir_etiquetas_resultado_evaluacion_tecnica
from core.utils import extraer_porcentaje
from database.repository import obtener_version_matriz

logger = logging.getLogger(__name__)

TRZ_004_TITULO = "TRZ-004 - Matriz de Trazabilidad - Etapa Pruebas"


def obtener_issues_pruebas(project_id, milestone_title="Pruebas"):
    """Obtiene TODOS los Issues PRU-xxx abiertos de GitLab y los estructura con testing_issue_mapper
    (cada uno conserva sus etiquetas; solo se analizan los Pendiente o Requiere modificación)."""
    adapter = GitLabAdapter(project_id=project_id)
    issues = adapter.listar_issues_abiertos(milestone_title=milestone_title)
    return [mapear_issue_pruebas(issue) for issue in issues]


def construir_comentario_pruebas(testing_summary: dict) -> str:
    """
    Construye el comentario compacto de retroalimentación operativa para
    un Issue de Pruebas a partir de testing_summary (salida de
    nodo_testing_central_final). No repite las métricas completas
    MC-06/MC-07/MS-08/MS-09: solo el estado orientativo, las conclusiones
    de Calidad/Seguridad y los hallazgos ya clasificados por el Evaluador
    de Pruebas.
    """
    prueba_id = testing_summary.get("prueba_id", "")
    estado = testing_summary.get("estado_orientativo", "")
    calidad = testing_summary.get("calidad") or {}
    seguridad = testing_summary.get("seguridad") or {}

    def _textos(campo):
        valores = testing_summary.get(campo)
        if not isinstance(valores, list):
            return []
        return [texto.strip() for texto in valores if isinstance(texto, str) and texto.strip()]

    correcciones = _textos("correcciones_necesarias")
    precisiones = _textos("precisiones")
    oportunidades = _textos("oportunidades_mejora")

    lineas = [
        f"Resultado del análisis de Pruebas — {prueba_id}",
        "",
        f"Estado orientativo: {estado}",
        f"MC-06 Corrección Funcional: {extraer_porcentaje((calidad.get('mc07') or {}).get('valor'))}",
        f"MC-07 Corrección de Fallos: {extraer_porcentaje((calidad.get('mc08') or {}).get('valor'))}",
        f"MS-08 Cobertura de Verificación de Controles: {extraer_porcentaje((seguridad.get('ms08') or {}).get('valor'))}",
        f"MS-09 Pruebas de Seguridad Satisfactorias: {extraer_porcentaje((seguridad.get('ms09') or {}).get('valor'))}",
        "",
        "Correcciones necesarias:",
        *([f"- {item}" for item in correcciones] if correcciones else ["- Ninguna."]),
        "",
        "Precisiones:",
        *([f"- {item}" for item in precisiones] if precisiones else ["- Ninguna."]),
        "",
        "Oportunidades de mejora:",
        *([f"- {item}" for item in oportunidades] if oportunidades else ["- Ninguna."]),
        "",
        "Próxima acción:",
        (
            "Actualizar el Issue de Pruebas con las correcciones necesarias y volver a marcarlo como Pendiente."
            if correcciones else
            "El Issue de Pruebas queda marcado como Revisado y puede continuar con la siguiente etapa."
        ),
        "",
        "Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.",
    ]

    return "\n".join(lineas) + "\n"


def publicar_comentario_pruebas(project_id, issue_iid, testing_summary: dict, adapter=None):
    """Publica en GitLab el comentario de retroalimentación operativa de Pruebas."""
    if not testing_summary:
        raise ValueError("No existe resumen de Pruebas para publicar.")

    if testing_summary.get("estado_orientativo") == "ERROR":
        raise ValueError(
            "No se publica comentario de evaluación cuando existe error técnico."
        )

    comentario = construir_comentario_pruebas(testing_summary)

    adapter = adapter or GitLabAdapter(project_id=project_id)
    nota = adapter.agregar_comentario(issue_iid, comentario)
    issue = adapter.obtener_issue(issue_iid)
    nuevas_etiquetas = construir_etiquetas_resultado_evaluacion_tecnica(
        issue.labels, testing_summary.get("estado_orientativo"),
    )
    adapter.actualizar_etiquetas(issue_iid, nuevas_etiquetas)
    return nota


def construir_comentario_referencias_invalidas_pruebas(prueba_id: str, referencias_invalidas: list) -> str:
    """Comentario de aviso para un Issue de Pruebas que NO fue analizado por referenciar
    codificaciones inexistentes en la matriz de trazabilidad de Codificación heredada (TRZ-003)."""
    referencias = [str(ref).strip() for ref in (referencias_invalidas or []) if str(ref).strip()]
    lineas = [
        f"Revisar — Trazabilidad incompleta ({prueba_id})",
        "",
        "Este Issue de Pruebas no fue analizado porque referencia codificaciones "
        "inexistentes en la matriz de trazabilidad de Codificación heredada (TRZ-003).",
        "",
        "Codificaciones inexistentes:",
        *([f"- {item}" for item in referencias] if referencias else ["- No especificadas."]),
        "",
        "Próxima acción:",
        "Corregir las referencias del Issue de Pruebas (o actualizar la matriz de "
        "trazabilidad de Codificación) y volver a ejecutar el análisis.",
        "",
        "Evaluación asistida para apoyar el control, seguimiento y trazabilidad. La decisión final corresponde al responsable del proyecto.",
    ]
    return "\n".join(lineas) + "\n"


def publicar_aviso_referencias_invalidas_pruebas(project_id, issue_iid, prueba_id, referencias_invalidas, adapter=None):
    """Publica en GitLab el aviso de un Issue de Pruebas bloqueado por codificaciones
    inexistentes: comentario + etiqueta 'Requiere modificación' (reutiliza el ciclo de
    etiquetas de evaluación técnica con estado CORREGIR)."""
    comentario = construir_comentario_referencias_invalidas_pruebas(prueba_id, referencias_invalidas)
    adapter = adapter or GitLabAdapter(project_id=project_id)
    nota = adapter.agregar_comentario(issue_iid, comentario)
    issue = adapter.obtener_issue(issue_iid)
    nuevas_etiquetas = construir_etiquetas_resultado_evaluacion_tecnica(issue.labels, "CORREGIR")
    adapter.actualizar_etiquetas(issue_iid, nuevas_etiquetas)
    return nota


def obtener_issue_matriz_trazabilidad_pruebas(project_id):
    """Recupera TRZ-004 y sus filas con el contrato oficial de 18 columnas."""
    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_004_TITULO)
    if issue is None:
        return None, None
    return issue, mapear_matriz_trazabilidad_pruebas(issue.description or "")


def crear_o_actualizar_issue_matriz_trazabilidad_pruebas(project_id, filas_matriz, metadata=None):
    """Valida y persiste pasivamente en TRZ-004 las filas finales de Pruebas."""
    if not filas_matriz:
        logger.warning("No hay filas de matriz de Pruebas para publicar TRZ-004.")
        return None

    for indice, fila in enumerate(filas_matriz, start=1):
        columnas_fila = set(fila)
        columnas_esperadas = set(TESTING_TRACEABILITY_COLUMNS)
        if not columnas_esperadas.issubset(columnas_fila):
            faltantes = columnas_esperadas - columnas_fila
            raise ValueError(f"La fila {indice} de TRZ-004 no tiene las columnas obligatorias: {faltantes}.")

    contenido = construir_markdown_matriz_trazabilidad_pruebas(filas_matriz)
    recuperadas = mapear_matriz_trazabilidad_pruebas(contenido)

    if len(recuperadas) != len(filas_matriz):
        raise ValueError("El round-trip de TRZ-004 alteró la cantidad de filas.")
    for indice, (original, recuperada) in enumerate(zip(filas_matriz, recuperadas), start=1):
        for columna in TESTING_TRACEABILITY_COLUMNS:
            if recuperada[columna] != str(original.get(columna, "")):
                raise ValueError(
                    f"El round-trip de TRZ-004 alteró la fila {indice}, columna {columna!r}."
                )

    version = obtener_version_matriz("pruebas", filas_matriz, 4)
    detalle = (
        f"_Ejecución: {(metadata or {}).get('execution_id', 'No informado')} — "
        f"Versión: {version}._\n\n"
    )
    contenido = contenido.replace("## Matriz de trazabilidad", detalle + "## Matriz de trazabilidad", 1)

    adapter = GitLabAdapter(project_id=project_id)
    issue = adapter.buscar_issue_por_titulo(TRZ_004_TITULO)
    if issue is None:
        return adapter.crear_issue(TRZ_004_TITULO, contenido)
    return adapter.actualizar_descripcion_issue(issue.iid, contenido)
