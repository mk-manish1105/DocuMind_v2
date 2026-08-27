"""
Document upload, listing, renaming, and deletion.

Upload is synchronous for file save + DB row creation (fast), but text
extraction / chunking / embedding runs in a background task so the
request returns immediately. Document status ("processing" → "ready" /
"failed") lets the frontend show real progress instead of guessing.
"""
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Document, User
from app.db.session import SessionLocal, get_db
from app.schemas.document import DocumentRenameRequest, DocumentResponse, UploadResponse
from app.services.extraction import chunk_text, clean_text, extract_text_from_file
from app.services.retriever import build_faiss_index, load_chunks, remove_document_chunks, save_chunks
from app.utils.storage import build_stored_path, delete_file_safe, get_user_dirs, save_upload_file, validate_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


def _process_document(user_id: int, document_id: int) -> None:
    """Background task: extract, chunk, embed, and index a single document."""
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        dirs = get_user_dirs(user_id)
        index_dir = dirs["index"]

        raw = extract_text_from_file(doc.file_path)
        cleaned = clean_text(raw)
        new_chunks = chunk_text(cleaned)

        if not new_chunks:
            doc.status = "failed"
            db.commit()
            return

        chunk_path = index_dir / "chunk_texts.pkl"
        existing = load_chunks(chunk_path)
        merged = existing + [{"document_id": doc.id, "text": c} for c in new_chunks]
        save_chunks(chunk_path, merged)
        build_faiss_index(merged, index_dir / "faiss.index")

        doc.status = "ready"
        db.commit()
    except Exception:
        logger.exception("Failed to process document %s", document_id)
        db2 = SessionLocal()
        try:
            doc = db2.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                db2.commit()
        finally:
            db2.close()
    finally:
        db.close()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided")

    dirs = get_user_dirs(current_user.id)
    uploads_dir = dirs["uploads"]

    created: List[Document] = []
    for f in files:
        validate_upload(f)
        destination, safe_name = build_stored_path(uploads_dir, f.filename)
        size_bytes = save_upload_file(f, destination)

        doc = Document(
            user_id=current_user.id,
            filename=safe_name,
            title=safe_name,
            file_path=str(destination),
            file_size_bytes=size_bytes,
            status="processing",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        created.append(doc)

    for doc in created:
        background_tasks.add_task(_process_document, current_user.id, doc.id)

    return UploadResponse(
        message=f"{len(created)} file(s) uploaded. Processing started.",
        documents=created,
    )


@router.get("/", response_model=List[DocumentResponse])
def list_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Document)
        .filter(Document.user_id == current_user.id, Document.is_deleted == False)  # noqa: E712
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
def rename_document(
    document_id: int,
    data: DocumentRenameRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == current_user.id, Document.is_deleted == False)  # noqa: E712
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.title = data.title.strip()
    db.commit()
    db.refresh(doc)
    return doc


def _rebuild_index_after_delete(user_id: int, document_id: int) -> None:
    dirs = get_user_dirs(user_id)
    index_dir = dirs["index"]
    chunk_path = index_dir / "chunk_texts.pkl"
    remaining = remove_document_chunks(chunk_path, document_id)
    build_faiss_index(remaining, index_dir / "faiss.index")


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    delete_file_safe(Path(doc.file_path))
    doc.is_deleted = True
    db.commit()

    # Rebuilding from the tagged chunk store (not re-reading files from disk)
    # is cheap, so this can safely run in the background.
    background_tasks.add_task(_rebuild_index_after_delete, current_user.id, document_id)

    return {"message": "Document deleted"}