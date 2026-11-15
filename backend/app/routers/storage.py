import os
import uuid
import mimetypes
import hashlib
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, Response
from fastapi.responses import Response, StreamingResponse
import io

from app.database import get_db_connection
from app.auth import get_current_user
from app.engine.storage import StorageService
from app.config import DEFAULT_STORAGE_QUOTA_MB, MAX_UPLOAD_SIZE_BYTES
from app.schemas import (
    StorageFileResponse,
    StorageFileUpdate,
    StorageFolderCreate,
    StorageFolderUpdate,
    StorageFolderResponse,
    PresignedUploadRequest,
    PresignedUploadResponse,
    UploadCompleteRequest,
    FileShareCreate,
    FileShareResponse,
    StorageDashboardResponse
)

router = APIRouter(prefix="/storage", tags=["NeuralDesk Cloud Storage"])

def get_file_type_category(ext: str, mime: str) -> str:
    ext = ext.lower().lstrip(".")
    if ext in ["pdf"]:
        return "pdf"
    if ext in ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"]:
        return "image"
    if ext in ["doc", "docx", "odt", "rtf"]:
        return "document"
    if ext in ["txt", "md", "markdown", "py", "js", "ts", "json", "yaml", "yml", "html", "css", "sql"]:
        return "text"
    if ext in ["csv", "xlsx", "xls"]:
        return "spreadsheet"
    if ext in ["mp3", "wav", "ogg", "m4a", "flac"]:
        return "audio"
    if ext in ["mp4", "webm", "mov", "avi", "mkv"]:
        return "video"
    if ext in ["zip", "tar", "gz", "rar", "7z"]:
        return "archive"
    return "other"

@router.get("/status")
def get_storage_status(user: dict = Depends(get_current_user)):
    """Return cloud storage provider connection and configuration status."""
    service = StorageService.get_instance()
    status = service.get_status()
    status["quota_mb"] = DEFAULT_STORAGE_QUOTA_MB
    status["provider"] = status.get("active_provider")
    status["bucket"] = status.get("bucket_name")
    status["is_r2_active"] = status.get("r2_configured", False)
    return status

