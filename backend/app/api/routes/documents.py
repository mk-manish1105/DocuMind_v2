"""
Document upload, listing, renaming, and deletion.

Permanent document architecture:

    Browser
        ↓
    FastAPI
        ↓
    Supabase Storage
        ↓
    temporary Render file
        ↓
    text extraction
        ↓
    chunking
        ↓
    embeddings
        ↓
    Supabase PostgreSQL + pgvector

IMPORTANT:

- Permanent document files are stored in Supabase Storage.
- Permanent document chunks are stored in PostgreSQL.
- Permanent embeddings are stored using pgvector.
- Render's local filesystem is used only temporarily during processing.
- No permanent FAISS index is created.
- No permanent chunk_texts.pkl file is created.
"""

import logging
from pathlib import Path
from typing import List

import numpy as np

from app.core.config import settings

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from sqlalchemy.orm import Session

from app.api.deps import get_current_user

from app.db.models import (
    Document,
    User,
)

from app.db.session import (
    SessionLocal,
    get_db,
)

from app.schemas.document import (
    DocumentRenameRequest,
    DocumentResponse,
    UploadResponse,
)

from app.services.embeddings import (
    embedding_service,
)

from app.services.extraction import (
    chunk_text,
    clean_text,
    extract_text_from_file,
)

from app.services.supabase_storage import (
    delete_document as delete_storage_document,
    download_document_to_temp,
    upload_document,
)

from app.services.vector_store import (
    delete_document_chunks,
    save_document_chunks,
)

from app.utils.storage import (
    validate_upload,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


# ============================================================
# PROCESS DOCUMENT
# ============================================================

def _process_document(
    user_id: int,
    document_id: int,
) -> None:
    """
    Background processing pipeline:

        Supabase Storage
            ↓
        temporary local file
            ↓
        text extraction
            ↓
        text cleaning
            ↓
        chunking
            ↓
        embeddings
            ↓
        Supabase PostgreSQL + pgvector
            ↓
        document status = ready

    The temporary local file is deleted at the end.

    Nothing permanent is stored on Render's filesystem.
    """

    logger.info("=" * 60)

    logger.info(
        "DOCUMENT PROCESSING STARTED | "
        "document_id=%s | user_id=%s",
        document_id,
        user_id,
    )

    logger.info("=" * 60)

    db = SessionLocal()

    temporary_path = None

    try:

        # ====================================================
        # STEP 1 — FIND DOCUMENT
        # ====================================================

        doc = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.is_deleted == False,  # noqa: E712
            )
            .first()
        )

        if not doc:

            logger.error(
                "Document %s not found",
                document_id,
            )

            return

        logger.info(
            "STEP 1/6: Document found: %s",
            doc.filename,
        )

        # ====================================================
        # STEP 2 — DOWNLOAD FROM SUPABASE STORAGE
        # ====================================================

        logger.info(
            "STEP 2/6: Downloading document from "
            "Supabase Storage..."
        )

        suffix = Path(
            doc.filename
        ).suffix.lower()

        temporary_path = download_document_to_temp(
            storage_path=doc.file_path,
            suffix=suffix,
        )

        logger.info(
            "Supabase download complete: %s",
            temporary_path,
        )

        # ====================================================
        # STEP 3 — EXTRACT + CLEAN TEXT
        # ====================================================

        logger.info(
            "STEP 3/6: Extracting text..."
        )

        raw = extract_text_from_file(
            temporary_path
        )

        if raw is None:
            raw = ""

        logger.info(
            "Extraction complete: %d characters",
            len(raw),
        )

        cleaned = clean_text(
            raw
        )

        logger.info(
            "Cleaning complete: %d characters",
            len(cleaned),
        )

        if not cleaned:

            logger.error(
                "No readable text extracted from document %s",
                document_id,
            )

            doc.status = "failed"

            db.commit()

            return

        # ====================================================
        # STEP 4 — CHUNK DOCUMENT
        # ====================================================

        logger.info(
            "STEP 4/6: Creating chunks..."
        )

        new_chunks = chunk_text(
            cleaned,
            chunk_size=settings.CHUNK_SIZE_TOKENS,
            overlap=settings.CHUNK_OVERLAP_TOKENS,
        )

        logger.info(
            "Chunking complete: %d chunks created",
            len(new_chunks),
        )

        if not new_chunks:

            logger.error(
                "No chunks created for document %s",
                document_id,
            )

            doc.status = "failed"

            db.commit()

            return

        # ====================================================
        # STEP 5 — GENERATE EMBEDDINGS
        # ====================================================

        logger.info(
            "STEP 5/6: Generating embeddings..."
        )

        embeddings = embedding_service.embed_texts(
            new_chunks
        )

        embeddings = np.asarray(
            embeddings,
            dtype="float32",
        )

        logger.info(
            "Embeddings generated successfully."
        )

        logger.info(
            "Embedding shape: %s",
            embeddings.shape,
        )

        # ====================================================
        # SAVE TO SUPABASE POSTGRESQL + PGVECTOR
        # ====================================================

        logger.info(
            "Saving chunks and embeddings to "
            "Supabase PostgreSQL..."
        )

        save_document_chunks(
            document_id=document_id,
            user_id=user_id,
            chunks=new_chunks,
            embeddings=embeddings,
        )

        logger.info(
            "Permanent chunks and embeddings saved successfully."
        )

        # ====================================================
        # STEP 6 — MARK DOCUMENT READY
        # ====================================================

        doc.status = "ready"

        db.commit()

        logger.info("=" * 60)

        logger.info(
            "DOCUMENT PROCESSING COMPLETE | "
            "document_id=%s | user_id=%s",
            document_id,
            user_id,
        )

        logger.info(
            "STATUS: READY"
        )

        logger.info(
            "Storage: Supabase Storage"
        )

        logger.info(
            "Vector store: Supabase PostgreSQL + pgvector"
        )

        logger.info(
            "Permanent Render filesystem usage: NONE"
        )

        logger.info("=" * 60)

    except Exception:

        logger.exception(
            "DOCUMENT PROCESSING FAILED | "
            "document_id=%s | user_id=%s",
            document_id,
            user_id,
        )

        try:

            doc = (
                db.query(Document)
                .filter(
                    Document.id == document_id,
                    Document.user_id == user_id,
                )
                .first()
            )

            if doc:

                doc.status = "failed"

                db.commit()

        except Exception:

            logger.exception(
                "Failed to update document status "
                "to failed | document_id=%s",
                document_id,
            )

    finally:

        # ====================================================
        # DELETE TEMPORARY LOCAL FILE
        # ====================================================

        if temporary_path is not None:

            try:

                temporary_path.unlink(
                    missing_ok=True
                )

                logger.info(
                    "Temporary processing file deleted: %s",
                    temporary_path,
                )

            except Exception:

                logger.warning(
                    "Could not delete temporary processing file: %s",
                    temporary_path,
                )

        db.close()


