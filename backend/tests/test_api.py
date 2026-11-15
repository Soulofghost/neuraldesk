import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "database" in response.json()

def test_security_headers():
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "strict-origin" in response.headers["Referrer-Policy"]

def test_system_stats():
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_documents" in stats
    assert "total_chunks" in stats
    assert "total_edges" in stats
    assert "database_engine" in stats
    assert stats["status"] == "operational"

def test_document_lifecycle():
    # 1. Create Document
    doc_payload = {
        "title": "Distributed Consensus in Raft",
        "content": "Raft is a consensus algorithm designed to be easy to understand. It is equivalent to Paxos in fault-tolerance and performance.",
        "category": "Architecture",
        "tags": ["distributed-systems", "consensus", "algorithms"]
    }
    create_res = client.post("/api/v1/documents", json=doc_payload)
    assert create_res.status_code == 201
    created_doc = create_res.json()
    doc_id = created_doc["id"]
    assert created_doc["title"] == doc_payload["title"]
    assert created_doc["chunk_count"] >= 1

    # 2. Get Document by ID
    get_res = client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id
    assert len(get_res.json()["chunks"]) >= 1

    # 3. Hybrid Search
    search_payload = {
        "query": "consensus algorithm fault-tolerance",
        "limit": 5
    }
    search_res = client.post("/api/v1/search", json=search_payload)
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) >= 1
    assert any(r["document_id"] == doc_id for r in results)

    # 4. Fetch Graph
    graph_res = client.get("/api/v1/graph")
    assert graph_res.status_code == 200
    assert any(n["id"] == doc_id for n in graph_res.json()["nodes"])

    # 5. Delete Document
    del_res = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200

def test_validation_errors():
    # Empty title
    res_bad_title = client.post("/api/v1/documents", json={
        "title": "   ",
        "content": "Valid content"
    })
    assert res_bad_title.status_code in [400, 422]

    # Empty content
    res_bad_content = client.post("/api/v1/documents", json={
        "title": "Valid title",
        "content": "   "
    })
    assert res_bad_content.status_code in [400, 422]

def test_document_upload_and_export():
    # Create test markdown file
    md_content = b"# High Availability Database Clustering\n\nClustering enables multi-master replication and automatic failover."
    file_payload = {
        "file": ("clustering.md", io.BytesIO(md_content), "text/markdown")
    }
    data_payload = {
        "category": "Engineering",
        "tags": "clustering, database, failover"
    }

    upload_res = client.post("/api/v1/documents/upload", files=file_payload, data=data_payload)
    assert upload_res.status_code == 201
    uploaded = upload_res.json()
    assert uploaded["title"] == "High Availability Database Clustering"
    assert uploaded["category"] == "Engineering"
    doc_id = uploaded["id"]

    # Export markdown
    export_md = client.get(f"/api/v1/documents/{doc_id}/export?format=md")
    assert export_md.status_code == 200
    assert "High Availability Database Clustering" in export_md.text

    # Export JSON
    export_json = client.get(f"/api/v1/documents/{doc_id}/export?format=json")
    assert export_json.status_code == 200
    assert export_json.json()["id"] == doc_id

    # Clean up
    client.delete(f"/api/v1/documents/{doc_id}")

def test_graph_recompute():
    # Recompute topology
    res = client.post("/api/v1/graph/recompute")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data
