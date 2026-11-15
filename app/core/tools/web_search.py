import asyncio
import logging
from typing import List, Tuple
from google import genai
from google.genai import types
from app.config import settings
from app.db.models import RetrievedChunk
from app.core.privacy import privacy_guard


class GeminiGoogleSearchTool:
    """
    Production-grade live web search tool using native Gemini Google Search Grounding.
    Replaces fragile third-party HTML/SERP scraping with direct Google Grounding API.
    """
    name = "search_web"
    description = "Searches the live public web using official Google Search Grounding."

    def __init__(self, client: genai.Client = None):
        self.client = client

    async def execute(
        self, query: str, top_k: int = 3, allow_sensitive_web: bool = False, **kwargs
    ) -> List[RetrievedChunk]:
        safe_query = privacy_guard.sanitize_for_web_search(query, allow_sensitive_web=allow_sensitive_web)
        if not safe_query:
            logging.info("web search blocked by privacy guard (confidential or PII-only query)")
            return []

        if not self.client:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                import os
                api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                return []
            self.client = genai.Client(api_key=api_key)

        chunks, _ = await self.search_and_ground(safe_query, top_k=top_k)
        return chunks

    async def search_and_ground(self, query: str, top_k: int = 3) -> Tuple[List[RetrievedChunk], str]:
        """
        Executes Google Search Grounding via Gemini.
        Returns both RetrievedChunk objects (for context fusion) and the verified grounded summary.
        """
        prompt = f"Search Google and answer concisely with up-to-date facts: {query}"
        for model in (settings.PRIMARY_MODEL, settings.FALLBACK_MODEL):
            try:
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                    ),
                )

                chunks: List[RetrievedChunk] = []
                summary_text = response.text or ""

                # Extract grounding metadata (citations & web sources)
                candidate = response.candidates[0] if response.candidates else None
                metadata = getattr(candidate, "grounding_metadata", None) if candidate else None
                queries = getattr(metadata, "web_search_queries", []) if metadata else []
                chunks_info = getattr(metadata, "grounding_chunks", []) if metadata else []

                if chunks_info:
                    for i, gc in enumerate(chunks_info[:top_k]):
                        web_info = getattr(gc, "web", None)
                        uri = getattr(web_info, "uri", "google_search") if web_info else "google_search"
                        title = getattr(web_info, "title", uri) if web_info else uri
                        chunks.append(
                            RetrievedChunk(
                                id=f"web_google_{i}",
                                content=f"{title}: {summary_text[:300]}",
                                score=0.95,
                                source=uri,
                                page=None,
                                metadata={"url": uri, "title": title},
                            )
                        )

                # Fallback if no specific chunk metadata returned but answer is grounded
                if not chunks and summary_text:
                    chunks.append(
                        RetrievedChunk(
                            id="web_google_direct",
                            content=summary_text,
                            score=0.95,
                            source="https://google.com/search",
                            page=None,
                            metadata={"url": "https://google.com/search", "title": "Google Search Grounding"},
                        )
                    )

                return chunks, summary_text
            except Exception:
                if model == settings.FALLBACK_MODEL:
                    logging.exception("Gemini Google search grounding failed")
        return [], ""


web_search_tool = GeminiGoogleSearchTool()
