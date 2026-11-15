import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path
from app.database import init_db, is_postgres_configured
from app.routers import documents, search, graph

app = FastAPI(
    title="NeuralDesk API",
    description="AI-Powered Knowledge Management Platform with Semantic Search & Graph Relationships",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema
init_db()

# Mount API Routers
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")

@app.get("/api/v1/health")
def health_check():
    db_engine = "postgresql" if is_postgres_configured() else "sqlite"
    return {
        "status": "healthy",
        "service": "NeuralDesk Knowledge Engine",
        "version": "1.0.0",
        "database": f"{db_engine}_active"
    }

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
