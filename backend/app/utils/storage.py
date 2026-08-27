"""
Filesystem utilities for per-user document storage.

Fixes vs the original implementation:
- Filenames are sanitized and prefixed with a random token before touching
  disk, closing a path-traversal / same-name-overwrite issue.
- Upload size is enforced while streaming to disk (not after the fact).
"""
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

BASE_DIR = Path(os.path.expanduser(settings.DOCUMIND_DATA_DIR))

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Strip any path components and unsafe characters from a client-supplied filename."""
    name = os.path.basename(filename or "file")
    name = _SAFE_CHARS.sub("_", name).strip("._") or "file"
    return name[:150]


def get_user_dirs(user_id: int) -> dict:
    user_root = BASE_DIR / str(user_id)
    uploads = user_root / "uploads"
    index = user_root / "index"
    uploads.mkdir(parents=True, exist_ok=True)
    index.mkdir(parents=True, exist_ok=True)
    return {"root": user_root, "uploads": uploads, "index": index}


def validate_upload(upload: UploadFile) -> str:
    """Validate extension; returns the lowercase extension or raises 400."""
    filename = upload.filename or ""
    ext = os.path.splitext(filename)[1].lower()

    print(f"UPLOAD DEBUG: filename={filename!r}, extension={ext!r}")
    print(f"UPLOAD DEBUG: allowed={settings.allowed_extensions_list}")

    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.allowed_extensions_list)}",
        )

    return ext


def save_upload_file(upload: UploadFile, destination: Path) -> int:
    """Stream-save an upload to disk, enforcing MAX_UPLOAD_MB. Returns bytes written."""
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    with destination.open("wb") as buffer:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_MB}MB limit",
                )
            buffer.write(chunk)
    return written


def build_stored_path(uploads_dir: Path, original_filename: str) -> tuple[Path, str]:
    """Returns (destination_path, safe_display_filename)."""
    safe_name = sanitize_filename(original_filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    return uploads_dir / stored_name, safe_name


def delete_file_safe(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass