"""Pydantic Settings — single source of truth for all environment configuration."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Groq (replaces OpenAI) ---
    GROQ_API_KEY: str
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_CHAT_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FAST_MODEL: str = "llama-3.1-8b-instant"

    # --- SEC EDGAR ---
    SEC_EDGAR_USER_AGENT: str = "FinDoc Intelligence research@findoc.local"

    # --- Embeddings (local — no API key needed) ---
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIM: int = 768

    # --- Qdrant (replaces Pinecone) ---
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "findoc_sections"

    # --- Storage (Cloudflare R2 — replaces Backblaze B2) ---
    USE_LOCAL_STORAGE: bool = True
    LOCAL_UPLOAD_DIR: str = "/app/uploads"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "findoc-uploads"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Langfuse (replaces Logfire) ---
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = True

    # --- Database ---
    DATABASE_URL: str

    # --- Auth ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TTL_MIN: int = 30
    JWT_REFRESH_TTL_DAYS: int = 14

    # --- App ---
    SENTRY_DSN: str = ""
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ENV: Literal["dev", "staging", "prod"] = "dev"

    # --- Eval / ingest rate limiting ---
    EVAL_DELAY_SECS: float = 0.5
    INGEST_NODE_SUMMARY_DELAY_SECS: float = 0.1


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
