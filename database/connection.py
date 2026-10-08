"""Acceso a la base de datos del proyecto.

Si existe la variable de entorno DATABASE_URL se usa PostgreSQL (persistencia
externa, p. ej. Neon o Supabase); si no, se usa el archivo SQLite local de
siempre. El resto del código no cambia: pide `conectar(ruta_sqlite)` y trabaja
con la misma interfaz (cursor/execute/commit/close, marcadores `?`).
"""
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
_CAMBIOS_SQL = (
    (re.compile(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.I), "SERIAL PRIMARY KEY"),
    (re.compile(r"\bREAL\b", re.I), "DOUBLE PRECISION"),
    (re.compile(r"\bDATETIME\b", re.I), "TIMESTAMP"),
)

_pool = None
_pool_lock = threading.Lock()


def url_postgres() -> str | None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    return url or None


def usa_postgres() -> bool:
    return url_postgres() is not None


def traducir_sql(sql: str, con_parametros: bool = True) -> str:
    """Adapta SQL escrito para SQLite (marcadores `?`, AUTOINCREMENT, REAL) a PostgreSQL."""
    for patron, nuevo in _CAMBIOS_SQL:
        sql = patron.sub(nuevo, sql)
    if con_parametros:
        sql = sql.replace("%", "%%").replace("?", "%s")
    return sql


def _fila(fila):
    """SQLite entrega fechas como texto 'AAAA-MM-DD HH:MM:SS'; se mantiene ese formato."""
    if fila is None:
        return None
    return tuple(v.strftime(_FORMATO_FECHA) if isinstance(v, datetime) else v for v in fila)


class _CursorPG:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        if params is None:
            self._cursor.execute(traducir_sql(sql, con_parametros=False))
        else:
            self._cursor.execute(traducir_sql(sql), tuple(params))
        return self

    def fetchone(self):
        return _fila(self._cursor.fetchone())

    def fetchall(self):
        return [_fila(f) for f in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    def __getattr__(self, nombre):
        return getattr(self._cursor, nombre)


class ConexionPG:
    """Envuelve una conexión PostgreSQL del pool con la interfaz de sqlite3.Connection."""

    def __init__(self, crudo, pool):
        self._crudo = crudo
        self._pool = pool
        self._liberada = False

    def cursor(self):
        return _CursorPG(self._crudo.cursor())

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)

    def commit(self):
        self._crudo.commit()

    def rollback(self):
        self._crudo.rollback()

    def close(self):
        self._liberar()

    def _liberar(self):
        if self._liberada:
            return
        self._liberada = True
        try:
            if not self._crudo.closed:
                self._crudo.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._crudo)
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        if tipo is None:
            self._crudo.commit()
        else:
            self._crudo.rollback()
        self._liberar()
        return False

    def __del__(self):
        self._liberar()


def _obtener_pool(url: str):
    global _pool
    with _pool_lock:
        if _pool is None:
            from psycopg2.pool import ThreadedConnectionPool

            _pool = ThreadedConnectionPool(
                1, 8, url,
                connect_timeout=15,
                keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
            )
            logger.info("Persistencia: PostgreSQL (DATABASE_URL).")
        return _pool


def _tomar_conexion(url: str):
    """Entrega una conexión viva; descarta las que el servidor cerró por inactividad."""
    pool = _obtener_pool(url)
    for _ in range(3):
        crudo = pool.getconn()
        try:
            if crudo.closed:
                raise OSError("conexión cerrada")
            with crudo.cursor() as cursor:
                cursor.execute("SELECT 1")
            crudo.rollback()
            return crudo
        except Exception:
            pool.putconn(crudo, close=True)
    return pool.getconn()


def conectar(ruta_sqlite: str):
    """Conexión a PostgreSQL si hay DATABASE_URL; de lo contrario, SQLite en `ruta_sqlite`."""
    url = url_postgres()
    if url:
        return ConexionPG(_tomar_conexion(url), _obtener_pool(url))
    return sqlite3.connect(ruta_sqlite)


def columnas_de_tabla(conexion, tabla: str) -> set:
    if isinstance(conexion, ConexionPG):
        cursor = conexion.cursor().execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ?", (tabla,),
        )
        return {fila[0] for fila in cursor.fetchall()}
    return {fila[1] for fila in conexion.execute(f"PRAGMA table_info({tabla})")}
