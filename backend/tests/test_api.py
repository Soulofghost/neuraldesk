import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

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
