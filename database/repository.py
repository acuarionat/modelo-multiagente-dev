import os
import json
import hashlib
from datetime import datetime

from database.connection import columnas_de_tabla, conectar

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database")
DB_PATH = os.path.join(DB_DIR, "database.db")

def inicializar_bd():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gitlab_iid INTEGER UNIQUE,
            content_hash TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gitlab_iid INTEGER,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            quality_index REAL,
            security_index REAL,
            verdict TEXT,
            execution_time REAL,
            observations TEXT,
            stage TEXT DEFAULT 'requerimientos'
        )
    ''')

    # Bases creadas antes de registrar la etapa: todo lo guardado entonces es de Requerimientos.
    columnas_historial = columnas_de_tabla(conn, 'history')
    if 'stage' not in columnas_historial:
        cursor.execute("ALTER TABLE history ADD COLUMN stage TEXT DEFAULT 'requerimientos'")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cache_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE,
            schema_version TEXT,
            central_json TEXT,
            quality_json TEXT,
            security_json TEXT,
            eval_json TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stage_snapshots (
            stage TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matrix_versions (
            stage TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            major INTEGER NOT NULL,
            minor INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def limpiar_datos_seguimiento():
    """Limpia las tablas para reiniciar el proyecto sin borrar la BD."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM issues')
    cursor.execute('DELETE FROM history')
    cursor.execute('DELETE FROM cache_results')
    cursor.execute('DELETE FROM matrix_versions')
    conn.commit()
    conn.close()
    limpiar_estado_etapas()

def guardar_estado_etapa(stage: str, payload: dict):
    """Persiste el último resultado de análisis de una etapa (Requerimientos, Diseño, Codificación, Pruebas)."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO stage_snapshots (stage, payload, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(stage) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP
    ''', (stage, json.dumps(payload, ensure_ascii=False, default=str)))
    conn.commit()
    conn.close()

def cargar_estado_etapa(stage: str):
    """Recupera el último resultado de análisis persistido de una etapa, o None si no existe."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT payload FROM stage_snapshots WHERE stage = ?', (stage,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def cargar_matriz_base(etapa: str):
    """Filas de la matriz de entrada tal como estaban en la última carga de esa etapa
    (la 'versión anterior' contra la que se listan los cambios), o None si no hay."""
    persistido = cargar_estado_etapa(f"matriz_base_{etapa}")
    return persistido.get("filas") if persistido else None

def guardar_matriz_base(etapa: str, filas: list):
    """Registra la matriz de entrada recién cargada como nueva 'versión anterior'."""
    guardar_estado_etapa(f"matriz_base_{etapa}", {"filas": filas})

def obtener_fecha_estado_etapa(stage: str):
    """Fecha ('AAAA-MM-DD HH:MM:SS', UTC) en que se persistió el último resultado de una etapa, o None."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT updated_at FROM stage_snapshots WHERE stage = ?', (stage,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def limpiar_estado_etapas():
    """Borra los resultados de análisis persistidos de todas las etapas."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM stage_snapshots')
    conn.commit()
    conn.close()

def calcular_hash_issue(issue_data: dict) -> str:
    """Calcula el hash del issue tomando en cuenta los campos más relevantes."""
    # Extraer campos clave de issue_data ya procesado por issue_mapper
    fields_to_hash = [
        issue_data.get("titulo", ""),
        issue_data.get("actor", ""),
        issue_data.get("funcionalidad", ""),
        issue_data.get("objetivo", ""),
        json.dumps(issue_data.get("criterios_aceptacion", [])),
        json.dumps(issue_data.get("restricciones", [])),
        issue_data.get("prioridad", "")
    ]
    
    content_to_hash = "||".join(fields_to_hash)
    return hashlib.sha256(content_to_hash.encode('utf-8')).hexdigest()

def obtener_estado_issue(gitlab_iid: int):
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT status, content_hash FROM issues WHERE gitlab_iid = ?', (gitlab_iid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"status": row[0], "content_hash": row[1]}
    return None

def insertar_o_actualizar_issue(gitlab_iid: int, content_hash: str, status: str):
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM issues WHERE gitlab_iid = ?', (gitlab_iid,))
    if cursor.fetchone():
        cursor.execute('''
            UPDATE issues 
            SET content_hash = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE gitlab_iid = ?
        ''', (content_hash, status, gitlab_iid))
    else:
        cursor.execute('''
            INSERT INTO issues (gitlab_iid, content_hash, status)
            VALUES (?, ?, ?)
        ''', (gitlab_iid, content_hash, status))
    conn.commit()
    conn.close()

def guardar_historial(gitlab_iid: int, quality_index: float, security_index: float, verdict: str, execution_time: float, observations: str, stage: str = "requerimientos"):
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO history (gitlab_iid, quality_index, security_index, verdict, execution_time, observations, stage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (gitlab_iid, quality_index, security_index, verdict, execution_time, observations, stage))
    conn.commit()
    conn.close()

def obtener_historial(limite: int | None = None) -> list:
    """Lectura de solo lectura del historial de análisis (calidad, seguridad,
    veredicto, tiempo de ejecución) por Issue y por corrida, ordenado del más
    antiguo al más reciente. Pensado para el panel/dashboard del proyecto."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    query = (
        'SELECT gitlab_iid, analysis_date, quality_index, security_index, '
        'verdict, execution_time, observations, stage FROM history '
        'ORDER BY analysis_date ASC, id ASC'
    )
    if limite:
        cursor.execute(query + ' LIMIT ?', (int(limite),))
    else:
        cursor.execute(query)
    filas = cursor.fetchall()
    conn.close()
    return [
        {
            "gitlab_iid": fila[0],
            "analysis_date": fila[1],
            "quality_index": fila[2],
            "security_index": fila[3],
            "verdict": fila[4],
            "execution_time": fila[5],
            "observations": fila[6],
            "stage": fila[7] or "requerimientos",
        }
        for fila in filas
    ]


