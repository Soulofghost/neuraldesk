import json
import re
from fastapi import APIRouter, Query
from typing import List, Optional, Dict, Any
from app.database import get_db_connection
from app.schemas import SearchQuery, SearchResultItem, GlobalSearchRequest, GlobalSearchResponse, GlobalSearchResult
from app.engine.embeddings import vector_engine

router = APIRouter(prefix="/search", tags=["Neural Search"])

def _parse_embedding(raw_emb) -> List[float]:
    if isinstance(raw_emb, list):
        return raw_emb
    if isinstance(raw_emb, str):
        try:
            parsed = json.loads(raw_emb)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

@router.post("", response_model=List[SearchResultItem])
def hybrid_search(payload: SearchQuery):
    query_vector = vector_engine.embed(payload.query)
    query_terms = set(payload.query.lower().split())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        sql = """
            SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding,
                   d.title as doc_title, d.category as doc_category, d.file_type as doc_file_type
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.is_trash = 0
        """
        params = []
        if payload.category and payload.category != "ALL":
            sql += " AND d.category = ?"
            params.append(payload.category)
        if payload.workspace_id and payload.workspace_id != "all":
            sql += " AND d.workspace_id = ?"
            params.append(payload.workspace_id)
        if payload.file_type and payload.file_type != "all":
            sql += " AND d.file_type = ?"
            params.append(payload.file_type)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        scored_results = []
        for r in rows:
            chunk_embedding = _parse_embedding(r["embedding"]) if r["embedding"] else []
            vector_sim = vector_engine.cosine_similarity(query_vector, chunk_embedding)

            # Lexical overlap score
            chunk_lower = str(r["content"]).lower()
            term_hits = sum(1 for term in query_terms if term in chunk_lower)
            lexical_score = (term_hits / len(query_terms)) if query_terms else 0.0

            # Hybrid combined score (70% semantic vector, 30% lexical match)
            combined_score = (0.7 * vector_sim) + (0.3 * lexical_score)

            if combined_score > 0.04:
                scored_results.append(SearchResultItem(
                    document_id=str(r["document_id"]),
                    document_title=str(r["doc_title"]),
                    chunk_index=int(r["chunk_index"]),
                    content=str(r["content"]),
                    score=round(combined_score, 4),
                    category=str(r["doc_category"]),
                    file_type=str(r["doc_file_type"] or "text")
                ))

        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:payload.limit]


