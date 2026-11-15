import uuid
import json
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Response, Depends
from typing import List, Optional, Dict, Any
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentDetailResponse
from app.engine.chunker import chunk_text
from app.engine.embeddings import vector_engine
from app.engine.graph import recompute_document_edges
from app.engine.parser import parse_uploaded_file

logger = logging.getLogger("neuraldesk.documents")
router = APIRouter(prefix="/documents", tags=["Documents"])

def clean_tags(tags: Optional[List[str]]) -> List[str]:
    if not tags:
        return []
    cleaned = []
    seen = set()
    for t in tags:
        t_str = str(t).strip().lower()
        t_str = re.sub(r'[^a-zA-Z0-9_-]', '', t_str)
        if t_str and t_str not in seen:
            seen.add(t_str)
            cleaned.append(t_str)
        if len(cleaned) >= 20:
            break
    return cleaned

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

def log_activity(conn, workspace_id: str, user_id: str, action: str, details: str = ""):
    try:
        log_id = str(uuid.uuid4())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (id, workspace_id, user_id, action, details)
            VALUES (?, ?, ?, ?, ?)
        """, (log_id, workspace_id, user_id, action, details))
    except Exception as e:
        logger.warning(f"Failed to write activity log: {e}")

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    workspace_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    view: Optional[str] = Query("active", description="Filter view: active, favorites, archive, trash, all")
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sql = """
            SELECT d.id, d.workspace_id, d.title, d.content, d.category, d.tags, d.file_type, d.file_size,
                   d.is_favorite, d.is_archived, d.is_trash, d.created_at, d.updated_at,
                   COUNT(c.id) as chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON d.id = c.document_id
            WHERE 1=1
        """
        params = []

        if view == "trash":
            sql += " AND d.is_trash = 1"
        elif view == "archive":
            sql += " AND d.is_archived = 1 AND d.is_trash = 0"
        elif view == "favorites":
            sql += " AND d.is_favorite = 1 AND d.is_trash = 0"
        elif view == "all":
            pass
        else: # active
            sql += " AND d.is_trash = 0 AND d.is_archived = 0"

        if workspace_id and workspace_id != "all":
            sql += " AND d.workspace_id = ?"
            params.append(workspace_id)

        if category and category != "ALL":
            sql += " AND d.category = ?"
            params.append(category)

        sql += """
            GROUP BY d.id, d.workspace_id, d.title, d.content, d.category, d.tags, d.file_type, d.file_size,
                     d.is_favorite, d.is_archived, d.is_trash, d.created_at, d.updated_at
            ORDER BY d.updated_at DESC
        """
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append(DocumentResponse(
                id=str(r["id"]),
                workspace_id=str(r["workspace_id"] or "default"),
                title=str(r["title"]),
                content=str(r["content"]),
                category=str(r["category"]),
                tags=parse_tags(r["tags"]),
                file_type=str(r["file_type"] or "text"),
                file_size=int(r["file_size"] or 0),
                is_favorite=int(r["is_favorite"] or 0),
                is_archived=int(r["is_archived"] or 0),
                is_trash=int(r["is_trash"] or 0),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
                chunk_count=int(r["chunk_count"])
            ))
        return result

@router.post("", response_model=DocumentResponse, status_code=201)
def create_document(doc: DocumentCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    title = doc.title.strip()
    content = doc.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Document title cannot be empty.")
    if not content:
        raise HTTPException(status_code=400, detail="Document content cannot be empty.")

    doc_id = str(uuid.uuid4())
    sanitized_tags = clean_tags(doc.tags)
    tags_json = json.dumps(sanitized_tags)
    category = doc.category.strip() if doc.category else "General"
    workspace_id = doc.workspace_id or "default"
    file_type = doc.file_type or "text"
    file_size = len(content.encode("utf-8"))

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (id, workspace_id, owner_id, title, content, category, tags, file_type, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, workspace_id, current_user["id"], title, content, category, tags_json, file_type, file_size))

        # Chunk text & calculate 128-D vector embeddings
        chunks = chunk_text(content)
        for c in chunks:
            chunk_id = str(uuid.uuid4())
            emb = vector_engine.embed(c["content"])
            cursor.execute("""
                INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, (chunk_id, doc_id, c["index"], c["content"], json.dumps(emb)))

        recompute_document_edges(conn, doc_id)
        log_activity(conn, workspace_id, current_user["id"], "Created Document", f'Created "{title}" ({len(chunks)} chunks)')
        conn.commit()

        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        saved = cursor.fetchone()

        return DocumentResponse(
            id=str(saved["id"]),
            workspace_id=str(saved["workspace_id"]),
            title=str(saved["title"]),
            content=str(saved["content"]),
            category=str(saved["category"]),
            tags=parse_tags(saved["tags"]),
            file_type=str(saved["file_type"]),
            file_size=int(saved["file_size"]),
            is_favorite=int(saved["is_favorite"]),
            is_archived=int(saved["is_archived"]),
            is_trash=int(saved["is_trash"]),
            created_at=str(saved["created_at"]),
            updated_at=str(saved["updated_at"]),
            chunk_count=len(chunks)
        )

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form("General"),
    workspace_id: Optional[str] = Form("default"),
    tags: Optional[str] = Form(""),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    content_bytes = await file.read()
    if len(content_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds maximum 10MB limit.")

    try:
        parsed = parse_uploaded_file(file.filename or "uploaded_file.txt", content_bytes)
        content_text = parsed["text"].strip()
        file_type = parsed["file_type"]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    if not content_text:
        raise HTTPException(status_code=400, detail="The uploaded file contains no extractable text.")

    # Derive title
    title = Path(file.filename or "Uploaded Document").stem.replace("_", " ").replace("-", " ").title()
    lines = content_text.splitlines()
    if lines and lines[0].startswith("# "):
        h1 = lines[0].replace("# ", "").strip()
        if h1:
            title = h1[:200]

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    doc_create = DocumentCreate(
        title=title,
        content=content_text,
        category=category or "General",
        workspace_id=workspace_id or "default",
        tags=tag_list,
        file_type=file_type
    )
    return create_document(doc_create, current_user=current_user)

@router.get("/{doc_id}", response_model=DocumentDetailResponse)
def get_document(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        cursor.execute("SELECT chunk_index, content FROM document_chunks WHERE document_id = ? ORDER BY chunk_index", (doc_id,))
        chunks = cursor.fetchall()

        cursor.execute("""
            SELECT e.relation_type, e.weight,
                   CASE WHEN e.source_id = ? THEN d2.title ELSE d1.title END as related_title,
                   CASE WHEN e.source_id = ? THEN d2.id ELSE d1.id END as related_id
            FROM graph_edges e
            JOIN documents d1 ON e.source_id = d1.id
            JOIN documents d2 ON e.target_id = d2.id
            WHERE e.source_id = ? OR e.target_id = ?
        """, (doc_id, doc_id, doc_id, doc_id))
        relations = cursor.fetchall()

        return DocumentDetailResponse(
            id=str(doc["id"]),
            workspace_id=str(doc["workspace_id"] or "default"),
            title=str(doc["title"]),
            content=str(doc["content"]),
            category=str(doc["category"]),
            tags=parse_tags(doc["tags"]),
            file_type=str(doc["file_type"] or "text"),
            file_size=int(doc["file_size"] or 0),
            is_favorite=int(doc["is_favorite"] or 0),
            is_archived=int(doc["is_archived"] or 0),
            is_trash=int(doc["is_trash"] or 0),
            created_at=str(doc["created_at"]),
            updated_at=str(doc["updated_at"]),
            chunks=[{"index": c["chunk_index"], "content": c["content"]} for c in chunks],
            related=[{"id": str(r["related_id"]), "title": str(r["related_title"]), "weight": float(r["weight"]), "type": str(r["relation_type"])} for r in relations]
        )

@router.put("/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, doc: DocumentUpdate, current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found.")

        title = doc.title.strip() if doc.title is not None else existing["title"]
        content = doc.content.strip() if doc.content is not None else existing["content"]
        if not title:
            raise HTTPException(status_code=400, detail="Document title cannot be empty.")
        if not content:
            raise HTTPException(status_code=400, detail="Document content cannot be empty.")

        category = doc.category.strip() if doc.category is not None else existing["category"]
        tags_json = json.dumps(clean_tags(doc.tags)) if doc.tags is not None else (existing["tags"] if isinstance(existing["tags"], str) else json.dumps(existing["tags"]))
        is_fav = doc.is_favorite if doc.is_favorite is not None else existing["is_favorite"]
        is_arch = doc.is_archived if doc.is_archived is not None else existing["is_archived"]
        is_trsh = doc.is_trash if doc.is_trash is not None else existing["is_trash"]
        folder = doc.folder if doc.folder is not None else existing["folder"]
        new_size = len(content.encode("utf-8"))

        cursor.execute("""
            UPDATE documents
            SET title = ?, content = ?, category = ?, tags = ?, file_size = ?,
                is_favorite = ?, is_archived = ?, is_trash = ?, folder = ?,
                version = version + 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, content, category, tags_json, new_size, is_fav, is_arch, is_trsh, folder, doc_id))

        if doc.content is not None:
            cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            chunks = chunk_text(content)
            for c in chunks:
                chunk_id = str(uuid.uuid4())
                emb = vector_engine.embed(c["content"])
                cursor.execute("""
                    INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding)
                    VALUES (?, ?, ?, ?, ?)
                """, (chunk_id, doc_id, c["index"], c["content"], json.dumps(emb)))
        else:
            cursor.execute("SELECT count(*) as cnt FROM document_chunks WHERE document_id = ?", (doc_id,))
            chunks = range(cursor.fetchone()["cnt"])

        recompute_document_edges(conn, doc_id)
        log_activity(conn, str(existing["workspace_id"]), current_user["id"], "Updated Document", f'Updated "{title}"')
        conn.commit()

        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        updated = cursor.fetchone()

        return DocumentResponse(
            id=str(updated["id"]),
            workspace_id=str(updated["workspace_id"]),
            title=str(updated["title"]),
            content=str(updated["content"]),
            category=str(updated["category"]),
            tags=parse_tags(updated["tags"]),
            file_type=str(updated["file_type"]),
            file_size=int(updated["file_size"]),
            is_favorite=int(updated["is_favorite"]),
            is_archived=int(updated["is_archived"]),
            is_trash=int(updated["is_trash"]),
            created_at=str(updated["created_at"]),
            updated_at=str(updated["updated_at"]),
            chunk_count=len(chunks)
        )

@router.post("/{doc_id}/favorite")
def toggle_favorite(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_favorite FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")
        new_val = 0 if row["is_favorite"] else 1
        cursor.execute("UPDATE documents SET is_favorite = ? WHERE id = ?", (new_val, doc_id))
        conn.commit()
        return {"id": doc_id, "is_favorite": new_val}

@router.post("/{doc_id}/trash")
def move_to_trash(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE documents SET is_trash = 1 WHERE id = ?", (doc_id,))
        conn.commit()
        return {"id": doc_id, "status": "moved_to_trash"}

@router.post("/{doc_id}/restore")
def restore_from_trash(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE documents SET is_trash = 0 WHERE id = ?", (doc_id,))
        conn.commit()
        return {"id": doc_id, "status": "restored"}

@router.delete("/{doc_id}")
def delete_document(doc_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, workspace_id FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")

        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
        log_activity(conn, str(row["workspace_id"]), current_user["id"], "Deleted Document", f'Deleted "{row["title"]}"')
        conn.commit()
        return {"status": "success", "deleted_id": doc_id}

@router.get("/{doc_id}/export")
def export_document(doc_id: str, format: str = Query("md", pattern="^(md|json)$")):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        title_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', doc["title"]).lower()
        if format == "json":
            data = {
                "id": str(doc["id"]),
                "workspace_id": str(doc["workspace_id"]),
                "title": str(doc["title"]),
                "content": str(doc["content"]),
                "category": str(doc["category"]),
                "tags": parse_tags(doc["tags"]),
                "file_type": str(doc["file_type"]),
                "created_at": str(doc["created_at"]),
                "updated_at": str(doc["updated_at"])
            }
            return Response(
                content=json.dumps(data, indent=2),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{title_slug}.json"'}
            )
        else:
            tags_header = ", ".join(parse_tags(doc["tags"]))
            md_content = f"# {doc['title']}\n\n**Category:** {doc['category']}  \n**Tags:** {tags_header}  \n**Type:** {doc['file_type']}\n\n---\n\n{doc['content']}\n"
            return Response(
                content=md_content,
                media_type="text/markdown",
                headers={"Content-Disposition": f'attachment; filename="{title_slug}.md"'}
            )