@router.get("/dashboard", response_model=StorageDashboardResponse)
def get_storage_dashboard(
    workspace_id: str = Query("default"),
    user: dict = Depends(get_current_user)
):
    """Aggregated cloud storage telemetry: files, folders, usage, quota, and distributions."""
    service = StorageService.get_instance()
    status = service.get_status()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Total files and bytes
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(file_size), 0)
            FROM storage_files
            WHERE workspace_id = ? AND is_trash = 0
        """, (workspace_id,))
        row = cursor.fetchone()
        total_files = row[0] if row else 0
        used_bytes = row[1] if row else 0

        # Total folders
        cursor.execute("SELECT COUNT(*) FROM storage_folders WHERE workspace_id = ? AND is_trash = 0", (workspace_id,))
        frow = cursor.fetchone()
        total_folders = frow[0] if frow else 0

        # File type distribution
        cursor.execute("""
            SELECT file_extension, COUNT(*)
            FROM storage_files
            WHERE workspace_id = ? AND is_trash = 0
            GROUP BY file_extension
        """, (workspace_id,))
        ext_rows = cursor.fetchall()
        distribution = {}
        for r in ext_rows:
            category = get_file_type_category(r[0] or "", "")
            distribution[category] = distribution.get(category, 0) + r[1]

        # Recent files
        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files
            WHERE workspace_id = ? AND is_trash = 0
            ORDER BY created_at DESC LIMIT 5
        """, (workspace_id,))
        recent_rows = cursor.fetchall()

        # Large files
        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files
            WHERE workspace_id = ? AND is_trash = 0
            ORDER BY file_size DESC LIMIT 5
        """, (workspace_id,))
        large_rows = cursor.fetchall()

    def map_file(r):
        return StorageFileResponse(
            id=str(r[0]),
            workspace_id=str(r[1]),
            user_id=str(r[2]),
            folder_id=str(r[3]) if r[3] else None,
            name=str(r[4]),
            original_name=str(r[5]),
            storage_key=str(r[6]),
            storage_provider=str(r[7]),
            file_size=int(r[8]),
            mime_type=str(r[9]),
            file_extension=str(r[10]),
            checksum=str(r[11] or ""),
            is_favorite=int(r[12]),
            is_trash=int(r[13]),
            version=int(r[14]),
            created_at=str(r[15]),
            updated_at=str(r[16]),
            download_url=f"/api/v1/storage/files/{r[0]}/download"
        )

    quota_bytes = DEFAULT_STORAGE_QUOTA_MB * 1024 * 1024
    used_mb = round(used_bytes / (1024 * 1024), 2)
    pct = round((used_bytes / quota_bytes) * 100, 2) if quota_bytes > 0 else 0.0

    return StorageDashboardResponse(
        total_files=total_files,
        total_folders=total_folders,
        used_storage_bytes=used_bytes,
        used_storage_mb=used_mb,
        storage_quota_mb=DEFAULT_STORAGE_QUOTA_MB,
        usage_percentage=min(100.0, pct),
        file_type_distribution=distribution,
        provider=status["active_provider"],
        provider_status=status["status"],
        is_r2_active=status["r2_configured"],
        recent_files=[map_file(r) for r in recent_rows],
        large_files=[map_file(r) for r in large_rows]
    )

@router.get("/files", response_model=List[StorageFileResponse])
def list_storage_files(
    workspace_id: str = Query("default"),
    folder_id: Optional[str] = Query(None),
    view: str = Query("active"), # active, favorites, trash
    search: Optional[str] = Query(None),
    sort_by: str = Query("date_desc"), # date_desc, date_asc, size_desc, name_asc
    user: dict = Depends(get_current_user)
):
    """List files in cloud storage with folder hierarchy and status filters."""
    query = """
        SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
               storage_provider, file_size, mime_type, file_extension, checksum,
               is_favorite, is_trash, version, created_at, updated_at
        FROM storage_files
        WHERE workspace_id = ?
    """
    params = [workspace_id]

    if view == "trash":
        query += " AND is_trash = 1"
    elif view == "favorites":
        query += " AND is_trash = 0 AND is_favorite = 1"
    else: # active
        query += " AND is_trash = 0"
        if folder_id is not None and folder_id != "":
            query += " AND folder_id = ?"
            params.append(folder_id)
        elif folder_id == "":
            query += " AND (folder_id IS NULL OR folder_id = '')"

    if search:
        query += " AND (name LIKE ? OR original_name LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s])

    # Sorting
    if sort_by == "date_asc":
        query += " ORDER BY created_at ASC"
    elif sort_by == "size_desc":
        query += " ORDER BY file_size DESC"
    elif sort_by == "name_asc":
        query += " ORDER BY name ASC"
    else:
        query += " ORDER BY created_at DESC"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append(StorageFileResponse(
            id=str(r[0]),
            workspace_id=str(r[1]),
            user_id=str(r[2]),
            folder_id=str(r[3]) if r[3] else None,
            name=str(r[4]),
            original_name=str(r[5]),
            storage_key=str(r[6]),
            storage_provider=str(r[7]),
            file_size=int(r[8]),
            mime_type=str(r[9]),
            file_extension=str(r[10]),
            checksum=str(r[11] or ""),
            is_favorite=int(r[12]),
            is_trash=int(r[13]),
            version=int(r[14]),
            created_at=str(r[15]),
            updated_at=str(r[16]),
            download_url=f"/api/v1/storage/files/{r[0]}/download"
        ))
    return results

@router.post("/upload", response_model=StorageFileResponse, status_code=201)
async def upload_file_direct(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    workspace_id: str = Form("default"),
    user: dict = Depends(get_current_user)
):
    """Direct multipart file upload to Cloudflare R2 / S3 storage with quota and checksum verification."""
    data = await file.read()
    file_size = len(data)

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload limit of {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB"
        )

    # Check quota
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(file_size), 0) FROM storage_files WHERE workspace_id = ? AND is_trash = 0", (workspace_id,))
        row = cursor.fetchone()
        used_bytes = row[0] if row else 0
        quota_bytes = DEFAULT_STORAGE_QUOTA_MB * 1024 * 1024
        if used_bytes + file_size > quota_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"Storage quota exceeded ({DEFAULT_STORAGE_QUOTA_MB} MB limit). Delete files or upgrade plan."
            )

    original_filename = file.filename or "uploaded_file"
    ext = os.path.splitext(original_filename)[1].lstrip(".")
    mime = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    file_id = str(uuid.uuid4())
    storage_key = f"{workspace_id}/{file_id[:8]}_{original_filename}"

    service = StorageService.get_instance()
    upload_meta = service.upload_file(storage_key, data, mime)
    checksum = upload_meta.get("checksum", hashlib.sha256(data).hexdigest())

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO storage_files (
                id, workspace_id, user_id, folder_id, name, original_name,
                storage_key, storage_provider, file_size, mime_type, file_extension,
                checksum, is_favorite, is_trash, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
        """, (
            file_id,
            workspace_id,
            user.get("id", "system"),
            folder_id if folder_id else None,
            original_filename,
            original_filename,
            storage_key,
            service.adapter.get_provider_name(),
            file_size,
            mime,
            ext,
            checksum
        ))

        # Log activity
        cursor.execute("""
            INSERT INTO activity_logs (id, workspace_id, user_id, action, details)
            VALUES (?, ?, ?, 'UPLOAD_FILE', ?)
        """, (str(uuid.uuid4()), workspace_id, user.get("id", "system"), f"Uploaded file: {original_filename} ({file_size} bytes)"))

        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files WHERE id = ?
        """, (file_id,))
        r = cursor.fetchone()

    return StorageFileResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        folder_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        original_name=str(r[5]),
        storage_key=str(r[6]),
        storage_provider=str(r[7]),
        file_size=int(r[8]),
        mime_type=str(r[9]),
        file_extension=str(r[10]),
        checksum=str(r[11] or ""),
        is_favorite=int(r[12]),
        is_trash=int(r[13]),
        version=int(r[14]),
        created_at=str(r[15]),
        updated_at=str(r[16]),
        download_url=f"/api/v1/storage/files/{r[0]}/download"
    )

@router.post("/upload/presign", response_model=PresignedUploadResponse)
@router.post("/upload/presigned", response_model=PresignedUploadResponse)
def get_presigned_upload_url(
    req: PresignedUploadRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generate direct browser-to-R2 presigned PUT upload URL.
    Never exposes R2 credentials to the client.
    """
    if req.file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File size exceeds upload ceiling.")

    # Check quota
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(file_size), 0) FROM storage_files WHERE workspace_id = ? AND is_trash = 0", (req.workspace_id,))
        row = cursor.fetchone()
        used_bytes = row[0] if row else 0
        if used_bytes + req.file_size > DEFAULT_STORAGE_QUOTA_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Storage quota exceeded.")

    file_id = str(uuid.uuid4())
    clean_name = os.path.basename(req.filename)
    storage_key = f"{req.workspace_id}/{file_id[:8]}_{clean_name}"
    mime = req.mime_type or mimetypes.guess_type(clean_name)[0] or "application/octet-stream"

    service = StorageService.get_instance()
    presign_data = service.generate_presigned_upload_url(storage_key, mime)

    return PresignedUploadResponse(
        upload_url=presign_data["upload_url"],
        method=presign_data["method"],
        headers=presign_data["headers"],
        storage_key=storage_key,
        provider=presign_data["provider"],
        expires_in=presign_data["expires_in"],
        file_id=file_id
    )

