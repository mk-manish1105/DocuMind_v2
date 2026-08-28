"""
Remote embedding service using Hugging Face Inference.

The embedding model runs remotely on Hugging Face.
Render does NOT download or load PyTorch/SentenceTransformers.

Model:
    BAAI/bge-small-en-v1.5

Embedding dimension:
    384

This keeps the same embedding model and vector dimension
used by the existing Supabase pgvector database.
"""

import logging
import time
from typing import List

import numpy as np
import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self, model_name: str):

        self.model_name = model_name

        self.api_url = (
            "https://router.huggingface.co/"
            "hf-inference/models/"
            f"{model_name}/pipeline/feature-extraction"
        )

        self.timeout = 120

    # ========================================================
    # HEADERS
    # ========================================================

    def _headers(self) -> dict:

        if not settings.HF_TOKEN:
            raise RuntimeError(
                "HF_TOKEN is not configured."
            )

        return {
            "Authorization": (
                f"Bearer {settings.HF_TOKEN}"
            ),
            "Content-Type": "application/json",
        }

    # ========================================================
    # EMBED
    # ========================================================

    def _embed(
        self,
        texts: List[str],
    ) -> np.ndarray:

        if not texts:
            return np.empty(
                (0, 384),
                dtype="float32",
            )

        logger.info(
            "REMOTE EMBEDDING START | model=%s | texts=%d",
            self.model_name,
            len(texts),
        )

        start = time.time()

        response = requests.post(
            self.api_url,
            headers=self._headers(),
            json={
                "inputs": texts,
            },
            timeout=self.timeout,
        )

        # ----------------------------------------------------
        # Model may temporarily be loading on Hugging Face.
        # ----------------------------------------------------

        if response.status_code == 503:

            try:
                error_data = response.json()
            except Exception:
                error_data = {}

            wait_time = error_data.get(
                "estimated_time"
            )

            raise RuntimeError(
                "Hugging Face embedding model is "
                "currently loading. "
                f"Estimated wait: {wait_time}"
            )

        if response.status_code != 200:

            logger.error(
                "Hugging Face embedding API failed | "
                "status=%s | response=%s",
                response.status_code,
                response.text[:1000],
            )

            response.raise_for_status()

        data = response.json()

        embeddings = np.asarray(
            data,
            dtype="float32",
        )

        # ----------------------------------------------------
        # Hugging Face can return:
        #
        # [chunks][tokens][dimensions]
        #
        # for feature extraction.
        #
        # For sentence embeddings we need:
        #
        # [chunks][dimensions]
        #
        # Mean-pool token embeddings.
        # ----------------------------------------------------

        if embeddings.ndim == 3:

            attention_mask = None

            pooled = embeddings.mean(
                axis=1
            )

            embeddings = pooled

        elif embeddings.ndim == 2:

            # Already sentence-level embeddings.
            pass

        elif embeddings.ndim == 1:

            embeddings = embeddings.reshape(
                1,
                -1,
            )

        else:

            raise RuntimeError(
                "Unexpected embedding response shape: "
                f"{embeddings.shape}"
            )

        # ----------------------------------------------------
        # Normalize exactly as before.
        # ----------------------------------------------------

        norms = np.linalg.norm(
            embeddings,
            axis=1,
            keepdims=True,
        )

        norms = np.maximum(
            norms,
            1e-12,
        )

        embeddings = (
            embeddings / norms
        )

        embeddings = embeddings.astype(
            "float32"
        )

        elapsed = time.time() - start

        logger.info(
            "REMOTE EMBEDDING COMPLETE | "
            "texts=%d | shape=%s | time=%.2fs",
            len(texts),
            embeddings.shape,
            elapsed,
        )

        return embeddings

    # ========================================================
    # DOCUMENT CHUNKS
    # ========================================================

    def embed_texts(
        self,
        texts: List[str],
    ) -> np.ndarray:

        return self._embed(
            texts
        )

    # ========================================================
    # QUERY
    # ========================================================

    def embed_query(
        self,
        query: str,
    ) -> np.ndarray:

        embeddings = self._embed(
            [query]
        )

        return embeddings


# ============================================================
# SINGLETON
# ============================================================

embedding_service = EmbeddingService(
    settings.EMBEDDING_MODEL
)