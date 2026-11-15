import uuid
import json
from fastapi import APIRouter, HTTPException
from typing import List
from app.database import get_db_connection
from app.schemas import DocumentCreate, DocumentUpdate, DocumentResponse
from app.engine.chunker import chunk_text
from app.engine.embeddings import vector_engine
from app.engine.graph import recompute_document_edges

router = APIRouter(prefix="/documents", tags=["Documents"])

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
def list_documents():
    with get_db_connection() as conn:
        cursor = conn.cursor()
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
    doc_id = str(uuid.uuid4())
    tags_json = json.dumps(doc.tags or [])
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (id, title, content, category, tags)
            VALUES (?, ?, ?, ?, ?)
        """, (doc_id, doc.title, doc.content, doc.category, tags_json))
        
        # Chunk text
        chunks = chunk_text(doc.content)
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

@router.get("/{doc_id}")
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
        
        return {
            "id": str(doc["id"]),
            "title": str(doc["title"]),
            "content": str(doc["content"]),
            "category": str(doc["category"]),
            "tags": parse_tags(doc["tags"]),
            "created_at": str(doc["created_at"]),
            "updated_at": str(doc["updated_at"]),
            "chunks": [{"index": c["chunk_index"], "content": c["content"]} for c in chunks],
            "related": [{"id": str(r["related_id"]), "title": str(r["related_title"]), "weight": float(r["weight"]), "type": str(r["relation_type"])} for r in relations]
        }

@router.put("/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, doc: DocumentUpdate):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Document not found")
            
        title = doc.title if doc.title is not None else existing["title"]
        content = doc.content if doc.content is not None else existing["content"]
        category = doc.category if doc.category is not None else existing["category"]
        tags_json = json.dumps(doc.tags) if doc.tags is not None else existing["tags"]
        
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
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        cursor.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
        conn.commit()
        return {"status": "success", "deleted_id": doc_id}
