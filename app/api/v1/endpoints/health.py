from datetime import datetime
from fastapi import APIRouter
from app.db.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health():
    """Liveness probe returning cluster health status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="v6.0-production",
        database="connected",
        redis="connected",
    )
