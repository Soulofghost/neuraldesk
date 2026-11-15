import uuid
import json
import re
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Response
from typing import List, Optional
from app.database import get_db_connection
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentDetailResponse
from app.engine.chunker import chunk_text
from app.engine.embeddings import vector_engine
from app.engine.graph import recompute_document_edges

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

@router.get("", response_model=List[DocumentResponse])
def list_documents(category: Optional[str] = Query(None, description="Filter by category")):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if category and category != "ALL":
            cursor.execute("""
                SELECT d.id, d.title, d.content, d.category, d.tags, d.created_at, d.updated_at,
                       COUNT(c.id) as chunk_count
                FROM documents d
                LEFT JOIN document_chunks c ON d.id = c.document_id
                WHERE d.category = ?
                GROUP BY d.id, d.title, d.content, d.category, d.tags, d.created_at, d.updated_at
                ORDER BY d.updated_at DESC
            """, (category,))
        else:
            cursor.execute("""
                SELECT d.id, d.title, d.content, d.category, d.tags, d.created_at, d.updated_at,
                       COUNT(c.id) as chunk_count
                FROM documents d
                LEFT JOIN document_chunks c ON d.id = c.document_id
                GROUP BY d.id, d.title, d.content, d.category, d.tags, d.created_at, d.updated_at
                ORDER BY d.updated_at DESC
            """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append(DocumentResponse(
                id=str(r["id"]),
                title=str(r["title"]),
                content=str(r["content"]),
                category=str(r["category"]),
                tags=parse_tags(r["tags"]),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
                chunk_count=int(r["chunk_count"])
            ))
        return result

@router.post("", response_model=DocumentResponse, status_code=201)
def create_document(doc: DocumentCreate):
    title = doc.title.strip()
    content = doc.content.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Document title cannot be empty")
    if not content:
        raise HTTPException(status_code=400, detail="Document content cannot be empty")
    
    doc_id = str(uuid.uuid4())
    sanitized_tags = clean_tags(doc.tags)
    tags_json = json.dumps(sanitized_tags)
    category = doc.category.strip() if doc.category else "General"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (id, title, content, category, tags)
            VALUES (?, ?, ?, ?, ?)
        """, (doc_id, title, content, category, tags_json))
        
        # Chunk text
        chunks = chunk_text(content)
        for c in chunks:
            chunk_id = str(uuid.uuid4())
            emb = vector_engine.embed(c["content"])
            cursor.execute("""
                INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, (chunk_id, doc_id, c["index"], c["content"], json.dumps(emb)))
            
        recompute_document_edges(conn, doc_id)
        conn.commit()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        saved = cursor.fetchone()
        
        return DocumentResponse(
            id=str(saved["id"]),
            title=str(saved["title"]),
            content=str(saved["content"]),
            category=str(saved["category"]),
            tags=parse_tags(saved["tags"]),
            created_at=str(saved["created_at"]),
            updated_at=str(saved["updated_at"]),
            chunk_count=len(chunks)
        )

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: Optional[str] = Form("General"),
    tags: Optional[str] = Form("")
):
    # Validate extension
    allowed_exts = {".md", ".txt", ".markdown", ".json"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Allowed: .md, .txt, .json")
    
    # Read content with 5MB size limit
    content_bytes = await file.read()
    if len(content_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File size exceeds maximum 5MB limit")
    
    try:
        content_text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content_text = content_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Failed to decode text content from uploaded file")
            
    content_text = content_text.strip()
    if not content_text:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    # Derive title
    title = Path(file.filename or "Uploaded Document").stem.replace("_", " ").replace("-", " ").title()
    # Check if first line is a markdown H1
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
        tags=tag_list
    )
    return create_document(doc_create)

@router.get("/{doc_id}", response_model=DocumentDetailResponse)
def get_document(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        cursor.execute("SELECT chunk_index, content FROM document_chunks WHERE document_id = ? ORDER BY chunk_index", (doc_id,))
        chunks = cursor.fetchall()
        
        # Backlinks / related documents
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
            title=str(doc["title"]),
            content=str(doc["content"]),
            category=str(doc["category"]),
            tags=parse_tags(doc["tags"]),
            created_at=str(doc["created_at"]),
            updated_at=str(doc["updated_at"]),
            chunks=[{"index": c["chunk_index"], "content": c["content"]} for c in chunks],
            related=[{"id": str(r["related_id"]), "title": str(r["related_title"]), "weight": float(r["weight"]), "type": str(r["relation_type"])} for r in relations]
        )

@router.get("/{doc_id}/export")
def export_document(doc_id: str, format: str = Query("md", pattern="^(md|json)$")):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
            
        title_slug = re.sub(r'[^a-zA-Z0-9_-]', '_', doc["title"]).lower()
        if format == "json":
            data = {
                "id": str(doc["id"]),
                "title": str(doc["title"]),
                "content": str(doc["content"]),
                "category": str(doc["category"]),
                "tags": parse_tags(doc["tags"]),
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
            md_content = f"# {doc['title']}\n\n**Category:** {doc['category']}  \n**Tags:** {tags_header}\n\n---\n\n{doc['content']}\n"
            return Response(
                content=md_content,
                media_type="text/markdown",
                headers={"Content-Disposition": f'attachment; filename="{title_slug}.md"'}
            )

@router.put("/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, doc: DocumentUpdate):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
            
        title = doc.title.strip() if doc.title is not None else existing["title"]
        content = doc.content.strip() if doc.content is not None else existing["content"]
        if not title:
            raise HTTPException(status_code=400, detail="Document title cannot be empty")
        if not content:
            raise HTTPException(status_code=400, detail="Document content cannot be empty")
            
        category = doc.category.strip() if doc.category is not None else existing["category"]
        if doc.tags is not None:
            tags_json = json.dumps(clean_tags(doc.tags))
        else:
            tags_json = existing["tags"] if isinstance(existing["tags"], str) else json.dumps(existing["tags"])
        
        cursor.execute("""
            UPDATE documents
            SET title = ?, content = ?, category = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, content, category, tags_json, doc_id))
        
        # If content changed, re-chunk and re-embed
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
        conn.commit()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        updated = cursor.fetchone()
        
        return DocumentResponse(
            id=str(updated["id"]),
            title=str(updated["title"]),
            content=str(updated["content"]),
            category=str(updated["category"]),
            tags=parse_tags(updated["tags"]),
            created_at=str(updated["created_at"]),
            updated_at=str(updated["updated_at"]),
            chunk_count=len(chunks)
        )

@router.delete("/{doc_id}")
def delete_document(doc_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Document not found")
            
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
        conn.commit()
        return {"status": "success", "deleted_id": doc_id}
