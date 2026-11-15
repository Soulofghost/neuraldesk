import uuid
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import NoteCreate, NoteUpdate, NoteResponse

router = APIRouter(prefix="/notes", tags=["Notes & Knowledge Capture"])

def parse_tags(raw_tags) -> List[str]:
    if isinstance(raw_tags, list):
        return raw_tags
    if isinstance(raw_tags, str):
        try:
            parsed = json.loads(raw_tags)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

@router.get("", response_model=List[NoteResponse])
def list_notes(
    workspace_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM notes WHERE 1=1"
        params = []
        if workspace_id and workspace_id != "all":
            sql += " AND workspace_id = ?"
            params.append(workspace_id)
        if q:
            sql += " AND (title LIKE ? OR content LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])

        sql += " ORDER BY is_pinned DESC, updated_at DESC"
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return [
            NoteResponse(
                id=str(r["id"]),
                workspace_id=str(r["workspace_id"] or "default"),
                title=str(r["title"]),
                content=str(r["content"]),
                tags=parse_tags(r["tags"]),
                is_pinned=int(r["is_pinned"] or 0),
                is_favorite=int(r["is_favorite"] or 0),
                linked_document_id=str(r["linked_document_id"]) if r["linked_document_id"] else None,
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"])
            )
            for r in rows
        ]

@router.post("", response_model=NoteResponse, status_code=201)
def create_note(payload: NoteCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    title = payload.title.strip()
    content = payload.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Note title cannot be empty.")
    if not content:
        raise HTTPException(status_code=400, detail="Note content cannot be empty.")

    note_id = str(uuid.uuid4())
    ws_id = payload.workspace_id or "default"
    tags_json = json.dumps(payload.tags or [])

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notes (id, workspace_id, owner_id, title, content, tags, linked_document_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (note_id, ws_id, current_user["id"], title, content, tags_json, payload.linked_document_id))
        conn.commit()

        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        return NoteResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            content=str(row["content"]),
            tags=parse_tags(row["tags"]),
            is_pinned=int(row["is_pinned"]),
            is_favorite=int(row["is_favorite"]),
            linked_document_id=str(row["linked_document_id"]) if row["linked_document_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )

@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Note not found.")
        return NoteResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            content=str(row["content"]),
            tags=parse_tags(row["tags"]),
            is_pinned=int(row["is_pinned"]),
            is_favorite=int(row["is_favorite"]),
            linked_document_id=str(row["linked_document_id"]) if row["linked_document_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )

@router.put("/{note_id}", response_model=NoteResponse)
def update_note(note_id: str, payload: NoteUpdate):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found.")

        title = payload.title.strip() if payload.title is not None else existing["title"]
        content = payload.content.strip() if payload.content is not None else existing["content"]
        tags_json = json.dumps(payload.tags) if payload.tags is not None else existing["tags"]
        is_pin = payload.is_pinned if payload.is_pinned is not None else existing["is_pinned"]
        is_fav = payload.is_favorite if payload.is_favorite is not None else existing["is_favorite"]

        cursor.execute("""
            UPDATE notes SET title = ?, content = ?, tags = ?, is_pinned = ?, is_favorite = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, content, tags_json, is_pin, is_fav, note_id))
        conn.commit()

        cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        return NoteResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            content=str(row["content"]),
            tags=parse_tags(row["tags"]),
            is_pinned=int(row["is_pinned"]),
            is_favorite=int(row["is_favorite"]),
            linked_document_id=str(row["linked_document_id"]) if row["linked_document_id"] else None,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"])
        )

@router.delete("/{note_id}")
def delete_note(note_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return {"status": "success", "deleted_id": note_id}
