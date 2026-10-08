"""Copia los datos guardados en el SQLite local a la base PostgreSQL (DATABASE_URL).

Uso (una sola vez, desde la carpeta del proyecto, con DATABASE_URL definida en
el entorno o en el .env):

    python scripts/migrar_sqlite_a_postgres.py [ruta/al/database.db]

- El SQLite se abre en modo SOLO LECTURA: no se modifica ni se borra nada.
- Conserva los identificadores y las fechas originales.
- Es seguro repetirlo: una tabla que ya tiene datos en Postgres no se toca.
"""
import os
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")

from database.connection import conectar, usa_postgres

TABLAS = (
    "issues", "history", "cache_results", "stage_snapshots",
    "matrix_versions", "project_configuration",
)
CON_SECUENCIA = ("issues", "history", "cache_results")


def main():
    if not usa_postgres():
        sys.exit("DATABASE_URL no está definida: no hay base PostgreSQL a la que migrar.")

    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "database" / "database.db"
    if not ruta.is_file():
        sys.exit(f"No existe el archivo SQLite: {ruta}")

    # Crea las tablas en Postgres (repository y project_config las inicializan).
    import database.repository  # noqa: F401
    import project_config

    project_config.load_project_config()

    origen = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
    destino = conectar(str(ruta))
    resumen = []
    try:
        for tabla in TABLAS:
            existe = origen.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
            ).fetchone()
            if not existe:
                resumen.append((tabla, 0, 0, "no existe en el origen"))
                continue
            columnas = [f[1] for f in origen.execute(f"PRAGMA table_info({tabla})")]
            filas = origen.execute(f"SELECT {', '.join(columnas)} FROM {tabla}").fetchall()
            previas = destino.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            if previas:
                resumen.append((tabla, len(filas), previas, "omitida: ya tiene datos"))
                continue
            marcadores = ", ".join("?" for _ in columnas)
            for fila in filas:
                destino.execute(
                    f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcadores})", fila
                )
            if tabla in CON_SECUENCIA and filas:
                destino.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                    f"(SELECT MAX(id) FROM {tabla}))"
                )
            copiadas = destino.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            resumen.append((tabla, len(filas), copiadas, "copiada"))
        destino.commit()
    except Exception:
        destino.rollback()
        raise
    finally:
        destino.close()
        origen.close()

    print(f"{'tabla':24} {'origen':>7} {'destino':>8}  resultado")
    for tabla, n_origen, n_destino, nota in resumen:
        print(f"{tabla:24} {n_origen:>7} {n_destino:>8}  {nota}")


if __name__ == "__main__":
    main()
