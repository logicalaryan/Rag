from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================
# API Request & Response Schemas
# ============================================================

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question or prompt")
    session_id: Optional[str] = Field(default="default_session", description="Session identifier")
    chat_history: Optional[str] = Field(default="", description="Multi-turn session memory buffer")
    tenant_id: Optional[str] = Field(default="default", description="Tenant/workspace isolation identifier")
    allow_web_search: bool = Field(default=True, description="Whether external web search is permitted")
    allow_sensitive_web: bool = Field(default=False, description="Explicit opt-in to send internal query terms to web search")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "v6.0-production"
    database: str
    redis: str


class DocumentMetadata(BaseModel):
    id: str
    filename: str
    size: str
    status: str
    created_at: str
    chunk_count: Optional[int] = 0


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str


# ============================================================
# Agent & Tool Internal Schemas
# ============================================================

class RetrievedChunk(BaseModel):
    id: str
    content: str
    score: float
    source: str
    page: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RoutingDecision(BaseModel):
    intent: str  # "search_local", "search_web", "both", "direct_answer"
    rewritten_query: str
    reasoning: str


class CriticEvaluation(BaseModel):
    passed: bool
    faithfulness_score: float
    relevance_score: float
    feedback: Optional[str] = None
    detected_hallucinations: List[str] = Field(default_factory=list)
