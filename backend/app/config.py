import os
import shutil
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Database Configuration (PostgreSQL / Neon / Supabase or local SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")

def get_db_path() -> str:
    # 1. Explicit environment variable override
    if os.environ.get("DB_PATH"):
        return os.environ["DB_PATH"]

    # 2. Serverless / Vercel runtime detection
    is_serverless = bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    )

    if is_serverless:
        tmp_dir = Path(tempfile.gettempdir())
        tmp_db = tmp_dir / "neuraldesk.db"
        seed_db = DATA_DIR / "neuraldesk.db"

        # Copy existing seed database if present and target doesn't exist yet
        if not tmp_db.exists() and seed_db.exists():
            try:
                shutil.copy2(str(seed_db), str(tmp_db))
            except Exception:
                pass
        return str(tmp_db)

    # 3. Local persistent storage with write-permission verification
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        test_file = DATA_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
        return str(DATA_DIR / "neuraldesk.db")
    except (OSError, PermissionError):
        tmp_dir = Path(tempfile.gettempdir())
        return str(tmp_dir / "neuraldesk.db")

DB_PATH = get_db_path()
DEFAULT_CHUNK_SIZE = 400
DEFAULT_CHUNK_OVERLAP = 80
SIMILARITY_THRESHOLD = 0.15
API_PREFIX = "/api/v1"

# Cloudflare R2 / S3 Storage Configuration
STORAGE_PROVIDER = os.environ.get("STORAGE_PROVIDER", "r2").lower()
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
R2_REGION = os.environ.get("R2_REGION", "auto").strip()
PRESIGNED_URL_TTL_SECONDS = int(os.environ.get("PRESIGNED_URL_TTL_SECONDS", "3600"))

# Constructed R2 endpoint if account id provided
if R2_ACCOUNT_ID and not os.environ.get("R2_ENDPOINT"):
    R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
else:
    R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "").strip()

# Local storage fallback directory
def get_local_storage_dir() -> Path:
    is_serverless = bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    )
    if is_serverless:
        p = Path(tempfile.gettempdir()) / "neuraldesk_storage"
    else:
        p = DATA_DIR / "storage"
    p.mkdir(parents=True, exist_ok=True)
    return p

LOCAL_STORAGE_DIR = get_local_storage_dir()

# Storage Quotas & Limits
DEFAULT_STORAGE_QUOTA_MB = int(os.environ.get("STORAGE_QUOTA_MB", "500"))
MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024))) # 100MB default
