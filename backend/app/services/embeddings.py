"""
Embedding service. Lazily loads the sentence-transformers model on first
use (not at import time) so the API can start instantly and report a clean
error if the model fails to load, instead of crashing the whole process.

Also correctly applies the "query: " / "passage: " prefix convention
required by the e5 model family (a no-op for MiniLM/BGE, so switching
EMBEDDING_MODEL later stays safe).
"""
import logging
import threading
from typing import List

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._needs_prefix = "e5" in model_name.lower()

    def _ensure_loaded(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info("Loading embedding model '%s'...", self.model_name)
                    self._model = SentenceTransformer(self.model_name)
                    logger.info("Embedding model loaded.")
        return self._model

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        model = self._ensure_loaded()
        prefixed = [f"passage: {t}" for t in texts] if self._needs_prefix else texts
        embeddings = model.encode(prefixed, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.astype("float32")

    def embed_query(self, query: str) -> np.ndarray:
        model = self._ensure_loaded()
        text = f"query: {query}" if self._needs_prefix else query
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.reshape(1, -1).astype("float32")


embedding_service = EmbeddingService(settings.EMBEDDING_MODEL)