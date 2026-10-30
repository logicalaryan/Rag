import asyncio
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

    async def execute(self, query: str, top_k: int = 4, filter_metadata: Optional[Dict[str, Any]] = None) -> List[RetrievedChunk]:
        return await asyncio.to_thread(self._sync_retrieve, query, top_k, filter_metadata)

    def _sync_retrieve(self, query: str, top_k: int, filter_metadata: Optional[Dict[str, Any]]) -> List[RetrievedChunk]:
        all_chunks = vector_store.get_all_chunks()
        if not all_chunks:
            return []

        # 1. Dense Vector Search
        try:
            query_emb = embedding_client.embed_query(query)
            dense_results = vector_store.query_similarity(query_emb, top_k=settings.TOP_K_CANDIDATES, filter_metadata=filter_metadata)
        except Exception as e:
            dense_results = []

        # 2. Sparse BM25 Search
        corpus_texts = [c["content"] for c in all_chunks]
        tokenized_corpus = [doc.lower().split() for doc in corpus_texts]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        bm25_scores = bm25.get_scores(tokenized_query)

        bm25_ranked_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[: settings.TOP_K_CANDIDATES]
        bm25_results = []
        for rank, idx in enumerate(bm25_ranked_indices):
            raw = all_chunks[idx]
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
