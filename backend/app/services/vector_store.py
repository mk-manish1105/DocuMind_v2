"""
Persistent vector store using Supabase PostgreSQL + pgvector.

Permanent document chunks and embeddings are stored in PostgreSQL,
so they survive Render restarts and deployments.

This module is ONLY for permanent document storage and retrieval.

Temporary chat attachments should continue using the in-memory
FAISS logic in chat.py.
"""

import logging
from typing import List

import numpy as np
from sqlalchemy import text

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


# ============================================================
# SAVE DOCUMENT CHUNKS + EMBEDDINGS
# ============================================================

def save_document_chunks(
    document_id: int,
    user_id: int,
    chunks: List[str],
    embeddings: np.ndarray,
) -> None:
    """
    Replace all existing chunks for a document and save the
    new chunks + embeddings.

    Permanent storage:
        PostgreSQL + pgvector
    """

    if len(chunks) != len(embeddings):
        raise ValueError(
            "Number of chunks and embeddings must match."
        )

    if not chunks:
        raise ValueError(
            "Cannot save an empty chunk list."
        )

    embeddings = np.asarray(
        embeddings,
        dtype="float32",
    )

    if embeddings.ndim != 2:
        raise ValueError(
            "Embeddings must be a 2-dimensional array."
        )

    if embeddings.shape[0] != len(chunks):
        raise ValueError(
            "Embedding count does not match chunk count."
        )

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # Remove old chunks for this document.
        # ----------------------------------------------------

        db.execute(
            text(
                """
                DELETE FROM public.document_chunks
                WHERE document_id = :document_id
                  AND user_id = :user_id
                """
            ),
            {
                "document_id": document_id,
                "user_id": user_id,
            },
        )

        # ----------------------------------------------------
        # Insert new chunks.
        # ----------------------------------------------------

        insert_query = text(
            """
            INSERT INTO public.document_chunks
            (
                document_id,
                user_id,
                chunk_index,
                text,
                embedding
            )
            VALUES
            (
                :document_id,
                :user_id,
                :chunk_index,
                :text,
                CAST(
                    :embedding
                    AS extensions.vector
                )
            )
            """
        )

        for index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings)
        ):

            if not chunk or not chunk.strip():
                continue

            vector = embedding.tolist()

            db.execute(
                insert_query,
                {
                    "document_id": document_id,
                    "user_id": user_id,
                    "chunk_index": index,
                    "text": chunk.strip(),
                    "embedding": str(vector),
                },
            )

        db.commit()

        logger.info(
            "VECTOR STORE: saved %d chunks for document_id=%s user_id=%s",
            len(chunks),
            document_id,
            user_id,
        )

    except Exception:

        db.rollback()

        logger.exception(
            "VECTOR STORE: failed to save chunks "
            "for document_id=%s",
            document_id,
        )

        raise

    finally:
        db.close()


# ============================================================
# DELETE DOCUMENT CHUNKS
# ============================================================

def delete_document_chunks(
    document_id: int,
    user_id: int,
) -> None:
    """
    Delete all vector chunks belonging to a document.
    """

    db = SessionLocal()

    try:

        db.execute(
            text(
                """
                DELETE FROM public.document_chunks
                WHERE document_id = :document_id
                  AND user_id = :user_id
                """
            ),
            {
                "document_id": document_id,
                "user_id": user_id,
            },
        )

        db.commit()

        logger.info(
            "VECTOR STORE: deleted chunks for document_id=%s",
            document_id,
        )

    except Exception:

        db.rollback()

        logger.exception(
            "VECTOR STORE: failed to delete chunks "
            "for document_id=%s",
            document_id,
        )

        raise

    finally:
        db.close()


# ============================================================
# SEARCH
# ============================================================

def search_document_chunks(
    user_id: int,
    query_embedding: np.ndarray,
    top_k: int,
    min_similarity: float,
) -> List[dict]:
    """
    Search permanent document chunks using pgvector.

    Security:
        Only chunks belonging to the specified user_id
        can be returned.

    Returns:
        [
            {
                "id": ...,
                "document_id": ...,
                "chunk_index": ...,
                "text": ...,
                "similarity": ...
            }
        ]
    """

    if top_k <= 0:
        return []

    query_embedding = np.asarray(
        query_embedding,
        dtype="float32",
    ).reshape(-1)

    if query_embedding.size == 0:
        return []

    db = SessionLocal()

    try:

        embedding = query_embedding.tolist()

        result = db.execute(
            text(
                """
                SELECT
                    id,
                    document_id,
                    chunk_index,
                    text,
                    similarity
                FROM public.match_document_chunks(
                    CAST(
                        :query_embedding
                        AS extensions.vector
                    ),
                    :user_id,
                    :match_count,
                    :min_similarity
                )
                """
            ),
            {
                "query_embedding": str(
                    embedding
                ),
                "user_id": user_id,
                "match_count": int(top_k),
                "min_similarity": float(
                    min_similarity
                ),
            },
        )

        rows = result.mappings().all()

        results = [
            dict(row)
            for row in rows
        ]

        logger.info(
            "VECTOR SEARCH: user_id=%s | "
            "top_k=%s | min_similarity=%.4f | "
            "results=%s",
            user_id,
            top_k,
            min_similarity,
            len(results),
        )

        return results

    except Exception:

        logger.exception(
            "VECTOR SEARCH FAILED | user_id=%s",
            user_id,
        )

        return []

    finally:
        db.close()