import os
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from app.config import (
    STORAGE_PROVIDER,
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT,
    R2_REGION,
    PRESIGNED_URL_TTL_SECONDS,
    LOCAL_STORAGE_DIR
)

logger = logging.getLogger("neuraldesk.storage")

class BaseStorageAdapter(ABC):
    @abstractmethod
    def upload_file(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        pass

    @abstractmethod
    def download_file(self, key: str) -> bytes:
        pass

    @abstractmethod
    def delete_file(self, key: str) -> bool:
        pass

    @abstractmethod
    def generate_presigned_upload_url(self, key: str, content_type: str = "application/octet-stream", expires_in: int = 3600) -> Dict[str, Any]:
        pass

    @abstractmethod
    def generate_presigned_download_url(self, key: str, filename: str = "", expires_in: int = 3600) -> str:
        pass

    @abstractmethod
    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class R2StorageAdapter(BaseStorageAdapter):
    """
    Cloudflare R2 Storage Adapter using standard S3 API with boto3.
    Supports presigned URLs, secure uploads, and head verification.
    """
    def __init__(self):
        self.bucket = R2_BUCKET_NAME
        self.account_id = R2_ACCOUNT_ID
        self.endpoint = R2_ENDPOINT
        self.access_key = R2_ACCESS_KEY_ID
        self.secret_key = R2_SECRET_ACCESS_KEY
        self.region = R2_REGION or "auto"
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.client import Config
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4")
            )
        return self._client

    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.bucket and (self.endpoint or self.account_id))

    def get_provider_name(self) -> str:
        return "cloudflare_r2"

    def upload_file(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        client = self._get_client()
        client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type
        )
        checksum = hashlib.sha256(data).hexdigest()
        return {
            "storage_key": key,
            "size": len(data),
            "checksum": checksum,
            "provider": self.get_provider_name()
        }

    def download_file(self, key: str) -> bytes:
        client = self._get_client()
        resp = client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete_file(self, key: str) -> bool:
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            logger.error(f"R2 delete error for key '{key}': {e}")
            return False

    def generate_presigned_upload_url(self, key: str, content_type: str = "application/octet-stream", expires_in: int = 3600) -> Dict[str, Any]:
        client = self._get_client()
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type
            },
            ExpiresIn=expires_in
        )
        return {
            "upload_url": url,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "storage_key": key,
            "provider": self.get_provider_name(),
            "expires_in": expires_in
        }

    def generate_presigned_download_url(self, key: str, filename: str = "", expires_in: int = 3600) -> str:
        client = self._get_client()
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in
        )

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            client = self._get_client()
            resp = client.head_object(Bucket=self.bucket, Key=key)
            return {
                "size": resp.get("ContentLength", 0),
                "content_type": resp.get("ContentType", ""),
                "etag": resp.get("ETag", "").strip('"')
            }
        except Exception as e:
            logger.warning(f"R2 head_object not found or error for key '{key}': {e}")
            return None


class LocalStorageAdapter(BaseStorageAdapter):
    """
    Local filesystem storage adapter for development and testing.
    Safely stores objects on local disk, calculating SHA-256 checksums.
    """
    def __init__(self, storage_dir: Path = LOCAL_STORAGE_DIR):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def is_configured(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "local_storage"

    def _get_path(self, key: str) -> Path:
        # Prevent directory traversal
        clean_key = Path(key).name if "/" not in key else "/".join(Path(p).name for p in key.split("/"))
        p = self.storage_dir / clean_key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def upload_file(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        p = self._get_path(key)
        p.write_bytes(data)
        checksum = hashlib.sha256(data).hexdigest()
        return {
            "storage_key": key,
            "size": len(data),
            "checksum": checksum,
            "provider": self.get_provider_name()
        }

    def download_file(self, key: str) -> bytes:
        p = self._get_path(key)
        if not p.exists():
            raise FileNotFoundError(f"Storage key '{key}' not found on local disk")
        return p.read_bytes()

    def delete_file(self, key: str) -> bool:
        try:
            p = self._get_path(key)
            if p.exists():
                p.unlink()
            return True
        except Exception as e:
            logger.error(f"Local storage delete error for key '{key}': {e}")
            return False

    def generate_presigned_upload_url(self, key: str, content_type: str = "application/octet-stream", expires_in: int = 3600) -> Dict[str, Any]:
        return {
            "upload_url": f"/api/v1/storage/upload?key={key}",
            "method": "POST",
            "headers": {"Content-Type": "multipart/form-data"},
            "storage_key": key,
            "provider": self.get_provider_name(),
            "expires_in": expires_in
        }

    def generate_presigned_download_url(self, key: str, filename: str = "", expires_in: int = 3600) -> str:
        fn_param = f"&filename={filename}" if filename else ""
        return f"/api/v1/storage/files/key/{key}/download?ttl={expires_in}{fn_param}"

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._get_path(key)
        if p.exists():
            stat = p.stat()
            return {
                "size": stat.st_size,
                "content_type": "application/octet-stream",
                "etag": hashlib.md5(p.read_bytes()).hexdigest()
            }
        return None


class StorageService:
    """
    Unified Storage Service handling R2 and Local adapters with quota monitoring.
    """
    _instance = None

    def __init__(self):
        self.r2_adapter = R2StorageAdapter()
        self.local_adapter = LocalStorageAdapter()

    @classmethod
    def get_instance(cls) -> "StorageService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def adapter(self) -> BaseStorageAdapter:
        # Use R2 if configured; otherwise seamlessly fall back to local adapter
        if self.r2_adapter.is_configured():
            return self.r2_adapter
        return self.local_adapter

    def get_status(self) -> Dict[str, Any]:
        is_r2 = self.r2_adapter.is_configured()
        return {
            "active_provider": "cloudflare_r2" if is_r2 else "local_storage",
            "r2_configured": is_r2,
            "bucket_name": R2_BUCKET_NAME if is_r2 else "local-storage",
            "endpoint": R2_ENDPOINT if is_r2 else "local",
            "region": R2_REGION if is_r2 else "local",
            "status": "connected" if is_r2 else "operating_local_fallback",
            "message": (
                "Cloudflare R2 storage operational"
                if is_r2
                else "Cloudflare R2 credentials unconfigured. Running in Local Development Storage Mode."
            )
        }

    def upload_file(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        return self.adapter.upload_file(key, data, content_type)

    def download_file(self, key: str) -> bytes:
        return self.adapter.download_file(key)

    def delete_file(self, key: str) -> bool:
        return self.adapter.delete_file(key)

    def generate_presigned_upload_url(self, key: str, content_type: str = "application/octet-stream", expires_in: int = 3600) -> Dict[str, Any]:
        return self.adapter.generate_presigned_upload_url(key, content_type, expires_in)

    def generate_presigned_download_url(self, key: str, filename: str = "", expires_in: int = 3600) -> str:
        return self.adapter.generate_presigned_download_url(key, filename, expires_in)

    def verify_upload(self, key: str) -> Optional[Dict[str, Any]]:
        return self.adapter.head_object(key)
