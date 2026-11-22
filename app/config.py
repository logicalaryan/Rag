import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Production Agentic RAG"
    API_V1_STR: str = "/api/v1"

    # AI & Model configs
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = ""
    PRIMARY_MODEL: str = "gemini-3.5-flash-lite"
    # Distinct fallback model (empty string prevents double-hitting the same model on 429)
    FALLBACK_MODEL: str = ""
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768

    # Rate Limiting, Concurrency, Timeout & Retry Controls
    GEMINI_MAX_CONCURRENT_REQUESTS: int = 2
    GEMINI_RPM_LIMIT: int = 12              # Stay safely below 15 RPM free-tier ceiling
    CLIENT_RATE_LIMIT_PER_MINUTE: int = 6   # Max chat requests per minute per tenant/session
    GEMINI_TIMEOUT_SECONDS: float = 20.0
    GEMINI_MAX_RETRIES: int = 2             # Bounded retries; never infinite
    CACHE_TTL_SECONDS: int = 600            # 10-minute response cache
    CACHE_MAX_ENTRIES: int = 256

    # RAG Retrieval & Context Budget parameters
    TOP_K_CANDIDATES: int = 12
    FINAL_TOP_K: int = 3
    MAX_CHUNK_CHARS: int = 600              # Cap per-chunk size sent to LLM
    MAX_HISTORY_CHARS: int = 1200           # Cap chat history tokens
    SIMILARITY_THRESHOLD: float = 0.35
    MAX_CRITIC_RETRIES: int = 0             # Avoid 2x 4-call loops on free tier

    # Storage & Persistence
    CHROMA_PERSIST_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chroma")
    DOCUMENTS_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "documents")

    # Security & CORS
    API_ACCESS_TOKEN: str = ""
    CORS_Origin_REGEX: str = r"https://([a-z0-9-]+\.)?raggg-2hw\.pages\.dev"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure local directories exist
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
