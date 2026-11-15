import sys
from pathlib import Path

# Ensure backend directory and project root are on sys.path for module resolution
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

for path in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app.main import app
