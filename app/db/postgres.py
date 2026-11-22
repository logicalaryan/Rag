import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

Base = declarative_base()


class ChatMessageRecord(Base):
    """Stores every user and assistant conversation turn in PostgreSQL."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), index=True, nullable=False)
    tenant_id = Column(String(128), index=True, nullable=False, default="default")
    role = Column(String(32), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    citations_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def _normalize_asyncpg_url(raw_url: str) -> str:
    """
    Normalizes any Neon/Render Postgres URL for SQLAlchemy + asyncpg:
    - Ensures scheme is 'postgresql+asyncpg'
    - Converts 'sslmode=require' -> 'ssl=require'
    - Strips unsupported 'channel_binding' query parameter so asyncpg doesn't error
    """
    url = (raw_url or "").strip().strip("'").strip('"')
    if not url:
        return ""
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned_pairs = []
    has_ssl = False
    for k, v in query_pairs:
        if k == "channel_binding":
            continue
        if k == "sslmode":
            cleaned_pairs.append(("ssl", v))
            has_ssl = True
        else:
            if k == "ssl":
                has_ssl = True
            cleaned_pairs.append((k, v))

    if "neon.tech" in parts.netloc and not has_ssl:
        cleaned_pairs.append(("ssl", "require"))

    new_query = urlencode(cleaned_pairs)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


class PostgresConversationStore:
    def __init__(self):
        raw_url = settings.DATABASE_URL or os.getenv("DATABASE_URL", "")
        self.db_url = _normalize_asyncpg_url(raw_url)
        self.engine = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        if self.db_url:
            try:
                self.engine = create_async_engine(
                    self.db_url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=5,
                )
                self.session_factory = async_sessionmaker(
                    self.engine, expire_on_commit=False, class_=AsyncSession
                )
            except Exception as exc:
                logging.warning("Failed to initialize PostgreSQL engine: %s", exc)

    async def init_db(self) -> bool:
        """Creates the chat_messages table automatically on startup if it doesn't exist."""
        if not self.engine:
            return False
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logging.info("PostgreSQL conversation table (chat_messages) initialized successfully.")
            return True
        except Exception as exc:
            logging.warning("PostgreSQL init_db failed (falling back to in-memory sessions): %s", exc)
            return False

    async def get_recent_history(
        self, session_id: str, tenant_id: str = "default", limit: int = 6
    ) -> List[str]:
        """Fetches the most recent messages for a session formatted as 'User: ...' / 'Assistant: ...'."""
        if not self.session_factory:
            return []
        try:
            async with self.session_factory() as session:
                stmt = (
                    select(ChatMessageRecord)
                    .where(
                        ChatMessageRecord.session_id == session_id,
                        ChatMessageRecord.tenant_id == tenant_id,
                    )
                    .order_by(ChatMessageRecord.id.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                rows = list(reversed(result.scalars().all()))
                return [
                    f"{'User' if r.role == 'user' else 'Assistant'}: {r.content}"
                    for r in rows
                ]
        except Exception as exc:
            logging.warning("Failed to read chat history from PostgreSQL: %s", exc)
            return []

    async def save_turn(
        self,
        session_id: str,
        tenant_id: str,
        user_query: str,
        assistant_answer: str,
        citations: Optional[List[str]] = None,
    ) -> None:
        """Persists a user message and the assistant response in a single transaction."""
        if not self.session_factory:
            return
        try:
            citations_str = json.dumps(citations) if citations else None
            async with self.session_factory() as session:
                session.add_all([
                    ChatMessageRecord(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        role="user",
                        content=user_query,
                        citations_json=None,
                    ),
                    ChatMessageRecord(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        role="assistant",
                        content=assistant_answer,
                        citations_json=citations_str,
                    ),
                ])
                await session.commit()
        except Exception as exc:
            logging.warning("Failed to save chat turn to PostgreSQL: %s", exc)


conversation_store = PostgresConversationStore()
