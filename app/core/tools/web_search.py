import asyncio
from typing import List
from app.db.models import RetrievedChunk

try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


class WebSearchTool:
    """Fallback tool searching live public web using DuckDuckGo."""
    name = "search_web"
    description = "Searches the live web for recent external facts or public information."

    async def execute(self, query: str, top_k: int = 3, **kwargs) -> List[RetrievedChunk]:
        return await asyncio.to_thread(self._sync_search, query, top_k)

    def _sync_search(self, query: str, top_k: int) -> List[RetrievedChunk]:
        if not DDGS_AVAILABLE:
            return []

        results = []
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=top_k))
                for idx, r in enumerate(raw_results):
                    snippet = f"{r.get('title', '')}: {r.get('body', '')}"
                    url = r.get("href", "web_source")
                    results.append(
                        RetrievedChunk(
                            id=f"web_{idx}",
                            content=snippet,
                            score=0.80,
                            source=url,
                            page=None,
                            metadata={"url": url, "title": r.get("title")},
                        )
                    )
        except Exception as e:
            pass
        return results


web_search_tool = WebSearchTool()