@router.post("/upload/complete", response_model=StorageFileResponse)
def complete_presigned_upload(
    req: UploadCompleteRequest,
    user: dict = Depends(get_current_user)
):
    """
    Verify that direct cloud upload finished successfully and index into database.
    Verifies that the object actually exists in R2/storage.
    """
    service = StorageService.get_instance()
    obj_info = service.verify_upload(req.storage_key)

    if not obj_info and service.adapter.is_configured():
        raise HTTPException(status_code=400, detail="Uploaded object could not be verified in cloud storage.")

    actual_size = obj_info["size"] if obj_info else req.file_size
    file_id = str(uuid.uuid4())
    original_name = os.path.basename(req.filename)
    ext = os.path.splitext(original_name)[1].lstrip(".")
    mime = req.mime_type or mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    checksum = req.checksum or (obj_info.get("etag") if obj_info else "")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO storage_files (
                id, workspace_id, user_id, folder_id, name, original_name,
                storage_key, storage_provider, file_size, mime_type, file_extension,
                checksum, is_favorite, is_trash, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1)
        """, (
            file_id,
            req.workspace_id,
            user.get("id", "system"),
            req.folder_id if req.folder_id else None,
            original_name,
            original_name,
            req.storage_key,
            service.adapter.get_provider_name(),
            actual_size,
            mime,
            ext,
            checksum
        ))

        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files WHERE id = ?
        """, (file_id,))
        r = cursor.fetchone()

    return StorageFileResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        folder_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        original_name=str(r[5]),
        storage_key=str(r[6]),
        storage_provider=str(r[7]),
        file_size=int(r[8]),
        mime_type=str(r[9]),
        file_extension=str(r[10]),
        checksum=str(r[11] or ""),
        is_favorite=int(r[12]),
        is_trash=int(r[13]),
        version=int(r[14]),
        created_at=str(r[15]),
        updated_at=str(r[16]),
        download_url=f"/api/v1/storage/files/{r[0]}/download"
    )

