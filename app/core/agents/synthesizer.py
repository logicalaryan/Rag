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
        history_block = f"\nConversation History:\n{chat_history}\n" if chat_history else ""

        if direct_answer and not context_chunks:
            prompt = f"""You are a helpful, professional enterprise RAG assistant.{history_block}
Respond politely and concisely to the user's message:
{query}
"""
        else:
            context_block = self.format_context(context_chunks)
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
{query}
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
