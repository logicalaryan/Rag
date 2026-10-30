import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from app.config import settings
from app.db.models import RetrievedChunk


class VectorStoreAdapter:
    """
    Persistent Vector Store Adapter using ChromaDB.
    Supports HNSW indexing and metadata filtering.
    """

    def __init__(self, collection_name: str = "production_rag_docs"):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def upsert_chunks(
        self,
        chunk_ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Batch upsert chunks into ChromaDB with embeddings and metadata."""
        if not chunk_ids:
            return
        self.collection.upsert(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query_similarity(
        self,
        query_embedding: List[float],
        top_k: int = 15,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """Query vector database by embedding cosine distance."""
        count = self.collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": actual_k,
        }
        if filter_metadata:
            query_params["where"] = filter_metadata

        results = self.collection.query(**query_params)

        retrieved = []
        if results and results.get("ids") and len(results["ids"][0]) > 0:
            for idx in range(len(results["ids"][0])):
                doc_id = results["ids"][0][idx]
                content = results["documents"][0][idx]
                meta = results["metadatas"][0][idx] if results.get("metadatas") else {}
                # Chroma returns cosine distance (0 to 2, where 0 is identical)
                distance = results["distances"][0][idx] if results.get("distances") else 0.0
                score = max(0.0, 1.0 - distance)

                retrieved.append(
                    RetrievedChunk(
                        id=doc_id,
                        content=content,
                        score=score,
                        source=meta.get("source", "unknown"),
                        page=meta.get("page"),
                        metadata=meta,
                    )
                )
        return retrieved

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieve all documents and metadata for lexical BM25 indexing."""
        data = self.collection.get()
        chunks = []
        if data and data.get("ids"):
            for idx in range(len(data["ids"])):
                chunks.append({
                    "id": data["ids"][idx],
                    "content": data["documents"][idx],
                    "metadata": data["metadatas"][idx] if data.get("metadatas") else {},
                })
        return chunks

    def count(self) -> int:
        return self.collection.count()


# Global Singleton Adapter
vector_store = VectorStoreAdapter()