# ============================================================
# UPLOAD
# ============================================================

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    if not files:

        raise HTTPException(
            status_code=400,
            detail="No files were provided",
        )

    created: List[Document] = []

    for uploaded_file in files:

        # ====================================================
        # VALIDATE FILE
        # ====================================================

        validate_upload(
            uploaded_file
        )

        # ====================================================
        # UPLOAD TO SUPABASE STORAGE
        # ====================================================

        (
            storage_path,
            safe_name,
            size_bytes,
        ) = await upload_document(
            upload=uploaded_file,
            user_id=current_user.id,
        )

        logger.info(
            "Document uploaded to Supabase Storage | "
            "user_id=%s | path=%s",
            current_user.id,
            storage_path,
        )

        # ====================================================
        # CREATE DATABASE RECORD
        # ====================================================

        doc = Document(
            user_id=current_user.id,
            filename=safe_name,
            title=safe_name,

            # Supabase Storage object path.
            #
            # Example:
            #
            # 11/8f3a..._resume.pdf
            #
            file_path=storage_path,

            file_size_bytes=size_bytes,

            status="processing",
        )

        db.add(doc)

        db.commit()

        db.refresh(doc)

        created.append(doc)

    # ========================================================
    # START BACKGROUND PROCESSING
    # ========================================================

    for doc in created:

        background_tasks.add_task(
            _process_document,
            current_user.id,
            doc.id,
        )

    logger.info(
        "%d document(s) uploaded successfully | user_id=%s",
        len(created),
        current_user.id,
    )

    return UploadResponse(
        message=(
            f"{len(created)} file(s) uploaded. "
            "Processing started."
        ),
        documents=created,
    )


# ============================================================
# LIST DOCUMENTS
# ============================================================

@router.get(
    "/",
    response_model=List[DocumentResponse],
)
def list_documents(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    return (
        db.query(Document)
        .filter(
            Document.user_id
            == current_user.id,

            Document.is_deleted
            == False,  # noqa: E712
        )
        .order_by(
            Document.uploaded_at.desc()
        )
        .all()
    )


# ============================================================
# RENAME DOCUMENT
# ============================================================

@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
)
def rename_document(
    document_id: int,
    data: DocumentRenameRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,

            Document.user_id
            == current_user.id,

            Document.is_deleted
            == False,  # noqa: E712
        )
        .first()
    )

    if not doc:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    title = data.title.strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="Document title cannot be empty",
        )

    doc.title = title

    db.commit()

    db.refresh(doc)

    return doc


# ============================================================
# DELETE DOCUMENT
# ============================================================

@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
)
def delete_document(
    document_id: int,

    background_tasks: BackgroundTasks,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(get_db),
):

    # ========================================================
    # FIND USER'S DOCUMENT ONLY
    # ========================================================

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,

            Document.user_id
            == current_user.id,
        )
        .first()
    )

    if not doc:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # ========================================================
    # DELETE FILE FROM SUPABASE STORAGE
    # ========================================================

    try:

        delete_storage_document(
            doc.file_path
        )

        logger.info(
            "Document deleted from Supabase Storage | "
            "document_id=%s | path=%s",
            document_id,
            doc.file_path,
        )

    except Exception:

        logger.exception(
            "Failed to delete document from Supabase Storage | "
            "document_id=%s",
            document_id,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to delete document from storage. "
                "The document was not deleted."
            ),
        )

    # ========================================================
    # DELETE VECTOR CHUNKS
    # ========================================================

    try:

        delete_document_chunks(
            document_id=document_id,
            user_id=current_user.id,
        )

        logger.info(
            "Document chunks deleted from vector store | "
            "document_id=%s",
            document_id,
        )

    except Exception:

        logger.exception(
            "Failed to delete document chunks | "
            "document_id=%s",
            document_id,
        )

        # We do NOT abort here because the physical file
        # has already been deleted from Supabase Storage.
        #
        # The document will still be soft-deleted below.
        #
        # This can be cleaned later if necessary.

    # ========================================================
    # SOFT DELETE DATABASE RECORD
    # ========================================================

    doc.is_deleted = True

    db.commit()

    logger.info(
        "Document soft-deleted | "
        "document_id=%s | user_id=%s",
        document_id,
        current_user.id,
    )

    return {
        "message": "Document deleted"
    }