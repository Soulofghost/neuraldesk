from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from app.database import get_db_connection, is_postgres_configured
from app.auth import require_admin

router = APIRouter(prefix="/admin", tags=["Administration & SaaS Control"])

@router.get("/overview")
def get_admin_overview(admin: Dict[str, Any] = Depends(require_admin)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as cnt FROM users")
        user_count = int(cursor.fetchone()["cnt"] or 0)

        cursor.execute("SELECT count(*) as cnt FROM documents")
        doc_count = int(cursor.fetchone()["cnt"] or 0)

        cursor.execute("SELECT COALESCE(SUM(file_size), 0) as total_size FROM documents")
        storage = int(cursor.fetchone()["total_size"] or 0)

        cursor.execute("SELECT plan, count(*) as cnt FROM users GROUP BY plan")
        plans = {str(r["plan"]): int(r["cnt"]) for r in cursor.fetchall()}

        return {
            "users_count": user_count,
            "documents_count": doc_count,
            "total_storage_bytes": storage,
            "plan_breakdown": plans,
            "database_engine": "PostgreSQL (Neon/Supabase)" if is_postgres_configured() else "SQLite WAL",
            "serverless_status": "optimal",
            "version": "2.0.0"
        }

@router.put("/users/{user_id}/plan")
def update_user_plan(user_id: str, plan: str, admin: Dict[str, Any] = Depends(require_admin)):
    allowed_plans = {"free", "pro", "enterprise"}
    if plan not in allowed_plans:
        raise HTTPException(status_code=400, detail=f"Invalid plan. Allowed: {allowed_plans}")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET plan = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan, user_id))
        conn.commit()
        return {"user_id": user_id, "updated_plan": plan}

@router.get("/audit-logs")
def get_audit_logs(limit: int = 50, admin: Dict[str, Any] = Depends(require_admin)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, workspace_id, user_id, action, details, created_at
            FROM activity_logs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [
            {
                "id": str(r["id"]),
                "workspace_id": str(r["workspace_id"]),
                "user_id": str(r["user_id"]),
                "action": str(r["action"]),
                "details": str(r["details"] or ""),
                "created_at": str(r["created_at"])
            }
            for r in cursor.fetchall()
        ]
