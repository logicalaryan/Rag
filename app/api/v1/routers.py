import hmac
from fastapi import APIRouter, Depends, Header, HTTPException
from app.config import settings
from app.api.v1.endpoints import chat, documents, health


def verify_api_key(x_api_key: str = Header(default="")) -> None:
    if settings.API_ACCESS_TOKEN and not hmac.compare_digest(x_api_key, settings.API_ACCESS_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header.")


api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"], dependencies=[Depends(verify_api_key)])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"], dependencies=[Depends(verify_api_key)])
