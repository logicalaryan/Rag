import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Production Agentic RAG"
    API_V1_STR: str = "/api/v1"
    
    # AI & Model configs
    GEMINI_API_KEY: str = ""
    PRIMARY_MODEL: str = "gemini-2.5-flash"
    FALLBACK_MODEL: str = "gemini-2.5-flash-lite"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    
    # RAG Retrieval parameters
    TOP_K_CANDIDATES: int = 15
    FINAL_TOP_K: int = 4
    SIMILARITY_THRESHOLD: float = 0.35
    MAX_CRITIC_RETRIES: int = 2
    
    # Storage & Persistence
    DATABASE_URL: str = "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CHROMA_PERSIST_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chroma")
    DOCUMENTS_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "documents")
    
    # Semantic Cache
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_TTL_SECONDS: int = 86400  # 24 hours
    
    # Security & CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.pages.dev"
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure local directories exist
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
