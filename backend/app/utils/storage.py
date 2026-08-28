"""
Utilities for validating and safely naming uploaded files.

Permanent document storage is handled by Supabase Storage.
This module does NOT store permanent files on the local filesystem.
"""

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


# ============================================================
# SANITIZE FILENAME
# ============================================================

def sanitize_filename(filename: str) -> str:
    """
    Convert an uploaded filename into a safe display filename.

    Example:
        "My Resume (Final).pdf"
        -> "My_Resume_Final.pdf"
    """

    filename = Path(
        filename or "document"
    ).name

    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()

    # Replace unsafe characters with underscores.
    stem = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "_",
        stem,
    )

    # Remove repeated underscores.
    stem = re.sub(
        r"_+",
        "_",
        stem,
    ).strip("._-")

    if not stem:
        stem = "document"

    return f"{stem}{suffix}"


# ============================================================
# VALIDATE UPLOAD
# ============================================================

def validate_upload(upload: UploadFile) -> str:
    """
    Validate the uploaded document extension.

    Returns:
        Lowercase file extension.

    Permanent files are stored in Supabase Storage.
    """

    filename = upload.filename or ""

    extension = Path(
        filename
    ).suffix.lower()

    allowed = {
        ext.strip().lower()
        for ext in settings.ALLOWED_UPLOAD_EXTENSIONS.split(",")
        if ext.strip()
    }

    allowed = {
        ext if ext.startswith(".") else f".{ext}"
        for ext in allowed
    }

    if extension not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed: {', '.join(sorted(allowed))}"
            ),
        )

    return extension