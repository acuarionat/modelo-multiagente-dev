"""Series de datos y gráficos del panel del proyecto.

Las funciones de datos son puras (sin Streamlit, GitLab ni Altair) para poder
probarlas. Los constructores de gráficos arman gráficos Altair autoexplicativos:
título, subtítulo que dice qué se mira, ejes rotulados y la línea del umbral de
aprobación. Solo presentan lo ya registrado; no recalculan ningún índice.
"""

from datetime import datetime, timezone

from core.umbral_aprobacion import UMBRAL_APROBACION, porcentaje

NOMBRES_ETAPA = {
    "requerimientos": "Requerimientos",
    "diseno": "Diseño",
    "codificacion": "Codificación",
    "pruebas": "Pruebas",
}
UMBRAL_PCT = porcentaje(UMBRAL_APROBACION)  # 80.0
# Análisis de una misma etapa registrados con menos de estos minutos de diferencia
# pertenecen a una misma ejecución (un clic en «Iniciar análisis»).
VENTANA_EJECUCION_MIN = 10

MARGEN_ROTULOS = 150  # píxeles reservados a la derecha para los rótulos del umbral
COLOR_CALIDAD = "#07549A"
COLOR_SEGURIDAD = "#E08A00"
COLOR_UMBRAL = "#D9534F"
COLORES_ETAPA = {
    "Requerimientos": "#1F75CB",
    "Diseño": "#8E44AD",
    "Codificación": "#E08A00",
    "Pruebas": "#0E9AA7",
}
FORMAS_ETAPA = {"Requerimientos": "circle", "Diseño": "square", "Codificación": "triangle-up", "Pruebas": "diamond"}
COLORES_ESTADO = {
    "Revisada": "#1F75CB",
    "Requiere modificación": "#D9534F",
    "Pendiente": "#F2C300",
    "Sin estado": "#B8C4CF",
}


