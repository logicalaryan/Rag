from fastapi import APIRouter
from starlette.responses import StreamingResponse
from app.db.models import ChatRequest
from app.core.agents.orchestrator import orchestrator

router = APIRouter()


@router.post("")
async def chat_stream(request: ChatRequest):
    """SSE Streaming Chat Endpoint using native FastAPI StreamingResponse."""
    return StreamingResponse(
        orchestrator.execute_stream(
            query=request.query,
            session_id=request.session_id or "default_session",
            chat_history=request.chat_history or "",
        ),
        media_type="text/event-stream"
    )
