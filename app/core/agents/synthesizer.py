import re
from typing import List, AsyncGenerator
from google import genai
from google.genai import types
from app.config import settings
from app.db.models import RetrievedChunk


class SynthesizerAgent:
    """
    Generates grounded responses with inline citations and supports token streaming.
    """

    def __init__(self, client: genai.Client):
        self.client = client

    def _redact_sensitive_text(self, text: str) -> str:
        if not text:
            return text

        redacted = text
        patterns = [
            (r'(?i)\b(password|passwd|pwd|secret|api[_-]?key|token)\b\s*[:=]\s*\S+', r'\1=[REDACTED]'),
            (r'(?i)\b(bearer)\s+[A-Za-z0-9\-._~+/]+=*', r'\1 [REDACTED]'),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[REDACTED_EMAIL]'),
            (r'(?<!\d)(?:\+?\d[\d\-\s()]{7,}\d)', '[REDACTED_PHONE]'),
            (r'\b[A-Za-z0-9_\-]{24,}\b', '[REDACTED_TOKEN]'),
        ]
        for pattern, repl in patterns:
            redacted = re.sub(pattern, repl, redacted)
        return redacted

    def _sanitize_chunks(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        for c in chunks:
            c.content = self._redact_sensitive_text(c.content)
            c.source = self._redact_sensitive_text(c.source)
        return chunks

    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        return "\n\n".join([f"[Source: {c.source} | Page: {c.page or 1}]:\n{c.content}" for c in chunks])

    async def stream_generate(
        self,
        query: str,
        context_chunks: List[RetrievedChunk],
        critic_feedback: str = "",
        chat_history: str = "",
        direct_answer: bool = False,
    ) -> AsyncGenerator[str, None]:
        safe_query = self._redact_sensitive_text(query)
        safe_chat_history = self._redact_sensitive_text(chat_history)
        safe_chunks = self._sanitize_chunks(context_chunks)
        history_block = f"\nConversation History:\n{safe_chat_history}\n" if safe_chat_history else ""

        if direct_answer and not safe_chunks:
            prompt = f"""You are a helpful, professional enterprise RAG assistant.{history_block}
Respond politely and concisely to the user's message:
{safe_query}
"""
        else:
            context_block = self.format_context(safe_chunks)
            feedback_instruction = (
                f"\nIMPORTANT - Previous attempt failed verification: {critic_feedback}\nEnsure strictly supported facts."
                if critic_feedback
                else ""
            )
            prompt = f"""You are a professional enterprise RAG assistant.
Answer the user's inquiry accurately and factually using ONLY the provided context sources below.

Rules:
1. Always ground your facts in the Context. If the information is not present, clearly state: "I do not have enough verified information in the provided knowledge base."
2. Provide citations where relevant in the text using bracketed format [Source: filename | Page X].
3. Maintain an objective, concise, and structured tone.{feedback_instruction}{history_block}
Context Sources:
{context_block}

User Query:
{safe_query}
"""

        for model in (settings.PRIMARY_MODEL, settings.FALLBACK_MODEL):
            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception:
                if model == settings.FALLBACK_MODEL:
                    raise