@router.get("/files/{file_id}", response_model=StorageFileResponse)
def get_file_metadata(file_id: str, user: dict = Depends(get_current_user)):
    """Fetch file details and metadata."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files WHERE id = ?
        """, (file_id,))
        r = cursor.fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="File not found")

    return StorageFileResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        folder_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        original_name=str(r[5]),
        storage_key=str(r[6]),
        storage_provider=str(r[7]),
        file_size=int(r[8]),
        mime_type=str(r[9]),
        file_extension=str(r[10]),
        checksum=str(r[11] or ""),
        is_favorite=int(r[12]),
        is_trash=int(r[13]),
        version=int(r[14]),
        created_at=str(r[15]),
        updated_at=str(r[16]),
        download_url=f"/api/v1/storage/files/{r[0]}/download"
    )

@router.get("/files/{file_id}/download-url")
def get_download_presigned_url(file_id: str, user: dict = Depends(get_current_user)):
    """Generate temporary secure download URL for Cloudflare R2 / S3 object."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_key, name FROM storage_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

    service = StorageService.get_instance()
    url = service.generate_presigned_download_url(row[0], filename=row[1])
    return {"download_url": url, "expires_in": 3600}

@router.get("/files/{file_id}/download")
def download_file_direct(file_id: str, user: dict = Depends(get_current_user)):
    """Direct stream download from cloud storage."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_key, name, mime_type, file_size FROM storage_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

    service = StorageService.get_instance()
    try:
        data = service.download_file(row[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve file: {str(e)}")

    headers = {
        "Content-Disposition": f'attachment; filename="{row[1]}"',
        "Content-Length": str(len(data))
    }
    return Response(content=data, media_type=row[2], headers=headers)

@router.get("/files/{file_id}/preview")
def preview_file_inline(file_id: str, user: dict = Depends(get_current_user)):
    """Stream file with inline Content-Disposition for browser previewing (PDF, images, text, media)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_key, name, mime_type, file_size FROM storage_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

    service = StorageService.get_instance()
    try:
        data = service.download_file(row[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview unavailable: {str(e)}")

    headers = {
        "Content-Disposition": f'inline; filename="{row[1]}"',
        "Content-Length": str(len(data))
    }
    return Response(content=data, media_type=row[2], headers=headers)

@router.put("/files/{file_id}", response_model=StorageFileResponse)
def update_file(
    file_id: str,
    req: StorageFileUpdate,
    user: dict = Depends(get_current_user)
):
    """Rename file, move to folder, or update status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM storage_files WHERE id = ?", (file_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="File not found")

        updates = []
        params = []
        if req.name is not None:
            updates.append("name = ?")
            params.append(req.name)
        if req.folder_id is not None:
            updates.append("folder_id = ?")
            params.append(req.folder_id if req.folder_id != "" else None)
        if req.is_favorite is not None:
            updates.append("is_favorite = ?")
            params.append(req.is_favorite)
        if req.is_trash is not None:
            updates.append("is_trash = ?")
            params.append(req.is_trash)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(file_id)
            cursor.execute(f"UPDATE storage_files SET {', '.join(updates)} WHERE id = ?", params)

        cursor.execute("""
            SELECT id, workspace_id, user_id, folder_id, name, original_name, storage_key,
                   storage_provider, file_size, mime_type, file_extension, checksum,
                   is_favorite, is_trash, version, created_at, updated_at
            FROM storage_files WHERE id = ?
        """, (file_id,))
        r = cursor.fetchone()

    return StorageFileResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        folder_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        original_name=str(r[5]),
        storage_key=str(r[6]),
        storage_provider=str(r[7]),
        file_size=int(r[8]),
        mime_type=str(r[9]),
        file_extension=str(r[10]),
        checksum=str(r[11] or ""),
        is_favorite=int(r[12]),
        is_trash=int(r[13]),
        version=int(r[14]),
        created_at=str(r[15]),
        updated_at=str(r[16]),
        download_url=f"/api/v1/storage/files/{r[0]}/download"
    )

@router.post("/files/{file_id}/favorite")
def toggle_file_favorite(file_id: str, user: dict = Depends(get_current_user)):
    """Toggle file favorite bookmark."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_favorite FROM storage_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        new_val = 0 if row[0] else 1
        cursor.execute("UPDATE storage_files SET is_favorite = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_val, file_id))
    return {"id": file_id, "is_favorite": new_val}

@router.delete("/files/{file_id}")
@router.post("/files/{file_id}/trash")
def delete_file_to_trash(file_id: str, user: dict = Depends(get_current_user)):
    """Soft-delete file to trash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE storage_files SET is_trash = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (file_id,))
    return {"message": "File moved to trash", "id": file_id, "status": "moved_to_trash"}

