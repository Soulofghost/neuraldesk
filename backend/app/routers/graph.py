from fastapi import APIRouter
from app.database import get_db_connection
from app.schemas import GraphResponse
from app.engine.graph import get_graph_data

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

@router.get("", response_model=GraphResponse)
def fetch_graph():
    with get_db_connection() as conn:
        data = get_graph_data(conn)
        return GraphResponse(
            nodes=data["nodes"],
            edges=data["edges"]
        )
