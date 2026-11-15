import io
import uuid
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

def test_auth_workflow():
    unique_email = f"user_{uuid.uuid4().hex[:8]}@neuraldesk.io"
    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "Password123!",
        "full_name": "Alvin Senior Dev"
    })
    assert reg_res.status_code == 201
    token_data = reg_res.json()
    assert "access_token" in token_data
    assert token_data["user"]["email"] == unique_email

    # 2. Login
    login_res = client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # 3. Get profile
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_email

def test_workspace_lifecycle():
    create_res = client.post("/api/v1/workspaces", json={
        "name": "Cloud Infrastructure Lab",
        "description": "Distributed systems research workspace"
    })
    assert create_res.status_code == 201
    ws = create_res.json()
    ws_id = ws["id"]
    assert ws["name"] == "Cloud Infrastructure Lab"

    # List workspaces
    list_res = client.get("/api/v1/workspaces")
    assert list_res.status_code == 200
    assert any(w["id"] == ws_id for w in list_res.json())

    # Delete workspace
    del_res = client.delete(f"/api/v1/workspaces/{ws_id}")
    assert del_res.status_code == 200

def test_document_lifecycle():
    # 1. Create Document
    doc_payload = {
        "title": "Distributed Consensus in Raft",
        "content": "Raft is a consensus algorithm designed to be easy to understand. It is equivalent to Paxos in fault-tolerance and performance. The system elects a cluster leader to replicate state machine logs across follower nodes.",
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

def test_ai_intelligence():
    sample_text = "Vector embeddings project natural language tokens into dense continuous spaces where cosine angle indicates semantic similarity. We must implement vector indexing immediately to ensure sub-millisecond retrieval."
    
    # Summarization
    sum_res = client.post("/api/v1/intelligence/summarize", json={"content": sample_text})
    assert sum_res.status_code == 200
    assert "summary" in sum_res.json()
    assert len(sum_res.json()["key_takeaways"]) >= 1

    # Entity & Keyword extraction
    ent_res = client.post("/api/v1/intelligence/entities", json={"content": sample_text})
    assert ent_res.status_code == 200
    assert "entities" in ent_res.json()
    assert "keywords" in ent_res.json()

    # Action Items extraction
    act_res = client.post("/api/v1/intelligence/action-items", json={"content": sample_text})
    assert act_res.status_code == 200
    assert len(act_res.json()["action_items"]) >= 1

    # Grounded Q&A
    qa_res = client.post("/api/v1/intelligence/ask", json={"question": "What do vector embeddings do?"})
    assert qa_res.status_code == 200
    assert "answer" in qa_res.json()

def test_ai_chat_assistant():
    # 1. Create conversation
    conv_res = client.post("/api/v1/chat/conversations", json={"title": "Raft Architecture Discussion"})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 2. Post message
    msg_res = client.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={
        "content": "Explain how consensus algorithms elect leaders."
    })
    assert msg_res.status_code == 201
    assert msg_res.json()["role"] == "assistant"
    assert "citations" in msg_res.json()

    # 3. Retrieve messages
    list_res = client.get(f"/api/v1/chat/conversations/{conv_id}/messages")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 2

    # 4. Clean up
    client.delete(f"/api/v1/chat/conversations/{conv_id}")

def test_notes_module():
    # Create note
    note_res = client.post("/api/v1/notes", json={
        "title": "Distributed Cache Strategies",
        "content": "Write-through caching versus cache-aside in Redis clusters.",
        "tags": ["redis", "caching", "architecture"]
    })
    assert note_res.status_code == 201
    note_id = note_res.json()["id"]

    # List notes
    list_res = client.get("/api/v1/notes")
    assert list_res.status_code == 200
    assert any(n["id"] == note_id for n in list_res.json())

    # Clean up
    client.delete(f"/api/v1/notes/{note_id}")

def test_tasks_module():
    # Create task
    task_res = client.post("/api/v1/tasks", json={
        "title": "Benchmark HNSW vector indexing latency",
        "description": "Measure P99 latency across 100k chunked passages.",
        "priority": "high",
        "status": "todo"
    })
    assert task_res.status_code == 201
    task_id = task_res.json()["id"]

    # Toggle task
    toggle_res = client.post(f"/api/v1/tasks/{task_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["status"] == "done"

    # Clean up
    client.delete(f"/api/v1/tasks/{task_id}")

def test_collaboration_and_sharing():
    # Create doc
    doc_res = client.post("/api/v1/documents", json={
        "title": "Security Hardening Guidelines",
        "content": "Configure mutual TLS between microservices and rotate keys every 90 days.",
        "category": "Engineering"
    })
    doc_id = doc_res.json()["id"]

    # 1. Share Link
    share_res = client.post(f"/api/v1/collaboration/share/{doc_id}")
    assert share_res.status_code == 200
    token = share_res.json()["token"]

    # Access shared doc
    shared_access = client.get(f"/api/v1/collaboration/shared/{token}")
    assert shared_access.status_code == 200
    assert shared_access.json()["document"]["title"] == "Security Hardening Guidelines"

    # 2. Add comment
    comment_res = client.post(f"/api/v1/collaboration/comments/{doc_id}", json={
        "content": "Great overview of mutual TLS!"
    })
    assert comment_res.status_code == 201
    assert comment_res.json()["content"] == "Great overview of mutual TLS!"

    # Clean up
    client.delete(f"/api/v1/documents/{doc_id}")

def test_analytics_dashboard():
    res = client.get("/api/v1/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "total_documents" in data
    assert "storage_bytes" in data
    assert "category_distribution" in data
    assert "task_status_distribution" in data
