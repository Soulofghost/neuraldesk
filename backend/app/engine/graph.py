import json
from typing import List, Dict, Any
from app.engine.embeddings import vector_engine
from app.config import SIMILARITY_THRESHOLD

def _extract_tags(raw_tags) -> set:
    if isinstance(raw_tags, list):
        return set(raw_tags)
    if isinstance(raw_tags, str):
        try:
            parsed = json.loads(raw_tags)
            return set(parsed) if isinstance(parsed, list) else set()
        except Exception:
            return set()
    return set()

def _extract_embedding(raw_emb) -> List[float]:
    if isinstance(raw_emb, list):
        return raw_emb
    if isinstance(raw_emb, str):
        try:
            parsed = json.loads(raw_emb)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

def recompute_document_edges(conn: Any, doc_id: str):
    cursor = conn.cursor()
    
    # Remove existing edges connected to this doc
    cursor.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
    
    # Get current doc info
    cursor.execute("SELECT id, tags FROM documents WHERE id = ?", (doc_id,))
    current_doc = cursor.fetchone()
    if not current_doc:
        return
    
    current_tags = _extract_tags(current_doc["tags"])
    
    # Fetch embedding for current doc chunks (average pooling)
    cursor.execute("SELECT embedding FROM document_chunks WHERE document_id = ?", (doc_id,))
    chunk_rows = cursor.fetchall()
    if not chunk_rows:
        return
        
    avg_vector = [0.0] * vector_engine.dimensions
    valid_chunks = 0
    for r in chunk_rows:
        if r["embedding"]:
            emb = _extract_embedding(r["embedding"])
            for i in range(len(emb)):
                avg_vector[i] += emb[i]
            valid_chunks += 1
            
    if valid_chunks > 0:
        avg_vector = [v / valid_chunks for v in avg_vector]
    
    # Compare with all other documents
    cursor.execute("SELECT id, tags FROM documents WHERE id != ?", (doc_id,))
    other_docs = cursor.fetchall()
    
    for other in other_docs:
        other_id = other["id"]
        other_tags = _extract_tags(other["tags"])
        
        # Check tag overlap
        tag_overlap = len(current_tags.intersection(other_tags))
        
        # Check vector similarity
        cursor.execute("SELECT embedding FROM document_chunks WHERE document_id = ?", (other_id,))
        o_chunk_rows = cursor.fetchall()
        o_avg = [0.0] * vector_engine.dimensions
        o_valid = 0
        for orow in o_chunk_rows:
            if orow["embedding"]:
                o_emb = _extract_embedding(orow["embedding"])
                for i in range(len(o_emb)):
                    o_avg[i] += o_emb[i]
                o_valid += 1
        if o_valid > 0:
            o_avg = [v / o_valid for v in o_avg]
            
        sim = vector_engine.cosine_similarity(avg_vector, o_avg)
        
        total_weight = sim + (0.15 * tag_overlap)
        if total_weight >= SIMILARITY_THRESHOLD or tag_overlap > 0:
            edge_id = f"{min(doc_id, other_id)}_{max(doc_id, other_id)}"
            relation = "semantic_similarity" if sim > 0.3 else "shared_tags"
            cursor.execute("""
                INSERT OR REPLACE INTO graph_edges (id, source_id, target_id, weight, relation_type)
                VALUES (?, ?, ?, ?, ?)
            """, (edge_id, min(doc_id, other_id), max(doc_id, other_id), round(total_weight, 3), relation))

def get_graph_data(conn: Any) -> Dict[str, List]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category FROM documents")
    docs = cursor.fetchall()
    
    cursor.execute("SELECT source_id, target_id, weight, relation_type FROM graph_edges")
    edges = cursor.fetchall()
    
    nodes = []
    for d in docs:
        nodes.append({
            "id": str(d["id"]),
            "label": str(d["title"]),
            "category": str(d["category"]),
            "size": 18
        })
        
    edge_list = []
    for e in edges:
        edge_list.append({
            "source": str(e["source_id"]),
            "target": str(e["target_id"]),
            "weight": float(e["weight"]),
            "relation": str(e["relation_type"])
        })
        
    return {
        "nodes": nodes,
        "edges": edge_list
    }
