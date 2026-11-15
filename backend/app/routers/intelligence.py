import json
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import SummarizeRequest, SummarizeResponse, QuestionAnsweringRequest, QuestionAnsweringResponse
from app.engine.intelligence import intelligence_engine

router = APIRouter(prefix="/intelligence", tags=["AI Document Intelligence"])

@router.post("/summarize", response_model=SummarizeResponse)
def summarize_document(payload: SummarizeRequest):
    text = ""
    if payload.document_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM documents WHERE id = ?", (payload.document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found.")
            text = doc["content"]
    elif payload.content:
        text = payload.content
    else:
        raise HTTPException(status_code=400, detail="Provide either document_id or content.")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Document text is empty.")

    max_sentences = payload.max_sentences or 4
    result = intelligence_engine.summarize(text, max_sentences=max_sentences)
    return SummarizeResponse(
        summary=result["summary"],
        sentence_count=result["sentence_count"],
        key_takeaways=result["key_takeaways"]
    )

@router.post("/entities")
def extract_entities(payload: SummarizeRequest):
    text = ""
    if payload.document_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM documents WHERE id = ?", (payload.document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found.")
            text = doc["content"]
    elif payload.content:
        text = payload.content
    else:
        raise HTTPException(status_code=400, detail="Provide either document_id or content.")

    entities = intelligence_engine.extract_entities(text)
    keywords = intelligence_engine.extract_keywords(text)
    return {
        "entities": entities,
        "keywords": keywords
    }

@router.post("/action-items")
def extract_action_items(payload: SummarizeRequest):
    text = ""
    if payload.document_id:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM documents WHERE id = ?", (payload.document_id,))
            doc = cursor.fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found.")
            text = doc["content"]
    elif payload.content:
        text = payload.content
    else:
        raise HTTPException(status_code=400, detail="Provide either document_id or content.")

    items = intelligence_engine.extract_action_items(text)
    return {"action_items": items, "count": len(items)}

@router.post("/ask", response_model=QuestionAnsweringResponse)
def ask_question(payload: QuestionAnsweringRequest):
    chunks = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if payload.document_id:
            cursor.execute("SELECT chunk_index, content, embedding FROM document_chunks WHERE document_id = ?", (payload.document_id,))
            rows = cursor.fetchall()
            chunks = [{"chunk_index": r["chunk_index"], "content": r["content"], "embedding": r["embedding"]} for r in rows]
        else:
            # Query workspace chunks
            ws_id = payload.workspace_id or "default"
            cursor.execute("""
                SELECT c.chunk_index, c.content, c.embedding
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.workspace_id = ? AND d.is_trash = 0
                LIMIT 50
            """, (ws_id,))
            rows = cursor.fetchall()
            chunks = [{"chunk_index": r["chunk_index"], "content": r["content"], "embedding": r["embedding"]} for r in rows]

    if not chunks:
        return QuestionAnsweringResponse(
            answer="No relevant document passages were found in this context.",
            citations=[],
            confidence=0.0
        )

    res = intelligence_engine.answer_question(payload.question, chunks)
    return QuestionAnsweringResponse(
        answer=res["answer"],
        citations=res["citations"],
        confidence=res["confidence"]
    )
