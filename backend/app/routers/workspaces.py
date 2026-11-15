import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

@router.get("", response_model=List[WorkspaceResponse])
def list_workspaces(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT w.id, w.name, w.description, w.owner_id, w.is_default, w.created_at,
                   COUNT(d.id) as document_count
            FROM workspaces w
            LEFT JOIN documents d ON w.id = d.workspace_id AND d.is_trash = 0
            GROUP BY w.id, w.name, w.description, w.owner_id, w.is_default, w.created_at
            ORDER BY w.is_default DESC, w.created_at ASC
        """)
        rows = cursor.fetchall()
        return [
            WorkspaceResponse(
                id=str(r["id"]),
                name=str(r["name"]),
                description=str(r["description"] or ""),
                owner_id=str(r["owner_id"]),
                is_default=int(r["is_default"] or 0),
                created_at=str(r["created_at"]),
                document_count=int(r["document_count"])
            )
            for r in rows
        ]

@router.post("", response_model=WorkspaceResponse, status_code=201)
def create_workspace(payload: WorkspaceCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name cannot be empty.")

    ws_id = str(uuid.uuid4())
    desc = payload.description.strip() if payload.description else ""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO workspaces (id, name, description, owner_id, is_default)
            VALUES (?, ?, ?, ?, 0)
        """, (ws_id, name, desc, current_user["id"]))
        conn.commit()

        cursor.execute("SELECT id, name, description, owner_id, is_default, created_at FROM workspaces WHERE id = ?", (ws_id,))
        row = cursor.fetchone()
        return WorkspaceResponse(
            id=str(row["id"]),
            name=str(row["name"]),
            description=str(row["description"] or ""),
            owner_id=str(row["owner_id"]),
            is_default=0,
            created_at=str(row["created_at"]),
            document_count=0
        )

@router.put("/{ws_id}", response_model=WorkspaceResponse)
def update_workspace(ws_id: str, payload: WorkspaceUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workspace not found.")

        name = payload.name.strip() if payload.name is not None else row["name"]
        desc = payload.description.strip() if payload.description is not None else row["description"]

        cursor.execute("""
            UPDATE workspaces SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name, desc, ws_id))
        conn.commit()

        cursor.execute("""
            SELECT w.id, w.name, w.description, w.owner_id, w.is_default, w.created_at,
                   COUNT(d.id) as document_count
            FROM workspaces w
            LEFT JOIN documents d ON w.id = d.workspace_id AND d.is_trash = 0
            WHERE w.id = ?
            GROUP BY w.id, w.name, w.description, w.owner_id, w.is_default, w.created_at
        """, (ws_id,))
        updated = cursor.fetchone()
        return WorkspaceResponse(
            id=str(updated["id"]),
            name=str(updated["name"]),
            description=str(updated["description"] or ""),
            owner_id=str(updated["owner_id"]),
            is_default=int(updated["is_default"] or 0),
            created_at=str(updated["created_at"]),
            document_count=int(updated["document_count"])
        )

@router.delete("/{ws_id}")
def delete_workspace(ws_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    if ws_id == "default":
        raise HTTPException(status_code=400, detail="The default primary workspace cannot be deleted.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM workspaces WHERE id = ?", (ws_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Workspace not found.")

        # Reassign documents to default workspace rather than destroying data
        cursor.execute("UPDATE documents SET workspace_id = 'default' WHERE workspace_id = ?", (ws_id,))
        cursor.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
        conn.commit()
        return {"status": "success", "deleted_id": ws_id}