def obtener_versiones_matrices() -> list:
    """Lectura de solo lectura de la versión actual de cada matriz de trazabilidad
    (etapa, vMAJOR.MINOR y última modificación), ordenada por etapa."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT stage, major, minor, updated_at FROM matrix_versions ORDER BY major ASC')
    filas = cursor.fetchall()
    conn.close()
    return [
        {
            "stage": fila[0],
            "version": f"v{fila[1]}.{fila[2]}",
            "updated_at": fila[3],
        }
        for fila in filas
    ]


def guardar_cache(content_hash: str, schema_version: str, central_json: dict, quality_json: dict, security_json: dict, eval_json: dict):
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cache_results (content_hash, schema_version, central_json, quality_json, security_json, eval_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(content_hash) DO UPDATE SET schema_version=excluded.schema_version,
            central_json=excluded.central_json, quality_json=excluded.quality_json,
            security_json=excluded.security_json, eval_json=excluded.eval_json
    ''', (content_hash, schema_version, json.dumps(central_json), json.dumps(quality_json), json.dumps(security_json), json.dumps(eval_json)))
    conn.commit()
    conn.close()

def obtener_cache(content_hash: str, schema_version: str):
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT central_json, quality_json, security_json, eval_json 
        FROM cache_results 
        WHERE content_hash = ? AND schema_version = ?
    ''', (content_hash, schema_version))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "central_init": json.loads(row[0]),
            "quality_report": json.loads(row[1]),
            "security_report": json.loads(row[2]),
            "evaluation": json.loads(row[3])
        }
    return None

def _hash_filas_matriz(filas: list) -> str:
    """Hash estable del contenido de una matriz de trazabilidad. Excluye las
    columnas volátiles (fechas de generación) para que la versión cambie
    únicamente ante cambios reales de contenido y no por la fecha del día."""
    normalizadas = []
    for fila in filas or []:
        if isinstance(fila, dict):
            normalizadas.append({
                str(clave): "" if valor is None else str(valor)
                for clave, valor in fila.items()
                if "fecha" not in str(clave).lower()
            })
        else:
            normalizadas.append(fila)
    serial = json.dumps(normalizadas, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serial.encode('utf-8')).hexdigest()


def obtener_version_matriz(stage: str, filas: list, major: int) -> str:
    """Devuelve la versión 'vMAJOR.MINOR' de la matriz de trazabilidad de una
    etapa y persiste su estado. El MINOR se incrementa solo cuando el contenido
    cambia respecto de la última publicación registrada; si el contenido es
    idéntico, la versión se mantiene. El MAJOR identifica la etapa
    (1=Requerimientos, 2=Diseño, 3=Codificación, 4=Pruebas)."""
    content_hash = _hash_filas_matriz(filas)
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content_hash, major, minor FROM matrix_versions WHERE stage = ?', (stage,))
    row = cursor.fetchone()
    if row is None:
        minor = 0
    else:
        prev_hash, prev_major, prev_minor = row
        if prev_major != major:
            minor = 0
        elif prev_hash == content_hash:
            minor = prev_minor
        else:
            minor = prev_minor + 1
    cursor.execute('''
        INSERT INTO matrix_versions (stage, content_hash, major, minor, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(stage) DO UPDATE SET content_hash=excluded.content_hash,
            major=excluded.major, minor=excluded.minor, updated_at=CURRENT_TIMESTAMP
    ''', (stage, content_hash, major, minor))
    conn.commit()
    conn.close()
    return f"v{major}.{minor}"


def leer_version_matriz(stage: str) -> str | None:
    """Devuelve la versión 'vMAJOR.MINOR' actualmente registrada para la matriz de
    trazabilidad de una etapa, SIN modificarla. Retorna None si esa matriz aún no
    se ha publicado. Pensada para mostrar la versión en documentos/reportes sin
    provocar ningún incremento."""
    conn = conectar(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT major, minor FROM matrix_versions WHERE stage = ?', (stage,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return f"v{row[0]}.{row[1]}"


# Asegurar que se crea la BD al importar este módulo
inicializar_bd()
