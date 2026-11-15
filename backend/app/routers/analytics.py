from fastapi import APIRouter, Depends, Query
from typing import Dict, Any, Optional
from app.database import get_db_connection
from app.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Advanced Analytics & Dashboard"])

@router.get("")
def get_dashboard_analytics(workspace_id: Optional[str] = Query(None)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        ws_filter = " WHERE is_trash = 0"
        params = []
        if workspace_id and workspace_id != "all":
            ws_filter += " AND workspace_id = ?"
            params.append(workspace_id)

        # 1. Total Documents
        cursor.execute(f"SELECT count(*) as cnt, COALESCE(SUM(file_size), 0) as total_size FROM documents{ws_filter}", tuple(params))
        doc_stats = cursor.fetchone()
        total_docs = int(doc_stats["cnt"] or 0)
        total_storage = int(doc_stats["total_size"] or 0)

        # 2. Total Workspaces
        cursor.execute("SELECT count(*) as cnt FROM workspaces")
        total_workspaces = int(cursor.fetchone()["cnt"] or 1)

        # 3. Total Chunks
        cursor.execute("SELECT count(*) as cnt FROM document_chunks")
        total_chunks = int(cursor.fetchone()["cnt"] or 0)

        # 4. Total Notes
        cursor.execute("SELECT count(*) as cnt FROM notes")
        total_notes = int(cursor.fetchone()["cnt"] or 0)

        # 5. Total Tasks & Status Breakdown
        cursor.execute("SELECT status, count(*) as cnt FROM tasks GROUP BY status")
        task_rows = cursor.fetchall()
        task_status_map = {"todo": 0, "in_progress": 0, "done": 0}
        total_tasks = 0
        for tr in task_rows:
            task_status_map[tr["status"]] = int(tr["cnt"])
            total_tasks += int(tr["cnt"])

        # 6. Category Distribution
        cursor.execute(f"SELECT category, count(*) as cnt FROM documents{ws_filter} GROUP BY category", tuple(params))
        cat_rows = cursor.fetchall()
        category_distribution = {str(r["category"]): int(r["cnt"]) for r in cat_rows}

        # 7. File Type Distribution
        cursor.execute(f"SELECT file_type, count(*) as cnt FROM documents{ws_filter} GROUP BY file_type", tuple(params))
        ft_rows = cursor.fetchall()
        file_type_distribution = {str(r["file_type"]): int(r["cnt"]) for r in ft_rows}

        # 8. Graph stats
        cursor.execute("SELECT count(*) as cnt FROM graph_edges")
        total_edges = int(cursor.fetchone()["cnt"] or 0)

        # 9. Recent Documents
        cursor.execute(f"SELECT id, title, category, file_type, updated_at FROM documents{ws_filter} ORDER BY updated_at DESC LIMIT 5", tuple(params))
        recent_docs = [
            {
                "id": str(r["id"]),
                "title": str(r["title"]),
                "category": str(r["category"]),
                "file_type": str(r["file_type"]),
                "updated_at": str(r["updated_at"])
            }
            for r in cursor.fetchall()
        ]

        # 10. Recent Activity
        cursor.execute("SELECT action, details, created_at FROM activity_logs ORDER BY created_at DESC LIMIT 6")
        recent_activity = [
            {
                "action": str(r["action"]),
                "details": str(r["details"] or ""),
                "created_at": str(r["created_at"])
            }
            for r in cursor.fetchall()
        ]

        return {
            "total_documents": total_docs,
            "total_workspaces": total_workspaces,
            "total_chunks": total_chunks,
            "total_notes": total_notes,
            "total_tasks": total_tasks,
            "total_edges": total_edges,
            "storage_bytes": total_storage,
            "category_distribution": category_distribution,
            "file_type_distribution": file_type_distribution,
            "task_status_distribution": task_status_map,
            "recent_documents": recent_docs,
            "recent_activity": recent_activity
        }