@router.post("/files/{file_id}/restore")
def restore_file_from_trash(file_id: str, user: dict = Depends(get_current_user)):
    """Restore file from trash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE storage_files SET is_trash = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (file_id,))
    return {"message": "File restored", "id": file_id, "status": "restored"}

@router.delete("/files/{file_id}/permanent")
def delete_file_permanently(file_id: str, user: dict = Depends(get_current_user)):
    """Permanently delete file from cloud storage and database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT storage_key FROM storage_files WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")

        storage_key = row[0]
        # Remove object from storage
        StorageService.get_instance().delete_file(storage_key)
        # Delete from database
        cursor.execute("DELETE FROM storage_files WHERE id = ?", (file_id,))
        cursor.execute("DELETE FROM file_shares WHERE file_id = ?", (file_id,))

    return {"message": "File permanently deleted", "id": file_id, "status": "permanently_deleted"}

@router.post("/bulk/delete")
def bulk_delete_files(file_ids: List[str], user: dict = Depends(get_current_user)):
    """Bulk move multiple files to trash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for fid in file_ids:
            cursor.execute("UPDATE storage_files SET is_trash = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (fid,))
    return {"message": f"Moved {len(file_ids)} files to trash", "count": len(file_ids)}

# ================= FOLDERS =================
@router.get("/folders", response_model=List[StorageFolderResponse])
def list_folders(
    workspace_id: str = Query("default"),
    user: dict = Depends(get_current_user)
):
    """List storage folders with file counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.workspace_id, f.user_id, f.parent_id, f.name, f.color, f.is_trash,
                   f.created_at, f.updated_at,
                   (SELECT COUNT(*) FROM storage_files sf WHERE sf.folder_id = f.id AND sf.is_trash = 0) as file_count
            FROM storage_folders f
            WHERE f.workspace_id = ? AND f.is_trash = 0
            ORDER BY f.name ASC
        """, (workspace_id,))
        rows = cursor.fetchall()

    return [
        StorageFolderResponse(
            id=str(r[0]),
            workspace_id=str(r[1]),
            user_id=str(r[2]),
            parent_id=str(r[3]) if r[3] else None,
            name=str(r[4]),
            color=str(r[5] or "#e6a23c"),
            is_trash=int(r[6]),
            created_at=str(r[7]),
            updated_at=str(r[8]),
            file_count=int(r[9] or 0)
        )
        for r in rows
    ]

@router.post("/folders", response_model=StorageFolderResponse, status_code=201)
def create_folder(
    req: StorageFolderCreate,
    user: dict = Depends(get_current_user)
):
    """Create a new folder in storage workspace."""
    folder_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO storage_folders (id, workspace_id, user_id, parent_id, name, color)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            folder_id,
            req.workspace_id,
            user.get("id", "system"),
            req.parent_id,
            req.name,
            req.color
        ))
        cursor.execute("SELECT id, workspace_id, user_id, parent_id, name, color, is_trash, created_at, updated_at FROM storage_folders WHERE id = ?", (folder_id,))
        r = cursor.fetchone()

    return StorageFolderResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        parent_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        color=str(r[5]),
        is_trash=int(r[6]),
        created_at=str(r[7]),
        updated_at=str(r[8]),
        file_count=0
    )

@router.put("/folders/{folder_id}", response_model=StorageFolderResponse)
@router.patch("/folders/{folder_id}", response_model=StorageFolderResponse)
def update_folder(
    folder_id: str,
    req: StorageFolderUpdate,
    user: dict = Depends(get_current_user)
):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, color FROM storage_folders WHERE id = ?", (folder_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Folder not found")
        new_name = req.name if req.name is not None else existing[0]
        new_color = req.color if req.color is not None else existing[1]
        cursor.execute("""
            UPDATE storage_folders
            SET name = ?, color = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_name, new_color, folder_id))
        cursor.execute("""
            SELECT f.id, f.workspace_id, f.user_id, f.parent_id, f.name, f.color, f.is_trash,
                   f.created_at, f.updated_at,
                   (SELECT COUNT(*) FROM storage_files sf WHERE sf.folder_id = f.id AND sf.is_trash = 0) as file_count
            FROM storage_folders f WHERE f.id = ?
        """, (folder_id,))
        r = cursor.fetchone()
    return StorageFolderResponse(
        id=str(r[0]),
        workspace_id=str(r[1]),
        user_id=str(r[2]),
        parent_id=str(r[3]) if r[3] else None,
        name=str(r[4]),
        color=str(r[5] or "#e6a23c"),
        is_trash=int(r[6]),
        created_at=str(r[7]),
        updated_at=str(r[8]),
        file_count=int(r[9] or 0)
    )

