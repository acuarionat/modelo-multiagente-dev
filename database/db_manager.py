import sqlite3
import os
import json
from datetime import datetime
from core.config import DB_PATH

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Inicializa la base de datos de trazabilidad."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla principal de la ejecución/ticket
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS execution_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT,
            timestamp DATETIME,
            status TEXT,
            final_decision TEXT,
            final_report TEXT
        )
    ''')
    
    # Tabla de resultados de los agentes paralelos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER,
            agent_name TEXT,
            timestamp DATETIME,
            raw_output TEXT,
            FOREIGN KEY (execution_id) REFERENCES execution_logs(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def log_execution(ticket_id: str):
    """Crea una nueva ejecución y devuelve su ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO execution_logs (ticket_id, timestamp, status)
        VALUES (?, ?, ?)
    ''', (ticket_id, datetime.now(), "IN_PROGRESS"))
    
    execution_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return execution_id

def log_agent_result(execution_id: int, agent_name: str, raw_output: str):
    """Guarda el resultado crudo de un agente."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Si el output no es un string, lo serializamos a JSON
    if not isinstance(raw_output, str):
        raw_output = json.dumps(raw_output)
        
    cursor.execute('''
        INSERT INTO agent_results (execution_id, agent_name, timestamp, raw_output)
        VALUES (?, ?, ?, ?)
    ''', (execution_id, agent_name, datetime.now(), raw_output))
    
    conn.commit()
    conn.close()

def update_execution_final(execution_id: int, status: str, final_decision: str, final_report: str):
    """Actualiza la ejecución con el veredicto final."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE execution_logs
        SET status = ?, final_decision = ?, final_report = ?
        WHERE id = ?
    ''', (status, final_decision, final_report, execution_id))
    
    conn.commit()
    conn.close()