# ---------------------------------------------------------------------------
# Datos (puros)
# ---------------------------------------------------------------------------
def _parsear_fecha(texto):
    """Fecha de SQLite (UTC, 'AAAA-MM-DD HH:MM:SS') -> datetime con zona; None si no se puede leer."""
    try:
        return datetime.strptime(str(texto)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fecha_local_texto(fecha) -> str:
    return fecha.astimezone().strftime("%d/%m %H:%M") if fecha else "sin fecha"


def _pct(valor):
    """Índice 0..1 -> porcentaje (None si no es evaluable)."""
    return porcentaje(valor)


def etiqueta_cambio(actual, previo) -> str:
    """Texto del cambio de un índice (en %) respecto del valor anterior."""
    if actual is None:
        return "Sin índice evaluable"
    if previo is None:
        return "Primer valor evaluable"
    delta = round(actual - previo, 1)
    if delta > 0:
        texto = f"▲ +{delta:g} pts"
    elif delta < 0:
        texto = f"▼ −{abs(delta):g} pts"
    else:
        texto = "= sin cambio"
    if previo > UMBRAL_PCT >= actual:
        texto += " · cae bajo el umbral"
    elif previo <= UMBRAL_PCT < actual:
        texto += " · supera el umbral"
    return texto


def normalizar_historial(historial: list) -> list:
    """Una fila por análisis registrado, en orden cronológico, con índices en %."""
    filas = []
    for h in historial or []:
        etapa = h.get("stage") or "requerimientos"
        issue = h.get("gitlab_iid")
        fecha = _parsear_fecha(h.get("analysis_date"))
        filas.append({
            "etapa": etapa,
            "etapa_nombre": NOMBRES_ETAPA.get(etapa, etapa),
            "issue": issue,
            "fecha": fecha,
            "fecha_texto": _fecha_local_texto(fecha),
            "calidad": _pct(h.get("quality_index")),
            "seguridad": _pct(h.get("security_index")),
            "veredicto": (h.get("verdict") or "").strip() or "Sin veredicto",
        })
    return filas


def _indice_pruebas(summary: dict, codigos: tuple):
    """Promedio de las métricas EVALUADAS de Pruebas indicadas (None si ninguna se evaluó)."""
    valores = [
        m.get("valor") for codigo in codigos
        for m in [(summary.get("metricas") or {}).get(codigo) or {}]
        if m.get("estado") == "EVALUADO" and isinstance(m.get("valor"), (int, float)) and not isinstance(m.get("valor"), bool)
    ]
    return sum(valores) / len(valores) if valores else None


def historial_desde_resultados(etapa: str, payload: dict, fecha) -> list:
    """Filas con forma de historial a partir del último resultado guardado de una etapa.

    Sirve para las etapas cuyos análisis se hicieron antes de que el historial registrara la
    etapa: muestra su último resultado (un punto por issue) hasta que haya análisis nuevos."""
    configuracion = {
        "diseno": ("diseno_resultados", "design_summary", "design_context",
                   lambda r: r.get("indice_calidad_diseno"), lambda r: r.get("indice_seguridad_diseno")),
        "codificacion": ("codificacion_resultados", "coding_summary", "coding_context",
                         lambda r: r.get("indice_calidad_codigo"), lambda r: r.get("indice_seguridad_codigo")),
        "pruebas": ("pruebas_resultados", "testing_summary", "testing_context",
                    lambda r: _indice_pruebas(r, ("MC-07", "MC-08")), lambda r: _indice_pruebas(r, ("MS-08", "MS-09"))),
    }.get(etapa)
    resultados = (payload or {}).get(configuracion[0]) if configuracion else None
    if not isinstance(resultados, dict):
        return []
    _clave, clave_resumen, clave_contexto, f_calidad, f_seguridad = configuracion
    filas = []
    for resultado in resultados.values():
        resumen = (resultado or {}).get(clave_resumen) or {}
        contexto = ((resultado or {}).get(clave_contexto) or [{}])[0] or {}
        issue = contexto.get("issue_iid", resumen.get("issue_iid"))
        estado = resumen.get("estado_orientativo")
        if issue is None or estado == "ERROR":
            continue
        filas.append({
            "gitlab_iid": issue, "analysis_date": fecha, "quality_index": f_calidad(resumen),
            "security_index": f_seguridad(resumen), "verdict": estado, "execution_time": None,
            "observations": "", "stage": etapa,
        })
    return sorted(filas, key=lambda f: f["gitlab_iid"])


def _promedio(valores):
    numericos = [v for v in valores if v is not None]
    return round(sum(numericos) / len(numericos), 1) if numericos else None


def agrupar_ejecuciones(filas: list, ventana_min: int = VENTANA_EJECUCION_MIN) -> list:
    """Agrupa los análisis de cada etapa en ejecuciones y promedia sus índices.

    Devuelve una lista cronológica; cada ejecución trae el promedio de calidad y de
    seguridad de sus issues, cuántos issues tuvo y el cambio respecto de la
    ejecución anterior de la MISMA etapa."""
    abiertas = {}  # etapa -> ejecución en curso
    ejecuciones = []
    for fila in filas:
        etapa = fila["etapa"]
        actual = abiertas.get(etapa)
        if actual is not None:
            ultima, fecha = actual["_ultima"], fila["fecha"]
            mismo_grupo = ultima is None or fecha is None or (fecha - ultima).total_seconds() <= ventana_min * 60
        else:
            mismo_grupo = False
        if not mismo_grupo:
            actual = {"etapa": etapa, "etapa_nombre": fila["etapa_nombre"], "inicio": fila["fecha"],
                      "fecha_texto": fila["fecha_texto"], "filas": [], "_ultima": None}
            abiertas[etapa] = actual
            ejecuciones.append(actual)
        actual["filas"].append(fila)
        actual["_ultima"] = fila["fecha"] or actual["_ultima"]

    # El orden de ejecución es el de inicio (las etapas pueden intercalarse en el tiempo).
    posicion = {id(e): i for i, e in enumerate(ejecuciones)}
    ejecuciones.sort(key=lambda e: (e["inicio"] is None, e["inicio"] or datetime.min.replace(tzinfo=timezone.utc), posicion[id(e)]))
    previos = {}
    resultado = []
    for numero, e in enumerate(ejecuciones, start=1):
        calidad = _promedio([f["calidad"] for f in e["filas"]])
        seguridad = _promedio([f["seguridad"] for f in e["filas"]])
        previo = previos.get(e["etapa"], {})
        resultado.append({
            "ejecucion": numero,
            "etapa": e["etapa"],
            "etapa_nombre": e["etapa_nombre"],
            "fecha_texto": e["fecha_texto"],
            "fecha_iso": e["inicio"].astimezone().replace(tzinfo=None).isoformat() if e["inicio"] else None,
            "issues": len(e["filas"]),
            "calidad": calidad,
            "seguridad": seguridad,
            "cambio_calidad": etiqueta_cambio(calidad, previo.get("calidad")),
            "cambio_seguridad": etiqueta_cambio(seguridad, previo.get("seguridad")),
        })
        previos[e["etapa"]] = {"calidad": calidad if calidad is not None else previo.get("calidad"),
                               "seguridad": seguridad if seguridad is not None else previo.get("seguridad")}
    return resultado


def _formato_pct(valor) -> str:
    return "—" if valor is None else f"{valor:g} %"


def describir_cambios(ejecuciones: list) -> list:
    """Lectura automática de la serie: cuándo un índice cruza el umbral, y su mayor subida y bajada.

    Compara cada ejecución con la anterior de su misma etapa (la que ya trae `cambio_*`)."""
    frases = []
    for indicador, nombre in (("calidad", "Calidad"), ("seguridad", "Seguridad")):
        previos = {}
        cambios = []
        for e in ejecuciones:
            valor = e[indicador]
            previo = previos.get(e["etapa"])
            if valor is not None and previo is not None:
                cambios.append((e, previo, valor))
            if valor is not None:
                previos[e["etapa"]] = valor
        donde = lambda e: f"ejecución {e['ejecucion']} · {e['etapa_nombre']} · {e['fecha_texto']}"
        for e, previo, valor in cambios:
            if previo > UMBRAL_PCT >= valor:
                frases.append(f"**{nombre}** cae bajo el umbral del {UMBRAL_PCT:g} %: de {_formato_pct(previo)} a {_formato_pct(valor)} ({donde(e)}).")
            elif previo <= UMBRAL_PCT < valor:
                frases.append(f"**{nombre}** supera el umbral del {UMBRAL_PCT:g} %: de {_formato_pct(previo)} a {_formato_pct(valor)} ({donde(e)}).")
        if cambios:
            e, previo, valor = max(cambios, key=lambda c: c[2] - c[1])
            if valor - previo > 0:
                frases.append(f"Mayor subida de **{nombre.lower()}**: +{round(valor - previo, 1):g} pts, de {_formato_pct(previo)} a {_formato_pct(valor)} ({donde(e)}).")
            e, previo, valor = min(cambios, key=lambda c: c[2] - c[1])
            if valor - previo < 0:
                frases.append(f"Mayor bajada de **{nombre.lower()}**: −{round(previo - valor, 1):g} pts, de {_formato_pct(previo)} a {_formato_pct(valor)} ({donde(e)}).")
    return frases


def construir_porcentajes_trazabilidad(trazabilidad: dict) -> list:
    """Cumplimiento por etapa: qué porcentaje de lo que entrega la etapa anterior quedó cubierto.

    Devuelve una fila por etapa disponible con los tres tramos (cubierto, requiere
    revisión o con fallo, pendiente o sin evaluar) que suman el total de la etapa."""
    definiciones = (
        ("diseno", "Diseño", "Requisitos", "requisitos_totales",
         lambda r: r.get("cubiertos", 0), lambda r: r.get("requieren_revision", 0),
         lambda r: r.get("pendientes_relacion", 0) + r.get("no_evaluados", 0),
         "requisitos con un diseño que los cubre", "requisitos"),
        ("codificacion", "Codificación", "Diseño", "elementos_diseno_totales",
         lambda r: r.get("implementados", 0), lambda r: r.get("no_confirmados", 0),
         lambda r: r.get("no_evaluados", 0),
         "elementos de diseño implementados en código", "elementos de diseño"),
        ("pruebas", "Pruebas", "Codificación", "codificaciones_totales",
         lambda r: r.get("verificadas", 0),
         lambda r: r.get("con_fallo_pendiente", 0) + r.get("pendientes_revision", 0),
         lambda r: r.get("no_evaluadas", 0),
         "codificaciones verificadas con pruebas", "codificaciones"),
    )
    filas = []
    for etapa, nombre, objeto, clave_total, f_cubierto, f_atencion, f_pendiente, significado, elementos in definiciones:
        resumen = ((trazabilidad or {}).get(etapa) or {}).get("resumen")
        if not resumen:
            continue
        cubierto, atencion, pendiente = f_cubierto(resumen), f_atencion(resumen), f_pendiente(resumen)
        total = int(resumen.get(clave_total, 0) or 0)
        # Lo que no está en ninguna categoría cuenta como pendiente; el total nunca baja de lo contado.
        pendiente += max(0, total - (cubierto + atencion + pendiente))
        total = max(total, cubierto + atencion + pendiente)
        if total <= 0:
            continue
        filas.append({
            "etapa": etapa,
            "etiqueta": f"{nombre} cubre {objeto.lower()}",
            "significado": significado,
            "elementos": elementos,
            "total": total,
            "cubierto": cubierto,
            "atencion": atencion,
            "pendiente": pendiente,
            "pct_cubierto": round(cubierto / total * 100, 1),
        })
    return filas


# ---------------------------------------------------------------------------
# Gráficos (Altair)
# ---------------------------------------------------------------------------
def _titulo(texto: str, subtitulo: str):
    import altair as alt
    return alt.TitleParams(
        text=texto, subtitle=subtitulo, anchor="start", fontSize=16, subtitleFontSize=12,
        subtitleColor="#5E6E7E", subtitlePadding=6, offset=14,
    )


def _capa_umbral(titulo_y: str):
    """Franjas «aprobado / requiere corrección» y la línea del umbral, con rótulos."""
    import altair as alt
    import pandas as pd

    escala_y = alt.Scale(domain=[0, 100])

    def _franja(desde, hasta, color):
        return alt.Chart(pd.DataFrame({"a": [desde], "b": [hasta]})).mark_rect(color=color, opacity=0.07).encode(
            y=alt.Y("a:Q", title=titulo_y, scale=escala_y), y2="b:Q",
        )

    bandas = _franja(UMBRAL_PCT, 100, "#2E9E5B") + _franja(0, UMBRAL_PCT, "#D9534F")
    linea = alt.Chart(pd.DataFrame({"y": [UMBRAL_PCT]})).mark_rule(
        color=COLOR_UMBRAL, strokeDash=[6, 4], strokeWidth=1.6,
    ).encode(y=alt.Y("y:Q", title=titulo_y, scale=escala_y))

    def _rotulo(y, lineas_texto, color):
        # Van en el margen derecho (fuera del área de las líneas) y a distinta altura,
        # para que ni se tapen entre sí ni cubran los puntos.
        return alt.Chart(pd.DataFrame({"y": [y]})).mark_text(
            text=lineas_texto, align="left", baseline="middle", dx=10, fontSize=11, fontWeight="bold",
            lineHeight=13, color=color,
        ).encode(y=alt.Y("y:Q", title=titulo_y, scale=escala_y), x=alt.value("width"))

    rotulos = (
        _rotulo(96, ["Zona aprobada", f"(mayor a {UMBRAL_PCT:g} %)"], "#2E7D4F")
        + _rotulo(UMBRAL_PCT, ["Umbral de", f"aprobación: {UMBRAL_PCT:g} %"], COLOR_UMBRAL)
        + _rotulo(35, ["Zona que requiere", f"corrección ({UMBRAL_PCT:g} % o menos)"], "#9A2A24")
    )
    return bandas + linea + rotulos


def grafico_tendencia(ejecuciones: list, indicador: str):
    """Evolución de un índice (`calidad` o `seguridad`) a lo largo del tiempo, con una línea por etapa.

    Cada punto es el promedio de los issues evaluados en una ejecución. Un valor ausente corta la
    línea y se marca con una ✕ en la base del gráfico."""
    import altair as alt
    import pandas as pd

    nombre = "Calidad" if indicador == "calidad" else "Seguridad"
    cambio = "cambio_calidad" if indicador == "calidad" else "cambio_seguridad"
    registros = [
        {
            "fecha": e["fecha_iso"], "valor": e[indicador], "Etapa": e["etapa_nombre"], "ejecucion": e["ejecucion"],
            "fecha_texto": e["fecha_texto"], "issues": e["issues"], "cambio": e[cambio],
        }
        for e in ejecuciones if e["fecha_iso"]
    ]
    if not registros:
        return None
    df = pd.DataFrame(registros)
    etapas = [n for n in COLORES_ETAPA if n in set(df["Etapa"])]
    titulo_y = f"{nombre} promedio de la ejecución (%)"
    x = alt.X("fecha:T", title="Fecha de la ejecución del análisis", axis=alt.Axis(format="%d/%m", labelAngle=0, tickCount=8))
    y = alt.Y("valor:Q", title=titulo_y, scale=alt.Scale(domain=[0, 100]))
    color = alt.Color("Etapa:N", title="Etapa", sort=etapas,
                      scale=alt.Scale(domain=etapas, range=[COLORES_ETAPA[n] for n in etapas]))
    forma = alt.Shape("Etapa:N", title="Etapa", sort=etapas,
                      scale=alt.Scale(domain=etapas, range=[FORMAS_ETAPA[n] for n in etapas]))
    tooltip = [
        alt.Tooltip("Etapa:N"),
        alt.Tooltip("ejecucion:Q", title="Ejecución n.º"),
        alt.Tooltip("fecha_texto:N", title="Fecha"),
        alt.Tooltip("valor:Q", title=f"{nombre} promedio (%)", format=".1f"),
        alt.Tooltip("cambio:N", title="Cambio vs ejecución anterior de la etapa"),
        alt.Tooltip("issues:Q", title="Issues analizados"),
    ]
    # La línea usa todos los registros: un valor ausente la corta, para que el vacío se vea.
    lineas = alt.Chart(df).mark_line(strokeWidth=2.2).encode(x=x, y=y, color=color, detail="Etapa:N")
    puntos = alt.Chart(df[df["valor"].notna()]).mark_point(filled=True, size=80, opacity=1).encode(
        x=x, y=y, color=color, shape=forma, tooltip=tooltip,
    )
    capas = _capa_umbral(titulo_y) + lineas + puntos
    sin_valor = df[df["valor"].isna()].assign(y=2)
    if len(sin_valor):
        capas = capas + alt.Chart(sin_valor).mark_point(
            shape="cross", size=90, color=COLOR_UMBRAL, strokeWidth=2.2, filled=False,
        ).encode(
            x=alt.X("fecha:T", title="Fecha de la ejecución del análisis"), y=alt.Y("y:Q", title=titulo_y),
            tooltip=[alt.Tooltip("Etapa:N"), alt.Tooltip("fecha_texto:N", title="Fecha"),
                     alt.Tooltip("issues:Q", title="Issues analizados")],
        )
    return capas.properties(
        height=430,
        padding={"left": 5, "top": 5, "right": MARGEN_ROTULOS, "bottom": 5},
        title=_titulo(
            f"{nombre} a lo largo del tiempo",
            f"Cada punto es el promedio de {nombre.lower()} de los issues evaluados en una ejecución; una línea por etapa.",
        ),
    ).configure_legend(orient="bottom", titleFontSize=12, labelFontSize=12)


def grafico_avance_etapas(filas_grafico: dict, orden_etapas: list):
    """Issues de cada etapa por estado de revisión en GitLab (barras apiladas con cantidades)."""
    import altair as alt
    import pandas as pd

    estados = list(COLORES_ESTADO)
    registros = []
    for etapa, cantidades in filas_grafico.items():
        total = sum(cantidades.get(estado, 0) for estado in estados)
        acumulado = 0
        for estado in estados:
            cantidad = cantidades.get(estado, 0)
            if cantidad <= 0:
                continue
            registros.append({
                "Etapa": etapa, "Estado": estado, "Cantidad": cantidad,
                "inicio": acumulado, "fin": acumulado + cantidad, "medio": acumulado + cantidad / 2,
                "Porcentaje": round(cantidad / total * 100) if total else 0,
            })
            acumulado += cantidad
    df = pd.DataFrame(registros)
    x = alt.X("Etapa:N", sort=orden_etapas, title="Etapa del proyecto (en el orden del flujo)", axis=alt.Axis(labelAngle=0))
    barras = alt.Chart(df).mark_bar().encode(
        x=x,
        y=alt.Y("inicio:Q", title="Cantidad de issues abiertos", axis=alt.Axis(tickMinStep=1)), y2="fin:Q",
        color=alt.Color("Estado:N", title="Estado de revisión",
                        scale=alt.Scale(domain=estados, range=[COLORES_ESTADO[e] for e in estados])),
        tooltip=[alt.Tooltip("Etapa:N"), alt.Tooltip("Estado:N", title="Estado"),
                 alt.Tooltip("Cantidad:Q", title="Issues"), alt.Tooltip("Porcentaje:Q", title="% de la etapa", format=".0f")],
    )
    etiquetas = alt.Chart(df).mark_text(fontWeight="bold", fontSize=13).encode(
        x=x, y=alt.Y("medio:Q", title="Cantidad de issues abiertos"), text="Cantidad:Q",
        color=alt.condition(alt.FieldOneOfPredicate(field="Estado", oneOf=["Pendiente", "Sin estado"]),
                            alt.value("#33424F"), alt.value("white")),
    )
    return (barras + etiquetas).properties(
        height=400,
        title=_titulo(
            "Avance de las etapas según el estado de sus issues",
            "Cada barra es una etapa; sus colores indican cuántos de sus issues están revisados, por corregir o aún pendientes.",
        ),
    ).configure_legend(orient="bottom", titleFontSize=12, labelFontSize=12)


def grafico_trazabilidad(filas: list):
    """Cumplimiento de cada etapa: una barra por etapa que muestra qué % de lo que entrega la
    etapa anterior ya cubre. La barra completa es el 100 %; la parte verde, lo cubierto."""
    import altair as alt
    import pandas as pd

    registros = []
    for fila in filas:
        registros.append({
            "Etapa": fila["etiqueta"], "pct": fila["pct_cubierto"], "cero": 0, "cien": 100,
            "texto": f"{fila['pct_cubierto']:g} %  ·  {fila['cubierto']} de {fila['total']} {fila['elementos']}",
            "Cubierto": f"{fila['cubierto']} de {fila['total']} ({fila['pct_cubierto']:g} %)",
            "Requiere revisión o con fallo": fila["atencion"],
            "Pendiente o sin evaluar": fila["pendiente"],
            "Cubierto significa": fila["significado"],
        })
    df = pd.DataFrame(registros)
    orden = [f["etiqueta"] for f in filas]
    y = alt.Y("Etapa:N", sort=orden, title=None, scale=alt.Scale(paddingInner=0.35),
              axis=alt.Axis(labelLimit=320, labelFontSize=13, labelFontWeight="bold", ticks=False, domain=False))
    titulo_x = "% cubierto de lo que entrega la etapa anterior"
    x_eje = alt.Axis(values=[0, 20, 40, 60, 80, 100], labelExpr="datum.value + ' %'")
    escala_color = alt.Scale(domain=["Cubierto", "Sin cubrir"], range=["#2E9E5B", "#E3E9EF"])
    pista = alt.Chart(df.assign(Parte="Sin cubrir")).mark_bar(size=34).encode(
        x=alt.X("cero:Q", title=titulo_x, scale=alt.Scale(domain=[0, 100]), axis=x_eje), x2="cien:Q", y=y,
        color=alt.Color("Parte:N", title=None, scale=escala_color),
    )
    relleno = alt.Chart(df.assign(Parte="Cubierto")).mark_bar(size=34).encode(
        x=alt.X("cero:Q", title=titulo_x, scale=alt.Scale(domain=[0, 100]), axis=x_eje), x2="pct:Q", y=y,
        color=alt.Color("Parte:N", title=None, scale=escala_color),
        tooltip=[alt.Tooltip("Etapa:N"), alt.Tooltip("Cubierto:N", title="Cubierto"),
                 alt.Tooltip("Cubierto significa:N", title="Cubierto significa"),
                 alt.Tooltip("Requiere revisión o con fallo:Q", title="Requieren revisión o con fallo"),
                 alt.Tooltip("Pendiente o sin evaluar:Q", title="Pendientes o sin evaluar")],
    )
    # El número va dentro de la parte verde si es ancha; si no, justo a su derecha (sobre la parte gris).
    capas = pista + relleno
    dentro = df[df["pct"] >= 45]
    fuera = df[df["pct"] < 45]
    if len(dentro):
        capas = capas + alt.Chart(dentro).mark_text(align="right", dx=-10, fontWeight="bold", fontSize=13, color="white").encode(
            x=alt.X("pct:Q", scale=alt.Scale(domain=[0, 100])), y=y, text="texto:N")
    if len(fuera):
        capas = capas + alt.Chart(fuera).mark_text(align="left", dx=10, fontWeight="bold", fontSize=13, color="#1F5F3A").encode(
            x=alt.X("pct:Q", scale=alt.Scale(domain=[0, 100])), y=y, text="texto:N")
    return capas.properties(
        height=76 * len(filas) + 190,
        title=_titulo(
            "Cumplimiento de la trazabilidad por etapa",
            "Cada barra completa es el 100 % de lo que entrega la etapa anterior; la parte verde es lo que esta etapa ya cubre.",
        ),
    ).configure_legend(orient="bottom", titleFontSize=12, labelFontSize=12)
