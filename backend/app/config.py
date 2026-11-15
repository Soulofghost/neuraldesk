import os
import shutil
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

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
