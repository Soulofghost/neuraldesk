import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from app.config import DB_PATH

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            pass
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            tags TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_edges (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            weight REAL NOT NULL,
            relation_type TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (target_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
