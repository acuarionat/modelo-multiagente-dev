"""
Componentes visuales comunes para la interfaz Streamlit.

Extraídos del patrón de Recepción de Requerimientos para que Diseño
(y futuras etapas) reutilicen la misma jerarquía visual.

Solo presentación: no recalcula métricas ni modifica datos.
"""

import re
from html import escape
from types import SimpleNamespace

import streamlit as st

from core.dashboard_ui import clasificar_estado_flujo
from core.ui_theme import render_section_title
from integrations.gitlab_adapter import etiquetas_son_analizables


# ---------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------

def _lista_ui(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _texto_hallazgo_ui(item):
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for field in ("recomendacion", "precision", "sugerencia", "funcion", "descripcion", "texto"):
            value = str(item.get(field) or "").strip()
            if value:
                return value
    return ""


# ---------------------------------------------------------
# Navegación interna de una etapa
# ---------------------------------------------------------

# Cada fase: (título completo del panel, nombre corto para el botón, ícono del botón).
_FASE_ENTRADAS = ("Revisión de entradas", "entradas", ":material/inventory_2:")
_FASE_ANALISIS = ("Ejecución del análisis", "análisis", ":material/play_circle:")
_FASE_RESULTADOS = ("Resultados y artefactos", "resultados", ":material/fact_check:")
_FASE_REPOSITORIO = ("Información técnica del repositorio", "repositorio", ":material/account_tree:")


def _crear_flujo_de_fases(
    stage_prefix: str,
    fases: tuple,
    indice_resultados: int,
    resultados_presentes: bool,
    descripcion: str,
):
    """Barra de fases (botones «Ver / Ocultar») y un panel por cada fase.

    La fase visible se rastrea con un único índice en `st.session_state`
    (`<stage_prefix>_active_step`; `None` = todas ocultas), de modo que
    `render_next_phase_button` avanza de fase por programación. Presionar el
    botón de la fase visible la oculta; presionar otro la muestra.

    El contenido de todas las fases se sigue generando en cada ejecución (la
    lógica de cada etapa no cambia): las fases ocultas solo se ocultan con CSS
    mediante la clase de su `key` (`phase_off_*`).

    Si ya hay resultados, la primera vez se abre la fase de resultados (igual
    que antes); desde que la persona elige una fase se respeta su elección.
    """
    step_key = f"{stage_prefix}_active_step"
    manual_key = f"{stage_prefix}_step_manual"
    if step_key not in st.session_state:
        st.session_state[step_key] = indice_resultados if resultados_presentes else 0
    elif resultados_presentes and not st.session_state.get(manual_key):
        st.session_state[step_key] = indice_resultados
    if not resultados_presentes:
        st.session_state[manual_key] = False
    active_step = st.session_state[step_key]

    render_section_title(
        "Fases de la etapa",
        eyebrow="Paso a paso",
        description=descripcion,
        icon="fases",
    )

    with st.container(key=f"phase_bar_{stage_prefix}"):
        columnas = st.columns(len(fases))
        for indice, (columna, (titulo, corto, icono)) in enumerate(zip(columnas, fases)):
            abierta = active_step == indice
            if columna.button(
                f"{'Ocultar' if abierta else 'Ver'} {corto}",
                key=f"{stage_prefix}_phase_btn_{indice}",
                icon=icono,
                help=f"{chr(65 + indice)}. {titulo}",
                type="primary" if abierta else "secondary",
                width="stretch",
            ):
                st.session_state[step_key] = None if abierta else indice
                st.session_state[manual_key] = True
                st.rerun()

    paneles = []
    for indice, (titulo, _corto, _icono) in enumerate(fases):
        estado = "on" if active_step == indice else "off"
        panel = st.container(key=f"phase_{estado}_{stage_prefix}_{indice}")
        panel.markdown(
            '<div class="phase-panel-head">'
            f'<span class="phase-panel-letter">{chr(65 + indice)}</span>'
            f'<span class="phase-panel-title">{escape(titulo)}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        paneles.append(panel)
    return (*paneles, step_key)


def create_stage_step_panels(stage_prefix: str, resultados_presentes: bool = False):
    """Crea las tres fases comunes (entradas, análisis, resultados) sin alterar su contenido."""
    return _crear_flujo_de_fases(
        stage_prefix,
        (_FASE_ENTRADAS, _FASE_ANALISIS, _FASE_RESULTADOS),
        indice_resultados=2,
        resultados_presentes=resultados_presentes,
        descripcion="Revisión de entradas, ejecución del análisis y resultados.",
    )


def create_coding_step_panels(stage_prefix: str, resultados_presentes: bool = False):
    """Crea las cuatro fases propias de la etapa de Codificación.

    Ver `_crear_flujo_de_fases` para el manejo de la fase visible.
    """
    return _crear_flujo_de_fases(
        stage_prefix,
        (
            ("Entrada de codificación", "entradas", _FASE_ENTRADAS[2]),
            _FASE_REPOSITORIO,
            _FASE_ANALISIS,
            _FASE_RESULTADOS,
        ),
        indice_resultados=3,
        resultados_presentes=resultados_presentes,
        descripcion="Entrada, información técnica del repositorio, ejecución del análisis y resultados.",
    )


# ---------------------------------------------------------
# Navegación entre fases (botón discreto de avance)
# ---------------------------------------------------------

def render_next_phase_button(
    container,
    step_key: str,
    target_step: int,
    label: str = "Siguiente fase",
) -> None:
    """Botón discreto que oculta la fase actual y muestra la siguiente.

    Solo afecta la fase visible creada por `create_stage_step_panels` /
    `create_coding_step_panels`; no altera datos ni lógica de la etapa.
    """
    container.divider()
    _, col_button = container.columns([5, 1.4])
    if col_button.button(
        label,
        key=f"next_phase__{step_key}__{target_step}",
        icon=":material/arrow_forward:",
        icon_position="right",
        width="stretch",
    ):
        st.session_state[step_key] = target_step
        st.session_state[f"{step_key.removesuffix('_active_step')}_step_manual"] = True
        st.rerun()


# ---------------------------------------------------------
# Entradas con su estado de revisión (etiquetas de GitLab)
# ---------------------------------------------------------

_CLASES_ESTADO_FLUJO = {
    "Pendiente": "pendiente",
    "Requiere modificación": "rework",
    "Revisada": "revisada",
    "Sin estado": "sin-estado",
}


def chip_estado_flujo_html(labels) -> str:
    """Etiqueta visual del estado de revisión de un Issue (Pendiente, Requiere modificación…)."""
    estado = clasificar_estado_flujo(labels)
    return f'<span class="wf-chip {_CLASES_ESTADO_FLUJO[estado]}">{escape(estado)}</span>'


def entrada_fila_html(identificador: str, texto: str = "", labels=None) -> str:
    """Fila de una entrada: identificador, descripción, estado de revisión y si se analiza.

    Se listan todos los issues de la etapa; solo los Pendiente o Requiere modificación
    se analizan, y los demás se atenúan y se rotulan «Solo referencia».
    """
    texto_html = f'<span class="entry-text">{escape(str(texto))}</span>' if texto else ""
    analizable = etiquetas_son_analizables(labels)
    alcance = chip_html("Se analiza", "ok") if analizable else chip_html("Solo referencia", "muted")
    return (
        f'<div class="entry-row{"" if analizable else " not-analyzed"}">'
        f'<span class="entry-id">{escape(str(identificador))}</span>'
        f"{texto_html}"
        f"{chip_estado_flujo_html(labels)}"
        f"{alcance}"
        "</div>"
    )


def aviso_alcance_entradas_html() -> str:
    """Aclara que se listan todos los issues de entrada pero solo se analizan los de ciertas etiquetas."""
    return (
        '<div class="entry-scope-note">'
        "Se muestran <strong>todos los issues de entrada</strong> de esta etapa, con su etiqueta en GitLab. "
        "<strong>Solo se analizan</strong> los que tienen la etiqueta <strong>Pendiente</strong> o "
        "<strong>Requiere modificación</strong>; los demás (por ejemplo, <strong>Revisada</strong>) "
        "se muestran como referencia y no se envían al análisis."
        "</div>"
    )


# ---------------------------------------------------------
# Fase de entradas con matriz heredada + issues (Diseño, Codificación, Pruebas)
# ---------------------------------------------------------

def contar(n: int, singular: str, plural: str) -> str:
    """«1 válido» / «2 válidos»."""
    return f"{n} {singular if n == 1 else plural}"


def chip_html(texto, tono: str = "muted") -> str:
    """Etiqueta redondeada. Tonos: ok, warn, bad, info, muted."""
    return f'<span class="wf-chip tone-{tono}">{escape(str(texto))}</span>'


def tarjeta_estado_entrada_html(titulo: str, chips: list, meta: str = "") -> str:
    """Tarjeta del resumen de entradas: título, etiquetas de estado (ya en HTML) y una línea de contexto."""
    meta_html = f'<span class="entry-status-meta">{escape(meta)}</span>' if meta else ""
    return (
        '<div class="entry-status-card">'
        f'<span class="entry-status-title">{escape(titulo)}</span>'
        f'<div class="entry-status-chips">{"".join(chips)}</div>'
        f"{meta_html}"
        "</div>"
    )


def rotulo_bloque_html(texto: str) -> str:
    """Rótulo pequeño que titula un bloque dentro de una subsección."""
    return f'<div class="entry-block-label">{escape(texto)}</div>'


def crear_subsecciones_entrada(paso_entrada, etiqueta_issues: str) -> SimpleNamespace:
    """Ordena la fase de entradas en dos subsecciones (pestañas), cada una con su propio resumen.

    - Pestaña «Matriz de trazabilidad»: `resumen_matriz` (tarjeta de estado), `avisos`
      (cambios y errores, solo si los hay), `tabla` (contenido) y `acciones`
      (actualizar, editar, cargar).
    - Pestaña de issues: `resumen_issues` (tarjeta de estado) y luego `tab_issues`.

    Los contenedores se crean por adelantado y se rellenan cuando la etapa tiene los
    datos: el orden en pantalla es el de creación, no el de ejecución del script, así
    que la lógica de cada etapa no cambia. Las etiquetas de las pestañas son fijas
    (si cambiaran, Streamlit reiniciaría la pestaña activa en cada ejecución).
    """
    tab_matriz, tab_issues = paso_entrada.tabs(["Matriz de trazabilidad", etiqueta_issues])
    return SimpleNamespace(
        tab_matriz=tab_matriz,
        tab_issues=tab_issues,
        resumen_matriz=tab_matriz.container(),
        avisos=tab_matriz.container(),
        tabla=tab_matriz.container(),
        acciones=tab_matriz.container(),
        resumen_issues=tab_issues.container(),
    )


_ICONO_ESTADO_RESULTADO = {
    "CORREGIR": "🔴",
    "CONFORME CON MEJORAS": "🟡",
    "CONFORME": "🟢",
    "APROBADO": "🟢",
    "REVISAR": "🟡",
}


def selector_resultados(container, stage_prefix: str, items: list, columnas: int = 4):
    """Barra de botones para elegir qué resultado se muestra (uno a la vez).

    `items` es una lista de (identificador, estado). Devuelve el identificador elegido
    (por omisión, el primero). La elección se guarda en `st.session_state`
    (`<stage_prefix>_resultado_sel`); si el resultado elegido ya no existe (p. ej. tras
    un nuevo análisis) se vuelve al primero.
    """
    clave = f"{stage_prefix}_resultado_sel"
    ids = [identificador for identificador, _ in items]
    if not ids:
        return None
    if st.session_state.get(clave) not in ids:
        st.session_state[clave] = ids[0]
    elegido = st.session_state[clave]

    with container.container(key=f"result_bar_{stage_prefix}"):
        for inicio in range(0, len(items), columnas):
            fila = items[inicio:inicio + columnas]
            for columna, (identificador, estado) in zip(st.columns(columnas), fila):
                activo = identificador == elegido
                if columna.button(
                    f"{_ICONO_ESTADO_RESULTADO.get(estado, '⚪')} {identificador}",
                    key=f"{stage_prefix}_resultado_btn_{identificador}",
                    help=f"{identificador} · {estado}",
                    type="primary" if activo else "secondary",
                    width="stretch",
                ):
                    st.session_state[clave] = identificador
                    st.rerun()
    return elegido


def kpi_strip_html(items: list, compact: bool = False) -> str:
    """Fila de indicadores livianos: pares (valor, rótulo). Reemplaza varias tarjetas st.metric."""
    celdas = "".join(
        f'<div class="kpi-item"><span class="kpi-value">{escape(str(valor))}</span>'
        f'<span class="kpi-label">{escape(str(rotulo))}</span></div>'
        for valor, rotulo in items
    )
    return f'<div class="kpi-strip{" compact" if compact else ""}">{celdas}</div>'


def titulo_item(identificador, titulo, estado=None) -> str:
    """Título de un resultado sin repetir el identificador: «DIS-001 — Módulo · CORREGIR».

    Los Issues suelen llamarse «DIS-001 - Módulo…»: sin este ajuste el identificador
    se mostraba dos veces («DIS-001 — DIS-001 - Módulo…»).
    """
    ident = str(identificador or "").strip()
    resto = _titulo_sin_identificador(ident, titulo)
    base = f"{ident} — {resto}" if ident and resto else (ident or resto)
    return f"{base} · {estado}" if estado else base


def _titulo_sin_identificador(identificador: str, titulo) -> str:
    """El título del Issue sin el identificador con el que suele empezar («DIS-001 - Módulo» → «Módulo»)."""
    texto = str(titulo or "").strip()
    return re.sub(rf"^{re.escape(identificador)}\s*[-–—:]*\s*", "", texto, flags=re.IGNORECASE) if identificador else texto


def resumen_estados_entradas_html(lista_de_labels, con_total: bool = False, con_alcance: bool = False) -> str:
    """Conteo de entradas por estado de revisión, en el orden Pendiente · Requiere modificación · …

    Con `con_total` antepone el total («4 issues encontrados»), de modo que el total y
    los estados se lean en una sola línea. Con `con_alcance` agrega al final cuántos se
    analizan y cuántos quedan solo como referencia.
    """
    conteo = {}
    total = 0
    analizables = 0
    for labels in lista_de_labels:
        estado = clasificar_estado_flujo(labels)
        conteo[estado] = conteo.get(estado, 0) + 1
        total += 1
        analizables += bool(etiquetas_son_analizables(labels))
    chips = (chip_html(contar(total, "issue encontrado", "issues encontrados"), "info") if con_total else "") + "".join(
        f'<span class="wf-chip {_CLASES_ESTADO_FLUJO[estado]}">{conteo[estado]} · {escape(estado)}</span>'
        for estado in ("Pendiente", "Requiere modificación", "Revisada", "Sin estado")
        if conteo.get(estado)
    )
    if con_alcance and total:
        chips += chip_html(f"{analizables} se analizan", "ok" if analizables else "muted")
        if total - analizables:
            chips += chip_html(f"{total - analizables} solo referencia", "muted")
    return f'<div class="entry-summary">{chips}</div>' if chips else ""


def render_alcance_entradas(container, lista_de_labels) -> None:
    """Aviso de alcance + conteo por etiqueta de TODOS los issues de entrada de la etapa."""
    container.markdown(aviso_alcance_entradas_html(), unsafe_allow_html=True)
    container.markdown(
        resumen_estados_entradas_html(lista_de_labels, con_total=True, con_alcance=True),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Badge de estado
# ---------------------------------------------------------

_BADGE_CLASSES = {
    "CORREGIR": "state-corregir",
    "CONFORME CON MEJORAS": "state-mejoras",
    "CONFORME": "state-conforme",
    "APROBADO": "state-conforme",
}


def render_state_badge(estado: str) -> None:
    cls = _BADGE_CLASSES.get(estado, "state-revision")
    st.markdown(
        f'<span class="state-badge {cls}">{estado}</span>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Matriz de resultados (una fila por issue, antes del detalle)
# ---------------------------------------------------------

_COLUMNAS_MATRIZ_RESULTADOS = (
    ("Issue", ""),
    ("Título", ""),
    ("Estado", ""),
    ("Calidad", "num"),
    ("Seguridad", "num"),
    ("Correcciones", "num"),
    ("Precisiones", "num"),
    ("Mejoras", "num"),
)
_COLUMNAS_DETALLE_METRICAS = ("Código", "Métrica", "Resultado", "Base", "Interpretación")


def fila_metrica(codigo, nombre, resultado="—", base="—", interpretacion="") -> dict:
    """Una métrica del detalle desplegable de una fila de la matriz (todo ya formateado)."""
    return {
        "Código": codigo, "Métrica": nombre, "Resultado": resultado,
        "Base": base, "Interpretación": interpretacion,
    }


def filas_metricas_presentacion(metricas: dict) -> list:
    """Proyecta, sin recalcular, las métricas de una presentación (Diseño, Codificación, Pruebas)
    al detalle por métrica de la matriz."""
    from core.utils import extraer_porcentaje

    filas = []
    for metrica in (metricas or {}).values():
        if "numero_criticas" in metrica:  # MS-05: se mide en cantidad de críticas, no en porcentaje.
            criticas = metrica.get("numero_criticas")
            resultado = f"{criticas} críticas" if criticas is not None else "No evaluable"
        else:
            resultado = extraer_porcentaje(metrica.get("valor"))
        numerador, denominador = metrica.get("numerador"), metrica.get("denominador")
        filas.append(fila_metrica(
            metrica.get("codigo", ""),
            metrica.get("nombre", ""),
            resultado,
            f"{numerador} de {denominador}" if numerador is not None and denominador is not None else "—",
            metrica.get("resultado") or metrica.get("interpretacion") or metrica.get("conclusion") or "",
        ))
    return filas


def fila_matriz_resultados(
    identificador, titulo, estado, calidad="—", seguridad="—",
    correcciones=None, precisiones=None, mejoras=None, metricas=None,
) -> dict:
    """Fila de la matriz de resultados. Calidad y seguridad llegan ya formateadas; los
    hallazgos, como cantidades (None = no aplica, p. ej. un issue que no llegó a evaluarse);
    `metricas` (lista de `fila_metrica`) es el detalle que se despliega al abrir la fila."""
    ident = str(identificador or "").strip()
    return {
        "Issue": ident,
        "Título": _titulo_sin_identificador(ident, titulo),
        "Estado": estado,
        "Calidad": calidad,
        "Seguridad": seguridad,
        "Correcciones": correcciones,
        "Precisiones": precisiones,
        "Mejoras": mejoras,
        "Métricas": metricas or [],
    }


def _celda_matriz_html(nombre: str, valor) -> str:
    if nombre == "Estado":
        cls = _BADGE_CLASSES.get(valor, "state-revision")
        return f'<span class="state-badge {cls}">{escape(str(valor))}</span>'
    if nombre == "Issue":
        return f"<strong>{escape(str(valor))}</strong>"
    if nombre in ("Correcciones", "Precisiones", "Mejoras"):
        celda = "—" if valor is None else escape(str(valor))
        return f'<span class="rm-count">{celda}</span>' if valor else celda
    return escape(str(valor if valor not in (None, "") else "—"))


def _detalle_metricas_html(metricas: list) -> str:
    cabecera = "".join(f"<th>{escape(nombre)}</th>" for nombre in _COLUMNAS_DETALLE_METRICAS)
    cuerpo = "".join(
        "<tr>" + "".join(
            f"<td>{escape(str(metrica.get(nombre) or '—'))}</td>" for nombre in _COLUMNAS_DETALLE_METRICAS
        ) + "</tr>"
        for metrica in metricas
    )
    return (
        '<div class="rm-detail"><div class="rm-detail-title">Detalle por métrica</div>'
        f'<table class="rm-metrics"><thead><tr>{cabecera}</tr></thead><tbody>{cuerpo}</tbody></table></div>'
    )


def matriz_resultados_html(filas: list) -> str:
    """Matriz con el resultado de cada issue (estado, índices, cantidad de hallazgos). Cada fila con
    métricas se despliega para ver el detalle por métrica."""
    cabecera = "".join(
        f'<span class="{clase}">{escape(nombre)}</span>' if clase else f"<span>{escape(nombre)}</span>"
        for nombre, clase in _COLUMNAS_MATRIZ_RESULTADOS
    )
    cuerpo = ""
    for fila in filas:
        celdas = "".join(
            f'<span class="{clase}">{_celda_matriz_html(nombre, fila.get(nombre))}</span>' if clase
            else f"<span>{_celda_matriz_html(nombre, fila.get(nombre))}</span>"
            for nombre, clase in _COLUMNAS_MATRIZ_RESULTADOS
        )
        if fila.get("Métricas"):
            cuerpo += (
                f'<details class="rm-row"><summary class="rm-grid rm-summary">{celdas}</summary>'
                f'{_detalle_metricas_html(fila["Métricas"])}</details>'
            )
        else:
            cuerpo += f'<div class="rm-row"><div class="rm-grid rm-summary rm-flat">{celdas}</div></div>'
    return (
        '<div class="result-matrix">'
        f'<div class="rm-grid rm-head">{cabecera}</div>{cuerpo}</div>'
    )


def render_matriz_resultados(container, filas: list, etiqueta_detalle: str) -> None:
    """Matriz con TODOS los issues evaluados, para leer el resultado global antes del detalle."""
    if not filas:
        return
    container.markdown(rotulo_bloque_html("Matriz de resultados por issue"), unsafe_allow_html=True)
    container.markdown(matriz_resultados_html(filas), unsafe_allow_html=True)
    container.caption(
        "Una fila por issue evaluado: haz clic en una fila para desplegar el detalle por métrica. "
        "Correcciones, precisiones y mejoras indican la cantidad de hallazgos; su contenido y el "
        f"análisis completo están en la pestaña «{etiqueta_detalle}»."
    )


# ---------------------------------------------------------
# Resumen general de la etapa (mismo formato en todas las etapas)
# ---------------------------------------------------------

def _formatear_promedio(valor) -> str:
    """Formatea un índice promedio 0..1 como porcentaje; 'No evaluado' si no hay dato."""
    if isinstance(valor, (int, float)):
        return f"{round(valor * 100)} %"
    return "No evaluado"


def promedio_indices(valores) -> float:
    """Promedia solo los valores numéricos de una colección (ignora None/no numéricos)."""
    numericos = [v for v in (valores or []) if isinstance(v, (int, float))]
    return sum(numericos) / len(numericos) if numericos else None


def render_stage_summary(
    container,
    *,
    etiqueta_items: str,
    total_items: int,
    requieren_correccion: int,
    con_error: int,
    calidad_promedio,
    seguridad_promedio,
    aviso: str,
    subtitulo: str = "",
    filas_matriz: list = None,
    etiqueta_detalle: str = "",
) -> None:
    """Resumen general homogéneo para todas las etapas.

    Una sola fila de tarjetas (ítems evaluados · requieren corrección · con error ·
    calidad y seguridad promedio), la matriz de resultados de todos los issues (si se
    entregan `filas_matriz`) y el aviso de decisión humana. Solo presentación: no recalcula.
    """
    container.subheader("Resumen general de resultados")
    if subtitulo:
        container.caption(subtitulo)

    container.markdown(
        kpi_strip_html([
            (total_items, etiqueta_items),
            (requieren_correccion, "Requieren corrección"),
            (con_error, "Con error"),
            (_formatear_promedio(calidad_promedio), "Calidad promedio"),
            (_formatear_promedio(seguridad_promedio), "Seguridad promedio"),
        ]),
        unsafe_allow_html=True,
    )

    render_matriz_resultados(container, filas_matriz or [], etiqueta_detalle)

    with container:
        render_human_decision_notice(aviso)


# ---------------------------------------------------------
# Encabezado de resultado (Estado + métricas principales)
# ---------------------------------------------------------

def render_evaluation_header(
    titulo: str,
    estado: str,
    indice_calidad: str,
    indice_seguridad: str,
    explicacion_estado: str = "",
) -> None:
    """Estado, índices y explicación de un resultado.

    `titulo` se conserva por compatibilidad: el contenedor del resultado ya muestra
    su título, así que no se repite aquí.
    """
    render_state_badge(estado)

    m1, m2 = st.columns(2)
    m1.metric("Índice de Calidad", indice_calidad)
    m2.metric("Índice de Seguridad", indice_seguridad)

    if explicacion_estado:
        st.info(f"**¿Por qué este estado?**\n\n{explicacion_estado}")


# ---------------------------------------------------------
# Card de métrica individual (MC-01, MC-02, MC-03, etc.)
# ---------------------------------------------------------

def render_metric_card(
    codigo: str,
    nombre: str,
    valor_porcentaje: str,
    numerador: int,
    denominador: int,
    descripcion_calculo: str,
    estado_texto: str = "",
) -> None:
    st.markdown(f"### {codigo} — {nombre}")
    st.metric(f"Resultado {codigo}", valor_porcentaje)

    st.markdown(
        f'<div class="metric-detail">'
        f'{numerador} de {denominador} {descripcion_calculo}.'
        f'{"<br><strong>Estado:</strong> " + estado_texto if estado_texto else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Sección de métricas (calidad o seguridad)
# ---------------------------------------------------------

def render_metric_section(titulo: str, metricas: list) -> None:
    st.markdown(f"### {titulo}")
    for metrica in metricas:
        render_metric_card(**metrica)
        st.divider()


# ---------------------------------------------------------
# Sección de hallazgos (correcciones, precisiones, oportunidades)
# ---------------------------------------------------------

def render_findings_section(
    correcciones: list,
    precisiones: list,
    oportunidades: list,
) -> None:
    panels = (
        (
            "Correcciones necesarias",
            correcciones,
            "finding-correction",
            "No se identificaron correcciones necesarias.",
        ),
        (
            "Precisiones necesarias",
            precisiones,
            "finding-precision",
            "No se identificaron precisiones necesarias.",
        ),
        (
            "Oportunidades de mejora",
            oportunidades,
            "finding-opportunity",
            "No se identificaron oportunidades adicionales.",
        ),
    )

    columns = st.columns(3)
    for index, (column, panel) in enumerate(zip(columns, panels)):
        title, items, css_class, empty_message = panel
        with column:
            # El conteo funciona como cabecera visual de cada categoría y el
            # detalle queda alineado inmediatamente debajo, en la misma columna.
            st.metric(title, len(items))
            if items:
                for item in items:
                    text = _texto_hallazgo_ui(item)
                    if text:
                        safe_text = escape(text).replace("\n", "<br>")
                        st.markdown(
                            f'<div class="finding-block {css_class}">{safe_text}</div>',
                            unsafe_allow_html=True,
                        )
            elif index == 0:
                st.success(empty_message)
            else:
                st.caption(empty_message)


# ---------------------------------------------------------
# Sección de trazabilidad (colapsable)
# ---------------------------------------------------------

def render_traceability_section(titulo: str, filas: list, columnas: list = None) -> None:
    with st.expander(titulo, expanded=False):
        if not filas:
            st.info("No hay datos de trazabilidad disponibles.")
            return
        if columnas:
            import pandas as pd
            df = pd.DataFrame(filas)
            columnas_disponibles = [col for col in columnas if col in df.columns]
            st.dataframe(
                df[columnas_disponibles] if columnas_disponibles else df,
                width="stretch",
                hide_index=True,
            )
        else:
            st.table(filas)


# ---------------------------------------------------------
# Sección de artefactos y acciones
# ---------------------------------------------------------

def render_artifact_actions(descargas: list) -> None:
    st.subheader("Artefactos generados")
    cols = st.columns(len(descargas))
    for col, descarga in zip(cols, descargas):
        with col:
            st.download_button(**descarga)


# ---------------------------------------------------------
# Retroalimentación de GitLab
# ---------------------------------------------------------

def render_gitlab_feedback(publicado: bool) -> None:
    if publicado:
        st.success("Retroalimentación publicada correctamente en GitLab.")
    else:
        st.warning("La retroalimentación no fue publicada en GitLab.")


# ---------------------------------------------------------
# Aviso de decisión humana
# ---------------------------------------------------------

def render_human_decision_notice(texto: str) -> None:
    st.info(texto)
