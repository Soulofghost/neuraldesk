import os
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_storage_status():
    res = client.get("/api/v1/storage/status")
    assert res.status_code == 200
    data = res.json()
    assert "provider" in data
    assert "status" in data
    assert "bucket" in data
    assert "is_r2_active" in data
    # When credentials are not configured, it honestly reports local storage fallback
    assert data["provider"] in ["cloudflare_r2", "local_storage"]

def test_storage_dashboard():
    res = client.get("/api/v1/storage/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert "total_files" in data
    assert "total_folders" in data
    assert "used_storage_bytes" in data
    assert "used_storage_mb" in data
    assert "storage_quota_mb" in data
    assert "usage_percentage" in data
    assert "file_type_distribution" in data
    assert "provider" in data

def test_folder_crud():
    # 1. Create folder
    create_res = client.post("/api/v1/storage/folders", json={
        "name": "Research Papers",
        "color": "#e6a23c",
        "workspace_id": "default"
    })
    assert create_res.status_code == 201
    folder = create_res.json()
    folder_id = folder["id"]
    assert folder["name"] == "Research Papers"

    # 2. List folders
    list_res = client.get("/api/v1/storage/folders?workspace_id=default")
    assert list_res.status_code == 200
    folders = list_res.json()
    assert any(f["id"] == folder_id for f in folders)

    # 3. Update folder
    update_res = client.put(f"/api/v1/storage/folders/{folder_id}", json={
        "name": "AI & Systems Research",
        "color": "#38bdf8"
    })
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "AI & Systems Research"

    # 4. Delete folder
    del_res = client.delete(f"/api/v1/storage/folders/{folder_id}")
    assert del_res.status_code == 200

def test_file_upload_and_lifecycle():
    # 1. Direct File Upload
    file_content = b"NeuralDesk 2.0 High Performance Knowledge Storage"
    files = {"file": ("architecture_spec.txt", io.BytesIO(file_content), "text/plain")}
    data = {"workspace_id": "default"}

    upload_res = client.post("/api/v1/storage/upload", files=files, data=data)
    assert upload_res.status_code == 201
    file_data = upload_res.json()
    file_id = file_data["id"]
    assert file_data["name"] == "architecture_spec.txt"
    assert file_data["file_size"] == len(file_content)
    assert file_data["file_extension"] == "txt"
    assert len(file_data["checksum"]) == 64 # SHA-256

    # 2. Get file details
    detail_res = client.get(f"/api/v1/storage/files/{file_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == file_id

    # 3. File Preview
    preview_res = client.get(f"/api/v1/storage/files/{file_id}/preview")
    assert preview_res.status_code == 200
    assert preview_res.content == file_content

    # 4. File Download
    download_res = client.get(f"/api/v1/storage/files/{file_id}/download")
    assert download_res.status_code == 200
    assert "attachment" in download_res.headers.get("Content-Disposition", "")
    assert download_res.content == file_content

    # 5. Toggle favorite
    fav_res = client.post(f"/api/v1/storage/files/{file_id}/favorite")
    assert fav_res.status_code == 200
    assert fav_res.json()["is_favorite"] == 1

    # 6. Create share link
    share_res = client.post(f"/api/v1/storage/files/{file_id}/share", json={
        "access_type": "public_read",
        "expires_in_hours": 24
    })
    assert share_res.status_code == 200
    share_data = share_res.json()
    assert "token" in share_data
    token = share_data["token"]

    # 7. Access via share token
    public_res = client.get(f"/api/v1/storage/share/{token}")
    assert public_res.status_code == 200
    assert public_res.json()["file"]["id"] == file_id

    # 8. Soft Delete (Move to Trash)
    trash_res = client.post(f"/api/v1/storage/files/{file_id}/trash")
    assert trash_res.status_code == 200
    assert trash_res.json()["status"] == "moved_to_trash"

    # 9. Restore from Trash
    restore_res = client.post(f"/api/v1/storage/files/{file_id}/restore")
    assert restore_res.status_code == 200
    assert restore_res.json()["status"] == "restored"

    # 10. Permanent Delete
    perm_res = client.delete(f"/api/v1/storage/files/{file_id}/permanent")
    assert perm_res.status_code == 200
    assert perm_res.json()["status"] == "permanently_deleted"

def test_presigned_upload_flow():
    req_payload = {
        "filename": "neural_weights.bin",
        "file_size": 2048,
        "mime_type": "application/octet-stream",
        "workspace_id": "default"
    }
    presigned_res = client.post("/api/v1/storage/upload/presigned", json=req_payload)
    assert presigned_res.status_code == 200
    data = presigned_res.json()
    assert "upload_url" in data
    assert "storage_key" in data
    assert "provider" in data

def test_document_versions_and_diff():
    # 1. Create a Document
    doc_res = client.post("/api/v1/documents", json={
        "title": "Consensus Specifications",
        "content": "Initial Draft: Paxos protocol requirements and leader election.",
        "category": "Engineering"
    })
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # 2. Update Document to generate Version 2
    update_res = client.put(f"/api/v1/documents/{doc_id}", json={
        "title": "Consensus Specifications v2",
        "content": "Revision 2: Added Raft state machine log replication details and RPC heartbeat checks."
    })
    assert update_res.status_code == 200

    # 3. Retrieve Version History
    versions_res = client.get(f"/api/v1/documents/{doc_id}/versions")
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) >= 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1

    # 4. Compare Versions
    diff_res = client.post(f"/api/v1/documents/{doc_id}/compare", json={
        "document_id": doc_id,
        "version_a": 1,
        "version_b": 2
    })
    assert diff_res.status_code == 200
    diff = diff_res.json()
    assert diff["additions"] > 0
    assert diff["deletions"] > 0
    assert "diff_text" in diff

    # 5. Restore Version 1
    restore_res = client.post(f"/api/v1/documents/{doc_id}/restore-version/1")
    assert restore_res.status_code == 200
    assert "Initial Draft" in restore_res.json()["content"]

def test_bulk_document_actions():
    # Create two test documents
    doc1 = client.post("/api/v1/documents", json={"title": "Bulk Doc 1", "content": "Sample content 1", "category": "General"}).json()
    doc2 = client.post("/api/v1/documents", json={"title": "Bulk Doc 2", "content": "Sample content 2", "category": "General"}).json()
    ids = [doc1["id"], doc2["id"]]

    # Bulk favorite
    fav_res = client.post("/api/v1/documents/bulk", json={
        "action": "favorite",
        "document_ids": ids
    })
    assert fav_res.status_code == 200

    # Bulk categorize
    cat_res = client.post("/api/v1/documents/bulk", json={
        "action": "categorize",
        "document_ids": ids,
        "category": "Operations"
    })
    assert cat_res.status_code == 200

    # Bulk trash
    trash_res = client.post("/api/v1/documents/bulk", json={
        "action": "trash",
        "document_ids": ids
    })
    assert trash_res.status_code == 200

    # Bulk restore
    rest_res = client.post("/api/v1/documents/bulk", json={
        "action": "restore",
        "document_ids": ids
    })
    assert rest_res.status_code == 200

    # Bulk delete
    del_res = client.post("/api/v1/documents/bulk", json={
        "action": "delete",
        "document_ids": ids
    })
    assert del_res.status_code == 200

def test_unified_global_search():
    # Create document
    client.post("/api/v1/documents", json={
        "title": "Quantum Annealing Whitepaper",
        "content": "Adiabatic quantum computation exploits tunneling between ground states.",
        "category": "Research"
    })

    # Search for quantum
    search_res = client.post("/api/v1/search/global", json={
        "query": "Quantum Annealing",
        "workspace_id": "default"
    })
    assert search_res.status_code == 200
    res_data = search_res.json()
    assert res_data["total_results"] > 0
    match = next((r for r in res_data["results"] if "Quantum" in r["title"]), None)
    assert match is not None
    assert match["type"] == "document"
    assert match["score"] > 0.3

def test_advanced_ai_intelligence():
    sample_text = """
    Acme Corp engineering roadmap for 2026.
    By March 15, 2026, the team must implement Cloudflare R2 object storage integration.
    In Q3 2026, deploy Postgres Neon database migration and enable subword vector retrieval.
    Ensure end-to-end automated testing passes across all environments.
    """

    # 1. Timeline extraction
    t_res = client.post("/api/v1/intelligence/timeline", json={"content": sample_text})
    assert t_res.status_code == 200
    timeline = t_res.json()["timeline"]
    assert len(timeline) >= 2

    # 2. Document classification
    c_res = client.post("/api/v1/intelligence/classify", json={"content": sample_text})
    assert c_res.status_code == 200
    cls_data = c_res.json()
    assert "suggested_category" in cls_data
    assert "word_count" in cls_data
    assert "reading_time_minutes" in cls_data

    # 3. Document comparison
    comp_res = client.post("/api/v1/intelligence/compare-documents", json={
        "text_a": "FastAPI with PostgreSQL database persistence and automated migrations.",
        "text_b": "FastAPI with Cloudflare R2 object storage and S3 compatible presigned URLs."
    })
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert "semantic_similarity" in comp_data
    assert "common_concepts" in comp_data
