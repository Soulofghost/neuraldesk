import uuid
import json
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.database import get_db_connection
from app.auth import get_current_user
from app.schemas import ConversationCreate, ConversationResponse, MessageCreate, MessageResponse
from app.engine.intelligence import intelligence_engine

router = APIRouter(prefix="/chat", tags=["NeuralDesk AI Assistant"])

@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(current_user: Dict[str, Any] = Depends(get_current_user)):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.workspace_id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM ai_conversations c
            LEFT JOIN ai_messages m ON c.id = m.conversation_id
            WHERE c.user_id = ?
            GROUP BY c.id, c.workspace_id, c.title, c.created_at, c.updated_at
            ORDER BY c.updated_at DESC
        """, (current_user["id"],))
        rows = cursor.fetchall()
        return [
            ConversationResponse(
                id=str(r["id"]),
                workspace_id=str(r["workspace_id"] or "default"),
                title=str(r["title"]),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
                message_count=int(r["message_count"] or 0)
            )
            for r in rows
        ]

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(payload: ConversationCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conv_id = str(uuid.uuid4())
    title = (payload.title or "New Research Session").strip()
    ws_id = payload.workspace_id or "default"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_conversations (id, workspace_id, user_id, title)
            VALUES (?, ?, ?, ?)
        """, (conv_id, ws_id, current_user["id"], title))
        conn.commit()

        cursor.execute("SELECT id, workspace_id, title, created_at, updated_at FROM ai_conversations WHERE id = ?", (conv_id,))
        row = cursor.fetchone()
        return ConversationResponse(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            message_count=0
        )

@router.get("/conversations/{conv_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(conv_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, conversation_id, role, content, citations, created_at
            FROM ai_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
        """, (conv_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            cits = []
            if r["citations"]:
                try:
                    cits = json.loads(r["citations"]) if isinstance(r["citations"], str) else r["citations"]
                except Exception:
                    cits = []
            result.append(MessageResponse(
                id=str(r["id"]),
                conversation_id=str(r["conversation_id"]),
                role=str(r["role"]),
                content=str(r["content"]),
                citations=cits or [],
                created_at=str(r["created_at"])
            ))
        return result

@router.post("/conversations/{conv_id}/messages", response_model=MessageResponse, status_code=201)
def send_message(conv_id: str, payload: MessageCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    user_msg = payload.content.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, workspace_id, title FROM ai_conversations WHERE id = ?", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")

        # 1. Store User Message
        user_msg_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ai_messages (id, conversation_id, role, content, citations)
            VALUES (?, ?, 'user', ?, '[]')
        """, (user_msg_id, conv_id, user_msg))

        # 2. Gather context chunks for RAG
        chunks = []
        if payload.document_id:
            cursor.execute("SELECT chunk_index, content, embedding FROM document_chunks WHERE document_id = ?", (payload.document_id,))
            rows = cursor.fetchall()
            chunks = [{"chunk_index": r["chunk_index"], "content": r["content"], "embedding": r["embedding"]} for r in rows]
        else:
            ws_id = conv["workspace_id"] or "default"
            cursor.execute("""
                SELECT c.chunk_index, c.content, c.embedding
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.workspace_id = ? AND d.is_trash = 0
                LIMIT 40
            """, (ws_id,))
            rows = cursor.fetchall()
            chunks = [{"chunk_index": r["chunk_index"], "content": r["content"], "embedding": r["embedding"]} for r in rows]

        # 3. Generate grounded answer
        ai_res = intelligence_engine.answer_question(user_msg, chunks)
        assistant_msg_id = str(uuid.uuid4())
        citations_json = json.dumps(ai_res["citations"])

        # 4. Store Assistant Response
        cursor.execute("""
            INSERT INTO ai_messages (id, conversation_id, role, content, citations)
            VALUES (?, ?, 'assistant', ?, ?)
        """, (assistant_msg_id, conv_id, ai_res["answer"], citations_json))

        # Auto-update conversation title if it was default
        if conv["title"] == "New Research Chat":
            new_title = user_msg[:36] + ("..." if len(user_msg) > 36 else "")
            cursor.execute("UPDATE ai_conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_title, conv_id))
        else:
            cursor.execute("UPDATE ai_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))

        conn.commit()

        cursor.execute("SELECT id, conversation_id, role, content, citations, created_at FROM ai_messages WHERE id = ?", (assistant_msg_id,))
        saved = cursor.fetchone()
        return MessageResponse(
            id=str(saved["id"]),
            conversation_id=str(saved["conversation_id"]),
            role=str(saved["role"]),
            content=str(saved["content"]),
            citations=ai_res["citations"],
            created_at=str(saved["created_at"])
        )

@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ai_conversations WHERE id = ?", (conv_id,))
        cursor.execute("DELETE FROM ai_messages WHERE conversation_id = ?", (conv_id,))
        conn.commit()
        return {"status": "success", "deleted_id": conv_id}

@router.get("/suggested")
def get_suggested_prompts():
    return {
        "prompts": [
            "Summarize the key architectural tradeoffs across the knowledge base.",
            "What consensus mechanisms are discussed and how does Raft compare to Paxos?",
            "Extract all action items and deployment requirements.",
            "Explain the vector embedding dimensionality and cosine similarity algorithm used."
        ]
    }
