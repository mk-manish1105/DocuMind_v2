"""
Supabase Storage service for permanent DocuMind documents.

Permanent document files are stored in Supabase Storage instead of
Render's local filesystem.

Storage structure:

    documents/
        {user_id}/
            {uuid}_{safe_filename}

Example:

    documents/
        11/
            8f3a..._resume.pdf
        12/
            42ab..._research.docx

The bucket should be PRIVATE.

This service is used only by the FastAPI backend.
"""

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from supabase import Client, create_client

from app.core.config import settings
from app.utils.storage import sanitize_filename

logger = logging.getLogger(__name__)


# ============================================================
# SUPABASE CLIENT
# ============================================================

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SECRET_KEY,
)


# ============================================================
# BUCKET
# ============================================================

BUCKET_NAME = settings.SUPABASE_STORAGE_BUCKET


# ============================================================
# STORAGE PATH
# ============================================================

def build_storage_path(
    user_id: int,
    original_filename: str,
) -> tuple[str, str]:
    """
    Create a unique Supabase Storage object path.

    Example:

        11/8f3a..._resume.pdf
    """

    safe_name = sanitize_filename(
        original_filename
    )

    unique_name = (
        f"{uuid.uuid4().hex}_{safe_name}"
    )

    storage_path = (
        f"{user_id}/{unique_name}"
    )

    return storage_path, safe_name


# ============================================================
# UPLOAD
# ============================================================

async def upload_document(
    upload: UploadFile,
    user_id: int,
) -> tuple[str, str, int]:
    """
    Upload a permanent document to Supabase Storage.

    Returns:

        storage_path
        safe_filename
        file_size_bytes
    """

    if not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    storage_path, safe_name = build_storage_path(
        user_id,
        upload.filename,
    )

    max_bytes = (
        settings.MAX_UPLOAD_MB
        * 1024
        * 1024
    )

    total_bytes = 0
    contents = bytearray()

    try:

        # ----------------------------------------------------
        # Read upload in chunks and enforce size limit.
        # ----------------------------------------------------

        while True:

            chunk = await upload.read(
                1024 * 1024
            )

            if not chunk:
                break

            total_bytes += len(chunk)

            if total_bytes > max_bytes:

                raise HTTPException(
                    status_code=(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                    ),
                    detail=(
                        f"File exceeds the "
                        f"{settings.MAX_UPLOAD_MB}MB limit."
                    ),
                )

            contents.extend(chunk)

        if total_bytes == 0:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        # ----------------------------------------------------
        # Upload to private Supabase bucket.
        # ----------------------------------------------------

        logger.info(
            "SUPABASE UPLOAD START | "
            "user_id=%s | path=%s | size=%d",
            user_id,
            storage_path,
            total_bytes,
        )

        supabase.storage.from_(
            BUCKET_NAME
        ).upload(
            path=storage_path,
            file=bytes(contents),
            file_options={
                "content-type": (
                    upload.content_type
                    or "application/octet-stream"
                ),
                "upsert": "false",
            },
        )

        logger.info(
            "SUPABASE UPLOAD COMPLETE | "
            "user_id=%s | path=%s",
            user_id,
            storage_path,
        )

        return (
            storage_path,
            safe_name,
            total_bytes,
        )

    except HTTPException:
        raise

    except Exception as exc:

        logger.exception(
            "SUPABASE UPLOAD FAILED | "
            "user_id=%s | path=%s",
            user_id,
            storage_path,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store document.",
        ) from exc

    finally:

        contents.clear()

        try:
            await upload.close()
        except Exception:
            pass


# ============================================================
# DOWNLOAD TO TEMPORARY FILE
# ============================================================

def download_document_to_temp(
    storage_path: str,
    suffix: str,
) -> Path:
    """
    Download a permanent document from Supabase Storage
    into a temporary Render filesystem file.

    The temporary file exists only during document processing.

    Caller is responsible for deleting it.
    """

    if not storage_path:
        raise ValueError(
            "Storage path cannot be empty."
        )

    try:

        logger.info(
            "SUPABASE DOWNLOAD START | path=%s",
            storage_path,
        )

        data = (
            supabase.storage
            .from_(BUCKET_NAME)
            .download(storage_path)
        )

        if not data:

            raise RuntimeError(
                "Supabase returned an empty document."
            )

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        ) as temp_file:

            temp_file.write(data)

            temp_path = Path(
                temp_file.name
            )

        logger.info(
            "SUPABASE DOWNLOAD COMPLETE | "
            "temporary_path=%s",
            temp_path,
        )

        return temp_path

    except Exception as exc:

        logger.exception(
            "SUPABASE DOWNLOAD FAILED | path=%s",
            storage_path,
        )

        raise RuntimeError(
            "Could not download document from storage."
        ) from exc


# ============================================================
# DELETE
# ============================================================

def delete_document(
    storage_path: str,
) -> None:
    """
    Delete a permanent document from Supabase Storage.

    Raises an exception if deletion fails so the caller can
    keep the database state consistent.
    """

    if not storage_path:
        return

    try:

        logger.info(
            "SUPABASE DELETE START | path=%s",
            storage_path,
        )

        supabase.storage.from_(
            BUCKET_NAME
        ).remove(
            [storage_path]
        )

        logger.info(
            "SUPABASE DELETE COMPLETE | path=%s",
            storage_path,
        )

    except Exception as exc:

        logger.exception(
            "SUPABASE DELETE FAILED | path=%s",
            storage_path,
        )

        raise RuntimeError(
            "Could not delete document from storage."
        ) from exc