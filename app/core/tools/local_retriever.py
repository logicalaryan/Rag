import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from rank_bm25 import BM25Okapi
from app.config import settings
from app.db.models import RetrievedChunk
from app.db.vector_store import vector_store
from app.core.indexing.embeddings import embedding_client

try:
    from flashrank import Ranker, RerankRequest
    FLASHRANK_AVAILABLE = True
except ImportError:
    FLASHRANK_AVAILABLE = False


class LocalRetrieverTool:
    """
    Two-Stage Hybrid Retrieval:
    Stage 1: Dense Vector (ChromaDB) + Sparse Lexical (BM25) fused via Reciprocal Rank Fusion (RRF)
    Stage 2: Cross-Encoder Reranking via FlashRank
    """
    name = "search_local"
    description = "Searches the internal indexed document repository for company policies and knowledge."

    def __init__(self):
        self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2") if FLASHRANK_AVAILABLE else None
        self._bm25: Optional[BM25Okapi] = None
        self._chunks: List[Dict[str, Any]] = []

    def invalidate_cache(self) -> None:
        self._bm25 = None
        self._chunks = []

    def _ensure_bm25(self) -> None:
        if self._bm25 is None or len(self._chunks) != vector_store.count():
            self._chunks = vector_store.get_all_chunks()
            if self._chunks:
                tokenized = [re.findall(r"\w+", c["content"].lower()) for c in self._chunks]
                self._bm25 = BM25Okapi(tokenized)

    async def execute(self, query: str, top_k: int = 4, filter_metadata: Optional[Dict[str, Any]] = None) -> List[RetrievedChunk]:
        return await asyncio.to_thread(self._sync_retrieve, query, top_k, filter_metadata)

    def _sync_retrieve(self, query: str, top_k: int, filter_metadata: Optional[Dict[str, Any]]) -> List[RetrievedChunk]:
        self._ensure_bm25()
        if not self._chunks:
            return []

        # 1. Dense Vector Search
        try:
            query_emb = embedding_client.embed_query(query)
            dense_results = vector_store.query_similarity(query_emb, top_k=settings.TOP_K_CANDIDATES, filter_metadata=filter_metadata)
        except Exception:
            logging.exception("dense search failed, using BM25 only")
            dense_results = []

        # 2. Sparse BM25 Search
        bm25_results = []
        tokenized_query = re.findall(r"\w+", query.lower())
        if self._bm25 and tokenized_query:
            bm25_scores = self._bm25.get_scores(tokenized_query)
            bm25_ranked_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)
            for idx in bm25_ranked_indices:
                if bm25_scores[idx] <= 0:
                    break
                raw = self._chunks[idx]
                if filter_metadata and any(raw["metadata"].get(k) != v for k, v in filter_metadata.items()):
                    continue
                bm25_results.append(
                    RetrievedChunk(
                        id=raw["id"],
                        content=raw["content"],
                        score=float(bm25_scores[idx]),
                        source=raw["metadata"].get("source", "unknown"),
                        page=raw["metadata"].get("page"),
                        metadata=raw["metadata"],
                    )
                )
                if len(bm25_results) >= settings.TOP_K_CANDIDATES:
                    break

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(dense_results):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank + 1))
            chunk_map[chunk.id] = chunk

        for rank, chunk in enumerate(bm25_results):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (60.0 + rank + 1))
            if chunk.id not in chunk_map:
                chunk_map[chunk.id] = chunk

        fused_candidates = sorted(
            chunk_map.values(),
            key=lambda c: rrf_scores.get(c.id, 0.0),
            reverse=True
        )[: settings.TOP_K_CANDIDATES]

        # 4. Cross-Encoder Reranking (Stage 2)
        if self.ranker and fused_candidates:
            passages = [{"id": c.id, "text": c.content, "meta": c.metadata} for c in fused_candidates]
            rerank_req = RerankRequest(query=query, passages=passages)
            reranked = self.ranker.rerank(rerank_req)

            final_results = []
            for item in reranked[:top_k]:
                orig = chunk_map[item["id"]]
                orig.score = float(item["score"])
                final_results.append(orig)
            return final_results

        return fused_candidates[:top_k]


local_retriever = LocalRetrieverTool()
