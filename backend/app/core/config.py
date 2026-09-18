"""
Centralized application configuration.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============================================================
    # APP
    # ============================================================

    APP_NAME: str = "DocuMind API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # ============================================================
    # DATABASE
    # ============================================================

    DATABASE_URL: str

    # ============================================================
    # AUTH / JWT
    # ============================================================

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    # ============================================================
    # CORS
    # ============================================================

    CORS_ORIGINS: str = "http://localhost:5173"

    # ============================================================
    # LLM
    # ============================================================

    LLM_API_KEY: str
    LLM_API_URL: str = (
        "https://api.groq.com/openai/v1/chat/completions"
    )
    LLM_MODEL: str = "openai/gpt-oss-20b"

    LLM_MAX_TOKENS_CAP: int = 3000
    LLM_REQUEST_TIMEOUT_CONNECT: int = 10
    LLM_REQUEST_TIMEOUT_READ: int = 300

    # ============================================================
    # EMBEDDINGS / RETRIEVAL
    # ============================================================

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    HF_TOKEN: str

    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_TOP_SCORE_THRESHOLD: float = 0.62
    RETRIEVAL_CHUNK_SCORE_THRESHOLD: float = 0.55

    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 80

    # ============================================================
    # FILE UPLOAD
    # ============================================================

    MAX_UPLOAD_MB: int = 20

    ALLOWED_UPLOAD_EXTENSIONS: str = (
        ".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp"
    )

    # ============================================================
    # OCR (SCANNED / IMAGE-ONLY PDFS)
    # ============================================================

    OCR_SPACE_API_KEY: str = ""
    OCR_SPACE_API_URL: str = (
        "https://api.ocr.space/parse/image"
    )
    OCR_MAX_PAGES_PER_DOCUMENT: int = 15

    # ============================================================
    # SUPABASE
    # ============================================================

    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "documents"

    # ============================================================
    # CHAT
    # ============================================================

    CHAT_CONTEXT_CHAR_BUDGET: int = 4000
    CHAT_HISTORY_DEFAULT_LIMIT: int = 200

    # ============================================================
    # VALIDATION
    # ============================================================

    @field_validator(
        "DATABASE_URL",
        "JWT_SECRET",
        "LLM_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "HF_TOKEN",
    )
    
    @classmethod
    def not_empty(cls, v: str) -> str:

        if not v or not v.strip():
            raise ValueError(
                "Required setting is empty — "
                "check your .env file"
            )

        return v

    # ============================================================
    # HELPERS
    # ============================================================

    @property
    def cors_origins_list(self) -> List[str]:
        return [
            o.strip()
            for o in self.CORS_ORIGINS.split(",")
            if o.strip()
        ]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [
            e.strip().lower()
            for e in self.ALLOWED_UPLOAD_EXTENSIONS.split(",")
            if e.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()