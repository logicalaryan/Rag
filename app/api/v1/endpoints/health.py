from datetime import datetime, timezone
from fastapi import APIRouter
from app.db.models import HealthResponse
from app.db.vector_store import vector_store

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Liveness probe returning actual vector store status."""
    try:
        chunks = vector_store.count()
        db_status = f"connected ({chunks} chunks)"
        status = "healthy"
    except Exception:
        db_status = "disconnected"
        status = "degraded"

    return HealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="v6.0-production",
        database=db_status,
        redis="in-memory",
    )
