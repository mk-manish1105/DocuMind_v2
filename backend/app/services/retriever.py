"""
Per-user FAISS index + chunk store.

Chunks are stored as {"document_id": int, "text": str} records (not just
raw strings) so a document delete can drop that document's chunks and
rebuild the index without re-reading every remaining file from disk —
the original implementation re-extracted every document on every delete.
"""
import pickle
from pathlib import Path
from typing import List, TypedDict

import faiss

from app.services.embeddings import embedding_service


class ChunkRecord(TypedDict):
    document_id: int
    text: str


def load_chunks(path: Path) -> List[ChunkRecord]:
    if not path.exists():
        return []
    with path.open("rb") as f:
        return pickle.load(f)


def save_chunks(path: Path, chunks: List[ChunkRecord]) -> None:
    with path.open("wb") as f:
        pickle.dump(chunks, f)


def remove_document_chunks(path: Path, document_id: int) -> List[ChunkRecord]:
    chunks = load_chunks(path)
    remaining = [c for c in chunks if c["document_id"] != document_id]
    save_chunks(path, remaining)
    return remaining


def build_faiss_index(chunks: List[ChunkRecord], index_path: Path):
    if not chunks:
        index_path.unlink(missing_ok=True)
        return None

    print("=" * 60)
    print(f"FAISS INDEX BUILD START")
    print(f"Total chunks: {len(chunks)}")
    print("=" * 60)

    embeddings = embedding_service.embed_texts(
        [c["text"] for c in chunks]
    )

    print(
        f"Embeddings generated: {embeddings.shape}"
    )

    faiss.normalize_L2(embeddings)

    print("Creating FAISS IndexFlatIP...")

    index = faiss.IndexFlatIP(
        embeddings.shape[1]
    )

    index.add(embeddings)

    print(
        f"FAISS index contains {index.ntotal} vectors"
    )

    faiss.write_index(
        index,
        str(index_path)
    )

    print(
        f"FAISS index saved: {index_path}"
    )

    print("FAISS INDEX BUILD COMPLETE")

    return index


def load_faiss_index(index_path: Path):
    if not index_path.exists():
        return None
    return faiss.read_index(str(index_path))