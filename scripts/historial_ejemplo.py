"""Historial de ejemplo para el seguimiento de calidad y seguridad del panel del proyecto.

Diseño, Codificación y Pruebas solo conservaban su último análisis, lo que deja una sola
ejecución por etapa en el gráfico de seguimiento. Este script agrega ejecuciones ANTERIORES
de ejemplo (simuladas) que desembocan en el último resultado real de cada etapa:

- Los issues son los reales de cada etapa y su último resultado es el real, importado del
  último resultado guardado.
- Las ejecuciones anteriores son simuladas: cada issue mejora hacia su valor final con
  pequeñas variaciones y algún retroceso, de modo que los issues débiles hoy ya lo eran antes.
- Todas las filas agregadas quedan marcadas en la columna `observations`
  ([EJEMPLO] o [IMPORTADO]) para poder retirarlas.

Uso (desde la raíz del proyecto):
    python scripts/historial_ejemplo.py cargar   # agrega el historial (repetirlo no duplica)
    python scripts/historial_ejemplo.py quitar   # retira todo lo que agregó este script

Solo toca las etapas que no tienen historial propio (filas no marcadas por este script).
"""

import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.dashboard_charts import historial_desde_resultados
from core.umbral_aprobacion import UMBRAL_APROBACION
from database import repository

MARCA_EJEMPLO = "[EJEMPLO] Ejecución simulada para demostración."
MARCA_IMPORTADO = "[IMPORTADO] Último resultado guardado de la etapa."

# Fechas (UTC) de las ejecuciones anteriores al último resultado real de cada etapa.
FECHAS_PREVIAS = {
    "diseno": ["2026-08-14 00:45:00", "2026-08-20 11:03:00", "2026-09-10 15:33:00", "2026-09-25 17:39:00", "2026-10-03 22:42:00"],
    "codificacion": ["2026-08-16 23:42:00", "2026-08-20 11:10:00", "2026-09-10 15:03:00", "2026-09-25 18:10:00", "2026-10-03 22:40:00"],
    "pruebas": ["2026-09-22 14:20:00", "2026-09-27 20:05:00", "2026-10-02 21:30:00", "2026-10-03 23:10:00"],
}
# Ejecución (índice dentro de las previas) en la que algunos issues retroceden, y
# ejecución en la que el agente de seguridad no obtuvo índice evaluable (vacío en la línea).
RETROCESO = {"diseno": 3, "codificacion": 2, "pruebas": 2}
SEGURIDAD_SIN_INDICE = {"diseno": 1}
MINUTOS_ENTRE_ISSUES = 3


def _conectar():
    return sqlite3.connect(repository.DB_PATH)


def quitar() -> int:
    conn = _conectar()
    cursor = conn.execute(
        "DELETE FROM history WHERE observations LIKE '[EJEMPLO]%' OR observations LIKE '[IMPORTADO]%'"
    )
    conn.commit()
    conn.close()
    return cursor.rowcount


def _trayectoria(final, n_previas, rng, brecha_inicial, retroceso_en):
    """Valores de las `n_previas` ejecuciones anteriores de un issue que termina en `final`."""
    if final is None:
        return [None] * n_previas
    valores = []
    for k in range(n_previas):
        avance = (k + 1) / (n_previas + 1)
        valor = final - brecha_inicial * (1 - avance) + rng.uniform(-0.03, 0.03)
        if k == retroceso_en:
            valor -= rng.uniform(0.08, 0.18)
        valores.append(round(min(1.0, max(0.2, valor)), 3))
    return valores


def _veredicto(calidad, seguridad):
    return "CONFORME" if min(calidad, seguridad) > UMBRAL_APROBACION else "CORREGIR"


def cargar() -> None:
    quitar()  # repetir el comando no duplica filas
    conn = _conectar()
    insertar = (
        "INSERT INTO history (gitlab_iid, analysis_date, quality_index, security_index, verdict, "
        "execution_time, observations, stage) VALUES (?, ?, ?, ?, ?, NULL, ?, ?)"
    )
    for etapa, fechas in FECHAS_PREVIAS.items():
        propias = conn.execute("SELECT COUNT(*) FROM history WHERE stage = ?", (etapa,)).fetchone()[0]
        if propias:
            print(f"{etapa}: ya tiene historial propio ({propias} filas); no se modifica.")
            continue
        finales = historial_desde_resultados(
            etapa, repository.cargar_estado_etapa(etapa), repository.obtener_fecha_estado_etapa(etapa),
        )
        if not finales:
            print(f"{etapa}: sin último resultado guardado; no hay a qué converger. Se omite.")
            continue

        rng = random.Random(f"historial-ejemplo-{etapa}")  # reproducible
        n = len(fechas)
        # Brecha inicial por issue: los que hoy están bajos no partieron de tan lejos.
        brechas = {
            f["gitlab_iid"]: (
                min(0.35, max(0.10, (f["quality_index"] or 0.5) - 0.25)),
                min(0.35, max(0.10, (f["security_index"] or 0.5) - 0.25)),
            )
            for f in finales
        }
        trayectorias = {}
        for f in finales:
            iid = f["gitlab_iid"]
            retrocede = f["gitlab_iid"] % 3 != 0  # la mayoría de los issues, no todos
            r = RETROCESO[etapa] if retrocede else -1
            trayectorias[iid] = (
                _trayectoria(f["quality_index"], n, rng, brechas[iid][0], r),
                _trayectoria(f["security_index"], n, rng, brechas[iid][1], r),
            )

        for k, fecha_texto in enumerate(fechas):
            inicio = datetime.strptime(fecha_texto, "%Y-%m-%d %H:%M:%S")
            for orden, f in enumerate(finales):
                iid = f["gitlab_iid"]
                calidad = trayectorias[iid][0][k]
                seguridad = None if SEGURIDAD_SIN_INDICE.get(etapa) == k else trayectorias[iid][1][k]
                fecha = (inicio + timedelta(minutes=MINUTOS_ENTRE_ISSUES * orden)).strftime("%Y-%m-%d %H:%M:%S")
                veredicto = _veredicto(calidad, seguridad if seguridad is not None else calidad)
                conn.execute(insertar, (iid, fecha, calidad, seguridad, veredicto, MARCA_EJEMPLO, etapa))
        for f in finales:  # el último resultado, real, cierra la serie
            conn.execute(insertar, (
                f["gitlab_iid"], f["analysis_date"], f["quality_index"], f["security_index"],
                f["verdict"], MARCA_IMPORTADO, etapa,
            ))
        print(f"{etapa}: {n} ejecuciones de ejemplo + el último resultado real ({len(finales)} issues).")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion == "cargar":
        cargar()
    elif accion == "quitar":
        print(f"Filas retiradas: {quitar()}")
    else:
        print(__doc__)
        sys.exit(1)
