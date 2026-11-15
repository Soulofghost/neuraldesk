from fastapi import APIRouter, Query
from typing import Optional
from app.database import get_db_connection
from app.schemas import GraphResponse
from app.engine.graph import get_graph_data, recompute_document_edges

router = APIRouter(prefix="/graph", tags=["Knowledge Graph 2.0"])

@router.get("", response_model=GraphResponse)
def fetch_graph(workspace_id: Optional[str] = Query(None)):
    with get_db_connection() as conn:
        data = get_graph_data(conn)
        # If workspace filtered, filter nodes and edges
        if workspace_id and workspace_id != "all":
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM documents WHERE workspace_id = ?", (workspace_id,))
            valid_ids = {r["id"] for r in cursor.fetchall()}
            nodes = [n for n in data["nodes"] if n["id"] in valid_ids]
            edges = [e for e in data["edges"] if e["source"] in valid_ids and e["target"] in valid_ids]
            return GraphResponse(nodes=nodes, edges=edges)

        return GraphResponse(
            nodes=data["nodes"],
            edges=data["edges"]
        )

@router.post("/recompute", response_model=GraphResponse)
def recompute_all_edges():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE is_trash = 0")
        docs = cursor.fetchall()
        for d in docs:
            recompute_document_edges(conn, d["id"])
        conn.commit()
        data = get_graph_data(conn)
        return GraphResponse(
            nodes=data["nodes"],
            edges=data["edges"]
        )
