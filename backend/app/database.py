import os
import json
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any, Optional, Dict
from app.config import DB_PATH, DATABASE_URL

logger = logging.getLogger("neuraldesk.database")

# PostgreSQL Connection Pool (lazy initialization)
_pg_pool = None

def is_postgres_configured() -> bool:
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        import psycopg2.pool
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # 1 to 10 connections for serverless concurrency
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=url)
    return _pg_pool

def adapt_query(query: str, is_postgres: bool = False) -> str:
    if not is_postgres:
        return query

    # Adapt SQLite's INSERT OR REPLACE for graph_edges to ANSI/Postgres ON CONFLICT
    if "INSERT OR REPLACE INTO graph_edges" in query:
        query = """INSERT INTO graph_edges (id, source_id, target_id, weight, relation_type)
VALUES (?, ?, ?, ?, ?)
ON CONFLICT (id) DO UPDATE SET
    source_id = EXCLUDED.source_id,
    target_id = EXCLUDED.target_id,
    weight = EXCLUDED.weight,
    relation_type = EXCLUDED.relation_type"""

    # Translate parameter placeholders from ? to %s for psycopg2
    return query.replace("?", "%s")

class PostgresCursorWrapper:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, query: str, params: Any = None):
        adapted = adapt_query(query, is_postgres=True)
        if params is not None:
            return self._cursor.execute(adapted, params)
        return self._cursor.execute(adapted)

    def executemany(self, query: str, params_list: Any):
        adapted = adapt_query(query, is_postgres=True)
        return self._cursor.executemany(adapted, params_list)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size: Optional[int] = None):
        return self._cursor.fetchmany(size)

    def __iter__(self):
        return iter(self._cursor)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        return self._cursor.close()

class PostgresConnectionWrapper:
    def __init__(self, raw_conn, from_pool: bool = False):
        self._conn = raw_conn
        self._from_pool = from_pool

    def cursor(self):
        import psycopg2.extras
        return PostgresCursorWrapper(self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor))

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if self._from_pool and _pg_pool is not None:
            try:
                _pg_pool.putconn(self._conn)
                return
            except Exception as e:
                logger.warning(f"Failed to return connection to pool: {e}")
        try:
            self._conn.close()
        except Exception:
            pass

    def execute(self, query: str, params: Any = None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

def get_raw_connection():
    if is_postgres_configured():
        try:
            pool = _get_pg_pool()
            raw_conn = pool.getconn()
            return PostgresConnectionWrapper(raw_conn, from_pool=True)
        except Exception as e:
            logger.warning(f"Connection pool unavailable, creating direct connection: {e}")
            import psycopg2
            url = DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            raw_conn = psycopg2.connect(url)
            return PostgresConnectionWrapper(raw_conn, from_pool=False)
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def init_db():
    if is_postgres_configured():
        conn = get_raw_connection()
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
        # Indexes for fast retrieval
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents (updated_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks (document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges (source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges (target_id)")
        conn.commit()
        conn.close()
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
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
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents (updated_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks (document_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges (source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges (target_id)")
        conn.commit()
        conn.close()

@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    conn = get_raw_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()