def _extract_snippet(text: str, query: str, max_len: int = 160) -> str:
    if not text:
        return ""
    clean = re.sub(r'\s+', ' ', text).strip()
    q_lower = query.lower()
    idx = clean.lower().find(q_lower)
    if idx == -1:
        terms = [t for t in q_lower.split() if len(t) > 2]
        for t in terms:
            idx = clean.lower().find(t)
            if idx != -1:
                break
    if idx == -1:
        return clean[:max_len] + ("..." if len(clean) > max_len else "")
    start = max(0, idx - 40)
    end = min(len(clean), start + max_len)
    snippet = clean[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(clean):
        snippet = snippet + "..."
    return snippet

@router.post("/global", response_model=GlobalSearchResponse)
def unified_global_search(payload: GlobalSearchRequest):
    query = payload.query.strip()
    if not query:
        return GlobalSearchResponse(query="", total_results=0, results=[])

    q_terms = [t.lower() for t in query.split() if len(t) > 0]
    types_to_search = set(payload.types or ["documents", "files", "notes", "tasks"])
    workspace_id = payload.workspace_id or "default"

    results = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Search Documents
        if "documents" in types_to_search:
            ws_clause = "AND (workspace_id = ? OR ? = 'all')"
            cursor.execute(f"""
                SELECT id, title, content, category, file_type, updated_at
                FROM documents
                WHERE is_trash = 0 {ws_clause}
            """, (workspace_id, workspace_id))
            docs = cursor.fetchall()
            for d in docs:
                t_lower = str(d["title"]).lower()
                c_lower = str(d["content"]).lower()
                title_hits = sum(1 for term in q_terms if term in t_lower)
                content_hits = sum(1 for term in q_terms if term in c_lower)
                if title_hits > 0 or content_hits > 0:
                    score = (title_hits * 0.5) + (content_hits * 0.2 / max(len(q_terms), 1))
                    snippet = _extract_snippet(str(d["content"]), query)
                    results.append(GlobalSearchResult(
                        id=str(d["id"]),
                        type="document",
                        title=str(d["title"]),
                        snippet=snippet,
                        score=round(min(score, 1.0), 3),
                        metadata={
                            "category": str(d["category"]),
                            "file_type": str(d["file_type"]),
                            "updated_at": str(d["updated_at"])
                        }
                    ))

        # 2. Search Cloud Storage Files
        if "files" in types_to_search:
            try:
                ws_clause = "AND (workspace_id = ? OR ? = 'all')"
                cursor.execute(f"""
                    SELECT id, filename, file_size, mime_type, file_extension, storage_path, updated_at
                    FROM storage_files
                    WHERE is_trash = 0 {ws_clause}
                """, (workspace_id, workspace_id))
                files = cursor.fetchall()
                for f in files:
                    fn_lower = str(f["filename"]).lower()
                    hits = sum(1 for term in q_terms if term in fn_lower)
                    if hits > 0 or query.lower() in fn_lower:
                        score = 0.4 + (hits * 0.2)
                        results.append(GlobalSearchResult(
                            id=str(f["id"]),
                            type="file",
                            title=str(f["filename"]),
                            snippet=f"Cloud File ({f['mime_type'] or 'binary'}) • {f['file_extension']} • {round(int(f['file_size'])/1024, 1)} KB",
                            score=round(min(score, 1.0), 3),
                            metadata={
                                "file_size": int(f["file_size"]),
                                "mime_type": str(f["mime_type"]),
                                "storage_path": str(f["storage_path"]),
                                "updated_at": str(f["updated_at"])
                            }
                        ))
            except Exception:
                pass

        # 3. Search Notes
        if "notes" in types_to_search:
            try:
                ws_clause = "AND (workspace_id = ? OR ? = 'all')"
                cursor.execute(f"""
                    SELECT id, title, content, is_pinned, linked_document_id, updated_at
                    FROM notes
                    WHERE 1=1 {ws_clause}
                """, (workspace_id, workspace_id))
                notes = cursor.fetchall()
                for n in notes:
                    t_lower = str(n["title"]).lower()
                    c_lower = str(n["content"]).lower()
                    title_hits = sum(1 for term in q_terms if term in t_lower)
                    content_hits = sum(1 for term in q_terms if term in c_lower)
                    if title_hits > 0 or content_hits > 0:
                        score = (title_hits * 0.4) + (content_hits * 0.2 / max(len(q_terms), 1))
                        snippet = _extract_snippet(str(n["content"]), query)
                        results.append(GlobalSearchResult(
                            id=str(n["id"]),
                            type="note",
                            title=str(n["title"]),
                            snippet=snippet,
                            score=round(min(score, 1.0), 3),
                            metadata={
                                "is_pinned": int(n["is_pinned"] or 0),
                                "linked_document_id": str(n["linked_document_id"] or ""),
                                "updated_at": str(n["updated_at"])
                            }
                        ))
            except Exception:
                pass

        # 4. Search Tasks
        if "tasks" in types_to_search:
            try:
                ws_clause = "AND (workspace_id = ? OR ? = 'all')"
                cursor.execute(f"""
                    SELECT id, title, description, status, priority, due_date, updated_at
                    FROM tasks
                    WHERE 1=1 {ws_clause}
                """, (workspace_id, workspace_id))
                tasks = cursor.fetchall()
                for t in tasks:
                    t_lower = str(t["title"]).lower()
                    d_lower = str(t["description"] or "").lower()
                    title_hits = sum(1 for term in q_terms if term in t_lower)
                    desc_hits = sum(1 for term in q_terms if term in d_lower)
                    if title_hits > 0 or desc_hits > 0:
                        score = (title_hits * 0.4) + (desc_hits * 0.2 / max(len(q_terms), 1))
                        snippet = str(t["description"]) if t["description"] else f"Task [{t['status'].upper()}] - Priority: {t['priority']}"
                        results.append(GlobalSearchResult(
                            id=str(t["id"]),
                            type="task",
                            title=str(t["title"]),
                            snippet=snippet[:160],
                            score=round(min(score, 1.0), 3),
                            metadata={
                                "status": str(t["status"]),
                                "priority": str(t["priority"]),
                                "due_date": str(t["due_date"] or ""),
                                "updated_at": str(t["updated_at"])
                            }
                        ))
            except Exception:
                pass

    results.sort(key=lambda x: x.score, reverse=True)
    limit = payload.limit or 20
    sliced = results[:limit]
    return GlobalSearchResponse(
        query=query,
        total_results=len(results),
        results=sliced
    )
