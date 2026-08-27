"""
Centralized application configuration, loaded once from environment
variables (typically supplied via a .env file in development, or real
environment variables in production/Oracle Cloud).
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "DocuMind API"
    ENVIRONMENT: str = "development"  # "development" | "production"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str

    # --- Auth / JWT ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # --- CORS ---
    # Comma-separated list of allowed origins, e.g.
    # "http://localhost:5173,https://documind.yourdomain.com"
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- LLM provider (Groq / any OpenAI-compatible chat completions API) ---
    LLM_API_KEY: str
    LLM_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_MAX_TOKENS_CAP: int = 1600
    LLM_REQUEST_TIMEOUT_CONNECT: int = 10
    LLM_REQUEST_TIMEOUT_READ: int = 300


    # --- Embeddings / retrieval ---
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_TOP_SCORE_THRESHOLD: float = 0.62
    RETRIEVAL_CHUNK_SCORE_THRESHOLD: float = 0.55

    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 80


    # --- Storage ---
    DOCUMIND_DATA_DIR: str = "/data/documind"
    MAX_UPLOAD_MB: int = 20
    ALLOWED_UPLOAD_EXTENSIONS: str = ".pdf,.docx,.txt"

    # --- Chat ---
    CHAT_CONTEXT_CHAR_BUDGET: int = 4000
    CHAT_HISTORY_DEFAULT_LIMIT: int = 200

    @field_validator("DATABASE_URL", "JWT_SECRET", "LLM_API_KEY")


    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Required setting is empty — check your .env file")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip().lower() for e in self.ALLOWED_UPLOAD_EXTENSIONS.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    """Settings are cached — env is read once per process."""
    return Settings()


settings = get_settings()