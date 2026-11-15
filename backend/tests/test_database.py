import os
from app.database import adapt_query, is_postgres_configured

def test_adapt_query():
    # SQLite mode should preserve query
    sqlite_query = "SELECT * FROM documents WHERE id = ?"
    assert adapt_query(sqlite_query, is_postgres=False) == sqlite_query

    # Postgres mode should translate ? to %s
    pg_query = adapt_query(sqlite_query, is_postgres=True)
    assert pg_query == "SELECT * FROM documents WHERE id = %s"

    # Test INSERT OR REPLACE conversion
    replace_query = """INSERT OR REPLACE INTO graph_edges (id, source_id, target_id, weight, relation_type)
                VALUES (?, ?, ?, ?, ?)"""
    adapted = adapt_query(replace_query, is_postgres=True)
    assert "ON CONFLICT (id) DO UPDATE" in adapted
    assert "%s" in adapted

def test_is_postgres_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    
    # Reload or check
    from app import database
    database.DATABASE_URL = None
    assert not database.is_postgres_configured()

    database.DATABASE_URL = "postgresql://user:pass@host/db"
    assert database.is_postgres_configured()

    database.DATABASE_URL = "postgres://user:pass@host/db"
    assert database.is_postgres_configured()
    
    database.DATABASE_URL = None
