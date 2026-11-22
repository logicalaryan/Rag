import json
import logging
import os
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg
from app.config import settings


def _normalize_dsn_for_asyncpg(raw_url: str) -> Tuple[str, bool]:
    """
    Converts any Postgres/SQLAlchemy URL into a clean DSN for native asyncpg:
    - Converts 'postgresql+asyncpg://' -> 'postgresql://'
    - Strips 'sslmode', 'ssl', and 'channel_binding' from query params (which asyncpg rejects in DSN)
    - Returns (clean_dsn, use_ssl)
    """
    url = (raw_url or "").strip().strip("'").strip('"')
    if not url:
        return "", False

    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]

    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    cleaned_pairs = []
    use_ssl = "neon.tech" in parts.netloc

    for k, v in query_pairs:
        if k in ("channel_binding", "sslmode", "ssl"):
            if k in ("sslmode", "ssl") and v.lower() not in ("disable", "false", "0"):
                use_ssl = True
            continue
        cleaned_pairs.append((k, v))

    clean_dsn = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(cleaned_pairs), parts.fragment))
    return clean_dsn, use_ssl


class PostgresConversationStore:
    """
    Lightweight, zero-ORM asyncpg conversation store for Neon / PostgreSQL.
    Does not require greenlet or sqlalchemy.ext.asyncio.
    """

    def __init__(self):
        raw_url = settings.DATABASE_URL or os.getenv("DATABASE_URL", "")
        self.dsn, self.use_ssl = _normalize_dsn_for_asyncpg(raw_url)
        self.pool: Optional[asyncpg.Pool] = None

    async def _ensure_pool(self) -> Optional[asyncpg.Pool]:
        if self.pool is not None:
            return self.pool
        if not self.dsn:
            return None
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.dsn,
                ssl="require" if self.use_ssl else None,
                min_size=1,
                max_size=5,
                command_timeout=15.0,
            )
            return self.pool
        except Exception as exc:
            logging.warning("Failed to connect asyncpg pool to PostgreSQL: %s", exc)
            return None

    async def init_db(self) -> bool:
        """Creates the chat_messages table automatically on startup if it doesn't exist."""
        pool = await self._ensure_pool()
        if not pool:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(128) NOT NULL,
                        tenant_id VARCHAR(128) NOT NULL DEFAULT 'default',
                        role VARCHAR(32) NOT NULL,
                        content TEXT NOT NULL,
                        citations_json TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_chat_messages_session_tenant
                        ON chat_messages (session_id, tenant_id);
                    """
                )
            logging.info("PostgreSQL conversation table (chat_messages) initialized via asyncpg.")
            return True
        except Exception as exc:
            logging.warning("PostgreSQL init_db failed (falling back to in-memory sessions): %s", exc)
            return False

    async def get_recent_history(
        self, session_id: str, tenant_id: str = "default", limit: int = 6
    ) -> List[str]:
        """Fetches recent conversation turns for a session formatted as 'User: ...' / 'Assistant: ...'."""
        pool = await self._ensure_pool()
        if not pool:
            return []
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM chat_messages
                    WHERE session_id = $1 AND tenant_id = $2
                    ORDER BY id DESC
                    LIMIT $3
                    """,
                    session_id,
                    tenant_id,
                    limit,
                )
            return [
                f"{'User' if r['role'] == 'user' else 'Assistant'}: {r['content']}"
                for r in reversed(rows)
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
        pool = await self._ensure_pool()
        if not pool:
            return
        try:
            citations_str = json.dumps(citations) if citations else None
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (session_id, tenant_id, role, content, citations_json)
                        VALUES ($1, $2, 'user', $3, NULL),
                               ($1, $2, 'assistant', $4, $5)
                        """,
                        session_id,
                        tenant_id,
                        user_query,
                        assistant_answer,
                        citations_str,
                    )
        except Exception as exc:
            logging.warning("Failed to save chat turn to PostgreSQL: %s", exc)


conversation_store = PostgresConversationStore()
