from fastapi import APIRouter
from starlette.responses import StreamingResponse
from app.db.models import ChatRequest
from app.core.agents.orchestrator import orchestrator

router = APIRouter()


@router.post("")
async def chat_stream(request: ChatRequest):
    """SSE Streaming Chat Endpoint with proxy buffering disabled for real-time word-by-word streaming."""
    return StreamingResponse(
        orchestrator.execute_stream(
            query=request.query,
            session_id=request.session_id or "default_session",
            chat_history=request.chat_history or "",
            tenant_id=request.tenant_id or "default",
            allow_web_search=request.allow_web_search,
            allow_sensitive_web=request.allow_sensitive_web,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
