from fastapi import APIRouter
from app.database import get_db_connection
from app.schemas import GraphResponse
from app.engine.graph import get_graph_data, recompute_document_edges

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

@router.get("", response_model=GraphResponse)
def fetch_graph():
    with get_db_connection() as conn:
        data = get_graph_data(conn)
        return GraphResponse(
            nodes=data["nodes"],
            edges=data["edges"]
        )

@router.post("/recompute", response_model=GraphResponse)
def recompute_all_edges():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM documents")
        docs = cursor.fetchall()
        for d in docs:
            recompute_document_edges(conn, d["id"])
        conn.commit()
        data = get_graph_data(conn)
        return GraphResponse(
            nodes=data["nodes"],
            edges=data["edges"]
        )
