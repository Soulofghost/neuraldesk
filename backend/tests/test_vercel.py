import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def test_vercel_static_assets_exist():
    public_dir = ROOT_DIR / "public"
    assert public_dir.exists(), "public directory must exist for Vercel CDN static serving"
    for filename in ["index.html", "style.css", "app.js"]:
        asset = public_dir / filename
        assert asset.exists(), f"public/{filename} must exist"
        assert asset.stat().st_size > 0, f"public/{filename} must not be empty"

def test_vercel_serverless_entrypoint(monkeypatch):
    # Simulate Vercel runtime environment
    monkeypatch.setenv("VERCEL", "1")
    
    from api.index import app
    client = TestClient(app)
    
    # 1. Health check
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"
    
    # 2. Redirects to OpenAPI docs
    res_docs = client.get("/api/docs", follow_redirects=False)
    assert res_docs.status_code in [302, 307]
    assert res_docs.headers["location"] == "/docs"

    res_openapi = client.get("/api/openapi.json", follow_redirects=False)
    assert res_openapi.status_code in [302, 307]
    assert res_openapi.headers["location"] == "/openapi.json"

    # 3. Document ingestion in serverless tmp SQLite environment
    res_doc = client.post("/api/v1/documents", json={
        "title": "Serverless Knowledge Architecture",
        "content": "Serverless execution models enable stateless scaling while mounting localized transient storage in /tmp.",
        "category": "Architecture",
        "tags": ["serverless", "vercel", "cloud"]
    })
    assert res_doc.status_code == 201
    doc_id = res_doc.json()["id"]

    # 4. List documents
    res_list = client.get("/api/v1/documents")
    assert res_list.status_code == 200
    assert any(d["id"] == doc_id for d in res_list.json())

    # 5. Search verification
    res_search = client.post("/api/v1/search", json={"query": "stateless scaling serverless"})
    assert res_search.status_code == 200
    assert any(item["document_id"] == doc_id for item in res_search.json())

    # 6. Graph telemetry
    res_graph = client.get("/api/v1/graph")
    assert res_graph.status_code == 200
    assert any(node["id"] == doc_id for node in res_graph.json()["nodes"])

    # 7. Clean up
    del_res = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
