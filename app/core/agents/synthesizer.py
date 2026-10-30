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
    ) -> AsyncGenerator[str, None]:
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
3. Maintain an objective, concise, and structured tone.{feedback_instruction}

Context Sources:
{context_block}

User Query:
{query}
"""

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=settings.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except Exception:
            # Fallback to secondary model if primary encounters rate limit
            try:
                stream = await self.client.aio.models.generate_content_stream(
                    model=settings.FALLBACK_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
            except Exception as fallback_err:
                yield f"Error generating answer: {str(fallback_err)}"
