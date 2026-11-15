import uuid
import secrets
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import CommentCreate, CommentResponse, ShareLinkResponse, DocumentResponse

router = APIRouter(prefix="/collaboration", tags=["Collaboration & Sharing"])

@router.post("/share/{doc_id}", response_model=ShareLinkResponse)
def create_share_link(doc_id: str, permission: str = "view"):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found.")

        # Check existing link
        cursor.execute("SELECT id, document_id, token, permission, created_at FROM shared_links WHERE document_id = ?", (doc_id,))
        existing = cursor.fetchone()
        if existing:
            return ShareLinkResponse(
                id=str(existing["id"]),
                document_id=str(existing["document_id"]),
                token=str(existing["token"]),
                share_url=f"/api/v1/collaboration/shared/{existing['token']}",
                permission=str(existing["permission"]),
                created_at=str(existing["created_at"])
            )

        link_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(16)
        cursor.execute("""
            INSERT INTO shared_links (id, document_id, token, permission)
            VALUES (?, ?, ?, ?)
        """, (link_id, doc_id, token, permission))
        conn.commit()

        cursor.execute("SELECT id, document_id, token, permission, created_at FROM shared_links WHERE id = ?", (link_id,))
        row = cursor.fetchone()
        return ShareLinkResponse(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            token=str(row["token"]),
            share_url=f"/api/v1/collaboration/shared/{row['token']}",
            permission=str(row["permission"]),
            created_at=str(row["created_at"])
        )

@router.get("/shared/{token}")
def get_shared_document(token: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT document_id, permission FROM shared_links WHERE token = ?", (token,))
        link = cursor.fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Shared link is invalid or expired.")

        cursor.execute("SELECT id, title, content, category, tags, created_at, updated_at FROM documents WHERE id = ?", (link["document_id"],))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Referenced document no longer exists.")

        return {
            "document": {
                "id": str(doc["id"]),
                "title": str(doc["title"]),
                "content": str(doc["content"]),
                "category": str(doc["category"]),
                "created_at": str(doc["created_at"]),
                "updated_at": str(doc["updated_at"])
            },
            "permission": link["permission"]
        }

@router.get("/comments/{doc_id}", response_model=List[CommentResponse])
def list_comments(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, document_id, author_name, content, created_at FROM comments WHERE document_id = ? ORDER BY created_at ASC", (doc_id,))
        rows = cursor.fetchall()
        return [
            CommentResponse(
                id=str(r["id"]),
                document_id=str(r["document_id"]),
                author_name=str(r["author_name"]),
                content=str(r["content"]),
                created_at=str(r["created_at"])
            )
            for r in rows
        ]

@router.post("/comments/{doc_id}", response_model=CommentResponse, status_code=201)
def add_comment(doc_id: str, payload: CommentCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Comment cannot be empty.")

    comment_id = str(uuid.uuid4())
    author = current_user.get("full_name") or "Team Member"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, workspace_id, title FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        cursor.execute("""
            INSERT INTO comments (id, document_id, user_id, author_name, content)
            VALUES (?, ?, ?, ?, ?)
        """, (comment_id, doc_id, current_user["id"], author, content))
        conn.commit()

        cursor.execute("SELECT id, document_id, author_name, content, created_at FROM comments WHERE id = ?", (comment_id,))
        row = cursor.fetchone()
        return CommentResponse(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            author_name=str(row["author_name"]),
            content=str(row["content"]),
            created_at=str(row["created_at"])
        )

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        conn.commit()
        return {"status": "success", "deleted_id": comment_id}

@router.get("/activity")
def get_activity_stream(workspace_id: Optional[str] = "default"):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, workspace_id, user_id, action, details, created_at
            FROM activity_logs
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT 30
        """, (workspace_id,))
        rows = cursor.fetchall()
        return [
            {
                "id": str(r["id"]),
                "workspace_id": str(r["workspace_id"]),
                "user_id": str(r["user_id"]),
                "action": str(r["action"]),
                "details": str(r["details"] or ""),
                "created_at": str(r["created_at"])
            }
            for r in rows
        ]
