import sqlite3
import json
from typing import List, Dict
from app.engine.embeddings import vector_engine
from app.config import SIMILARITY_THRESHOLD

def recompute_document_edges(conn: sqlite3.Connection, doc_id: str):
    cursor = conn.cursor()
    
    # Remove existing edges connected to this doc
    cursor.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (doc_id, doc_id))
    
    # Get current doc info
    cursor.execute("SELECT id, tags FROM documents WHERE id = ?", (doc_id,))
    current_doc = cursor.fetchone()
    if not current_doc:
        return
    
    current_tags = set(json.loads(current_doc["tags"]))
    
    # Fetch embedding for current doc chunks (average pooling)
    cursor.execute("SELECT embedding FROM document_chunks WHERE document_id = ?", (doc_id,))
    chunk_rows = cursor.fetchall()
    if not chunk_rows:
        return
        
    avg_vector = [0.0] * vector_engine.dimensions
    valid_chunks = 0
    for r in chunk_rows:
        if r["embedding"]:
            emb = json.loads(r["embedding"])
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
        other_tags = set(json.loads(other["tags"]))
        
        # Check tag overlap
        tag_overlap = len(current_tags.intersection(other_tags))
        
        # Check vector similarity
        cursor.execute("SELECT embedding FROM document_chunks WHERE document_id = ?", (other_id,))
        o_chunk_rows = cursor.fetchall()
        o_avg = [0.0] * vector_engine.dimensions
        o_valid = 0
        for orow in o_chunk_rows:
            if orow["embedding"]:
                o_emb = json.loads(orow["embedding"])
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

def get_graph_data(conn: sqlite3.Connection) -> Dict[str, List]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category FROM documents")
    docs = cursor.fetchall()
    
    cursor.execute("SELECT source_id, target_id, weight, relation_type FROM graph_edges")
    edges = cursor.fetchall()
    
    nodes = []
    for d in docs:
        nodes.append({
            "id": d["id"],
            "label": d["title"],
            "category": d["category"],
            "size": 18
        })
        
    edge_list = []
    for e in edges:
        edge_list.append({
            "source": e["source_id"],
            "target": e["target_id"],
            "weight": e["weight"],
            "relation": e["relation_type"]
        })
        
    return {"nodes": nodes, "edges": edge_list}