@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: str, user: dict = Depends(get_current_user)):
    """Move folder and all its contents to trash."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE storage_folders SET is_trash = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (folder_id,))
        cursor.execute("UPDATE storage_files SET is_trash = 1, updated_at = CURRENT_TIMESTAMP WHERE folder_id = ?", (folder_id,))
    return {"message": "Folder moved to trash", "id": folder_id}

# ================= SHARING =================
@router.post("/files/{file_id}/share", response_model=FileShareResponse)
def create_file_share(
    file_id: str,
    req: FileShareCreate,
    user: dict = Depends(get_current_user)
):
    """Create persistent public share link with token."""
    share_id = str(uuid.uuid4())
    token = uuid.uuid4().hex[:16]
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours or 72)).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM storage_files WHERE id = ?", (file_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="File not found")

        cursor.execute("""
            INSERT INTO file_shares (id, file_id, token, access_type, expires_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (share_id, file_id, token, req.access_type, expires_at, user.get("id", "system")))

    return FileShareResponse(
        id=share_id,
        file_id=file_id,
        token=token,
        access_type=req.access_type,
        share_url=f"/share/file/{token}",
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc).isoformat()
    )

@router.get("/shared/{token}")
@router.get("/share/{token}")
def get_shared_file(token: str):
    """Public read access to shared cloud file by token."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.file_id, s.access_type, s.expires_at,
                   f.name, f.file_size, f.mime_type, f.file_extension
            FROM file_shares s
            JOIN storage_files f ON s.file_id = f.id
            WHERE s.token = ?
        """, (token,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Shared link not found or expired")

        # Check expiration
        if row[3]:
            try:
                exp = datetime.fromisoformat(row[3])
                if datetime.now(timezone.utc) > exp:
                    raise HTTPException(status_code=410, detail="Shared link has expired")
            except Exception:
                pass

        # Increment download counter
        cursor.execute("UPDATE file_shares SET download_count = download_count + 1 WHERE token = ?", (token,))

    file_info = {
        "id": row[1],
        "name": row[4],
        "file_size": row[5],
        "mime_type": row[6],
        "file_extension": row[7],
        "download_url": f"/api/v1/storage/files/{row[1]}/download"
    }
    return {
        "share_id": row[0],
        "file_id": row[1],
        "file": file_info,
        "name": row[4],
        "file_size": row[5],
        "mime_type": row[6],
        "file_extension": row[7],
        "access_type": row[2],
        "download_url": f"/api/v1/storage/files/{row[1]}/download"
    }
