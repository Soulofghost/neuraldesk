import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import TaskCreate, TaskUpdate, TaskResponse
from app.engine.intelligence import intelligence_engine

router = APIRouter(prefix="/tasks", tags=["Tasks & Action Management"])

@router.get("", response_model=List[TaskResponse])
def list_tasks(
    workspace_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None)
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if workspace_id and workspace_id != "all":
            sql += " AND workspace_id = ?"
            params.append(workspace_id)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if priority:
            sql += " AND priority = ?"
            params.append(priority)

        sql += " ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return [
            TaskResponse(
                id=str(r["id"]),
                workspace_id=str(r["workspace_id"] or "default"),
                title=str(r["title"]),
                description=str(r["description"] or ""),
                status=str(r["status"] or "todo"),
                priority=str(r["priority"] or "medium"),
                due_date=str(r["due_date"]) if r["due_date"] else None,
                linked_document_id=str(r["linked_document_id"]) if r["linked_document_id"] else None,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"])
            )
            for r in rows
        ]

@router.post("", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title cannot be empty.")

    task_id = str(uuid.uuid4())
    ws_id = payload.workspace_id or "default"
    desc = payload.description.strip() if payload.description else ""
    status = payload.status or "todo"
    priority = payload.priority or "medium"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (id, workspace_id, owner_id, title, description, status, priority, due_date, linked_document_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, ws_id, current_user["id"], title, desc, status, priority, payload.due_date, payload.linked_document_id))
        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return TaskResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            description=str(row["description"] or ""),
            status=str(row["status"]),
            priority=str(row["priority"]),
            due_date=str(row["due_date"]) if row["due_date"] else None,
            linked_document_id=str(row["linked_document_id"]) if row["linked_document_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, payload: TaskUpdate):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Task not found.")

        title = payload.title.strip() if payload.title is not None else existing["title"]
        desc = payload.description.strip() if payload.description is not None else existing["description"]
        status = payload.status if payload.status is not None else existing["status"]
        priority = payload.priority if payload.priority is not None else existing["priority"]
        due_date = payload.due_date if payload.due_date is not None else existing["due_date"]

        cursor.execute("""
            UPDATE tasks SET title = ?, description = ?, status = ?, priority = ?, due_date = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, desc, status, priority, due_date, task_id))
        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return TaskResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            description=str(row["description"] or ""),
            status=str(row["status"]),
            priority=str(row["priority"]),
            due_date=str(row["due_date"]) if row["due_date"] else None,
            linked_document_id=str(row["linked_document_id"]) if row["linked_document_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )

@router.post("/{task_id}/toggle", response_model=TaskResponse)
def toggle_task(task_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found.")
        new_status = "todo" if row["status"] == "done" else "done"
        cursor.execute("UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, task_id))
        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        updated = cursor.fetchone()
        return TaskResponse(
            id=str(updated["id"]),
            workspace_id=str(updated["workspace_id"]),
            title=str(updated["title"]),
            description=str(updated["description"] or ""),
            status=str(updated["status"]),
            priority=str(updated["priority"]),
            due_date=str(updated["due_date"]) if updated["due_date"] else None,
            linked_document_id=str(updated["linked_document_id"]) if updated["linked_document_id"] else None,
            created_at=str(updated["created_at"]),
            updated_at=str(updated["updated_at"])
        )

@router.delete("/{task_id}")
def delete_task(task_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return {"status": "success", "deleted_id": task_id}

@router.post("/extract-from-doc/{doc_id}", response_model=List[TaskResponse])
def extract_tasks_from_doc(doc_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT workspace_id, content, title FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        action_items = intelligence_engine.extract_action_items(doc["content"])
        created_tasks = []
        for item in action_items:
            task_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO tasks (id, workspace_id, owner_id, title, description, status, priority, linked_document_id)
                VALUES (?, ?, ?, ?, ?, 'todo', 'medium', ?)
            """, (task_id, str(doc["workspace_id"]), current_user["id"], item, f'Auto-extracted from "{doc["title"]}"', doc_id))
            created_tasks.append(task_id)

        conn.commit()

        # Fetch created tasks
        tasks = []
        for tid in created_tasks:
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (tid,))
            r = cursor.fetchone()
            tasks.append(TaskResponse(
                id=str(r["id"]),
                workspace_id=str(r["workspace_id"]),
                title=str(r["title"]),
                description=str(r["description"] or ""),
                status=str(r["status"]),
                priority=str(r["priority"]),
                due_date=str(r["due_date"]) if r["due_date"] else None,
                linked_document_id=str(r["linked_document_id"]) if r["linked_document_id"] else None,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"])
            ))
        return tasks
