import time
from typing import List, Optional
from google import genai
from google.genai import types
from app.config import settings


class EmbeddingClient:
    """
    Google Gemini Batch Embedding Client with Matryoshka (MRL) truncation.
    """

    def __init__(self):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("GEMINI_API_KEY", "")

        self.client = genai.Client(api_key=api_key) if api_key else None
        self.model_name = settings.EMBEDDING_MODEL
        self.output_dim = settings.EMBEDDING_DIM

    def embed_query(self, query: str) -> List[float]:
        """Embed a single search query."""
        if not self.client:
            raise ValueError("GEMINI_API_KEY not configured for embeddings.")

        response = self.client.models.embed_content(
            model=self.model_name,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.output_dim,
            ),
        )
        return response.embeddings[0].values

    def embed_documents(self, documents: List[str], batch_size: int = 10) -> List[List[float]]:
        """Batch embed document chunks with rate-limiting backoff."""
        if not self.client:
            raise ValueError("GEMINI_API_KEY not configured for embeddings.")

        all_embeddings = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            for doc in batch:
                try:
                    res = self.client.models.embed_content(
                        model=self.model_name,
                        contents=doc,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.output_dim,
                        ),
                    )
                    all_embeddings.append(res.embeddings[0].values)
                except Exception as e:
                    time.sleep(1.0)
                    # Retry once on error
                    res = self.client.models.embed_content(
                        model=self.model_name,
                        contents=doc,
                        config=types.EmbedContentConfig(
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=self.output_dim,
                        ),
                    )
                    all_embeddings.append(res.embeddings[0].values)
            time.sleep(0.1)  # Gentle spacing
        return all_embeddings


embedding_client = EmbeddingClient()
