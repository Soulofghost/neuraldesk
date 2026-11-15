import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import init_db, is_postgres_configured, get_db_connection
from app.routers import (
    auth,
    workspaces,
    documents,
    intelligence,
    chat,
    notes,
    tasks,
    search,
    graph,
    collaboration,
    analytics,
    admin
)
from app.schemas import SystemStats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("neuraldesk")

app = FastAPI(
    title="NeuralDesk 2.0 API",
    description="Enterprise AI-Powered Knowledge Management Platform with Subword Vector Retrieval, Graph Topology & Conversational RAG",
    version="2.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please verify your request parameters."}
    )

# Initialize database schema and tables
init_db()

# Mount All Core Application API Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(intelligence.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")
app.include_router(collaboration.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")

@app.get("/api/v1/health")
def health_check():
    db_engine = "postgresql" if is_postgres_configured() else "sqlite"
    return {
        "status": "healthy",
        "service": "NeuralDesk Knowledge Engine",
        "version": "2.0.0",
        "database": f"{db_engine}_active"
    }

@app.get("/api/v1/stats", response_model=SystemStats)
def system_stats():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) as cnt FROM documents WHERE is_trash = 0")
        doc_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT count(*) as cnt FROM document_chunks")
        chunk_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT count(*) as cnt FROM graph_edges")
        edge_count = cursor.fetchone()["cnt"]

        db_engine = "PostgreSQL (Neon/Supabase)" if is_postgres_configured() else "SQLite WAL"
        return SystemStats(
            total_documents=int(doc_count),
            total_chunks=int(chunk_count),
            total_edges=int(edge_count),
            database_engine=db_engine,
            version="2.0.0",
            status="operational"
        )

@app.get("/api/docs", include_in_schema=False)
def api_docs_redirect():
    return RedirectResponse(url="/docs")

@app.get("/api/openapi.json", include_in_schema=False)
def api_openapi_redirect():
    return RedirectResponse(url="/openapi.json")

# Mount static frontend when running locally (on Vercel, static assets are served from public/)
if not os.environ.get("VERCEL"):
    root_dir = Path(__file__).resolve().parent.parent.parent
    frontend_dir = root_dir / "frontend"
    if not frontend_dir.exists():
        frontend_dir = root_dir / "public"

    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
