import sqlite3
import os
import json
import hashlib
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database")
DB_PATH = os.path.join(DB_DIR, "database.db")

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    conn = sqlite3.connect(DB_PATH)
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
            observations TEXT
        )
    ''')
    
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
    
    conn.commit()
    conn.close()

def clear_tracking_data():
    """Limpia las tablas para reiniciar el proyecto sin borrar la BD."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM issues')
    cursor.execute('DELETE FROM history')
    cursor.execute('DELETE FROM cache_results')
    conn.commit()
    conn.close()

def compute_issue_hash(issue_data: dict) -> str:
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

def get_issue_status(gitlab_iid: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT status, content_hash FROM issues WHERE gitlab_iid = ?', (gitlab_iid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"status": row[0], "content_hash": row[1]}
    return None

def upsert_issue(gitlab_iid: int, content_hash: str, status: str):
    conn = sqlite3.connect(DB_PATH)
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

def save_history(gitlab_iid: int, quality_index: float, security_index: float, verdict: str, execution_time: float, observations: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO history (gitlab_iid, quality_index, security_index, verdict, execution_time, observations)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (gitlab_iid, quality_index, security_index, verdict, execution_time, observations))
    conn.commit()
    conn.close()

def save_cache(content_hash: str, schema_version: str, central_json: dict, quality_json: dict, security_json: dict, eval_json: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO cache_results (content_hash, schema_version, central_json, quality_json, security_json, eval_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (content_hash, schema_version, json.dumps(central_json), json.dumps(quality_json), json.dumps(security_json), json.dumps(eval_json)))
    conn.commit()
    conn.close()

def get_cache(content_hash: str, schema_version: str):
    conn = sqlite3.connect(DB_PATH)
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

# Asegurar que se crea la BD al importar este módulo
init_db()
