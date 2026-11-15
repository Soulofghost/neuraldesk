import json
from fastapi import APIRouter
from typing import List
from app.database import get_db_connection
from app.schemas import SearchQuery, SearchResultItem
from app.engine.embeddings import vector_engine

router = APIRouter(prefix="/search", tags=["Search"])

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
                   d.title as doc_title, d.category as doc_category
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
        """
        params = []
        if payload.category:
            sql += " WHERE d.category = ?"
            params.append(payload.category)
            
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
            
            if combined_score > 0.05:
                scored_results.append(SearchResultItem(
                    document_id=str(r["document_id"]),
                    document_title=str(r["doc_title"]),
                    chunk_index=int(r["chunk_index"]),
                    content=str(r["content"]),
                    score=round(combined_score, 4),
                    category=str(r["doc_category"])
                ))
                
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:payload.limit]
