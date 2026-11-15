import os
import json
import sqlite3
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any, Optional, Dict
from app.config import DB_PATH, DATABASE_URL

logger = logging.getLogger("neuraldesk.database")

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
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=url)
    return _pg_pool

def adapt_query(query: str, is_postgres: bool = False) -> str:
    if not is_postgres:
        return query

    # Adapt SQLite's INSERT OR REPLACE for graph_edges and shared_links
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
    conn = get_raw_connection()
    is_pg = is_postgres_configured()
    cursor = conn.cursor()

    if not is_pg:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
            except Exception:
                pass
        conn.execute("PRAGMA foreign_keys = ON")

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'pro',
            avatar_url TEXT DEFAULT '',
            preferences TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Workspaces Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner_id TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. Workspace Members Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_members (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'editor',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Documents Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            owner_id TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            tags TEXT NOT NULL DEFAULT '[]',
            file_type TEXT NOT NULL DEFAULT 'text',
            file_size INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            is_trash INTEGER DEFAULT 0,
            folder TEXT DEFAULT '',
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Safe Schema Migrations for existing documents table
    doc_columns = [
        ("workspace_id", "TEXT NOT NULL DEFAULT 'default'"),
        ("owner_id", "TEXT NOT NULL DEFAULT 'system'"),
        ("file_type", "TEXT NOT NULL DEFAULT 'text'"),
        ("file_size", "INTEGER DEFAULT 0"),
        ("is_favorite", "INTEGER DEFAULT 0"),
        ("is_archived", "INTEGER DEFAULT 0"),
        ("is_trash", "INTEGER DEFAULT 0"),
        ("folder", "TEXT DEFAULT ''"),
        ("version", "INTEGER DEFAULT 1")
    ]
    for col_name, col_type in doc_columns:
        try:
            cursor.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
            conn.commit()
        except Exception:
            # Column already exists
            pass

    # 5. Document Chunks Table
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

    # 6. Graph Edges Table
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

    # 7. AI Conversations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 8. AI Messages Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE
        )
    """)

    # 9. Notes Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            owner_id TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            is_pinned INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            linked_document_id TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 10. Tasks Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            owner_id TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo',
            priority TEXT NOT NULL DEFAULT 'medium',
            due_date TEXT DEFAULT NULL,
            linked_document_id TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 11. Comments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT 'system',
            author_name TEXT NOT NULL DEFAULT 'Team Member',
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    # 12. Notifications Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'system',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 13. Activity Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'system',
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 14. Shared Links Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_links (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            permission TEXT NOT NULL DEFAULT 'view',
            expires_at TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    # 15. Storage Folders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_folders (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'system',
            parent_id TEXT DEFAULT NULL,
            name TEXT NOT NULL,
            color TEXT DEFAULT '#e6a23c',
            is_trash INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 16. Storage Files Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storage_files (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL DEFAULT 'default',
            user_id TEXT NOT NULL DEFAULT 'system',
            folder_id TEXT DEFAULT NULL,
            name TEXT NOT NULL,
            original_name TEXT NOT NULL,
            storage_key TEXT UNIQUE NOT NULL,
            storage_provider TEXT NOT NULL DEFAULT 'r2',
            file_size INTEGER NOT NULL DEFAULT 0,
            mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
            file_extension TEXT NOT NULL DEFAULT '',
            checksum TEXT DEFAULT '',
            is_favorite INTEGER DEFAULT 0,
            is_trash INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            metadata TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 17. File Shares Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_shares (
            id TEXT PRIMARY KEY,
            file_id TEXT DEFAULT NULL,
            folder_id TEXT DEFAULT NULL,
            token TEXT UNIQUE NOT NULL,
            access_type TEXT NOT NULL DEFAULT 'public_read',
            password_hash TEXT DEFAULT NULL,
            expires_at TEXT DEFAULT NULL,
            download_count INTEGER DEFAULT 0,
            created_by TEXT NOT NULL DEFAULT 'system',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 18. File Versions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_versions (
            id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            storage_key TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            checksum TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 19. Document Versions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Performance Indexes
    indexes = [
        ("idx_documents_category", "documents (category)"),
        ("idx_documents_workspace", "documents (workspace_id)"),
        ("idx_documents_updated", "documents (updated_at DESC)"),
        ("idx_chunks_doc_id", "document_chunks (document_id)"),
        ("idx_graph_edges_source", "graph_edges (source_id)"),
        ("idx_graph_edges_target", "graph_edges (target_id)"),
        ("idx_notes_workspace", "notes (workspace_id)"),
        ("idx_tasks_workspace", "tasks (workspace_id)"),
        ("idx_ai_messages_conv", "ai_messages (conversation_id)"),
        ("idx_activity_workspace", "activity_logs (workspace_id)"),
        ("idx_storage_files_ws", "storage_files (workspace_id)"),
        ("idx_storage_files_folder", "storage_files (folder_id)"),
        ("idx_storage_files_trash", "storage_files (is_trash)"),
        ("idx_storage_folders_ws", "storage_folders (workspace_id)"),
        ("idx_file_shares_tok", "file_shares (token)"),
        ("idx_doc_versions_doc", "document_versions (document_id)")
    ]
    for idx_name, idx_def in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
        except Exception:
            pass

    # Seed Default Workspace if empty
    cursor.execute("SELECT id FROM workspaces WHERE id = 'default'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO workspaces (id, name, description, owner_id, is_default)
            VALUES ('default', 'Primary Workspace', 'Default neural knowledge base workspace', 'system', 1)
        """)

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
