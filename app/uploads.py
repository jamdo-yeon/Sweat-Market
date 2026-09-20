import os
from pathlib import Path


UPLOAD_ROOT = Path("/tmp/sweatmarket_uploads") if os.getenv("VERCEL") else Path("static")
UPLOAD_URL_PREFIX = "/uploads" if os.getenv("VERCEL") else "/static"


def upload_directory(name: str) -> Path:
    directory = UPLOAD_ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    return directory
