"""Embedding service."""
from typing import Optional
from sentence_transformers import SentenceTransformer
from ..config import settings
from .cache_service import CacheService

class EmbeddingService:
    """Embedding service singleton với cache."""

    _instance: Optional[SentenceTransformer] = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Get or load embedding model."""
        if cls._instance is None:
            cls._instance = SentenceTransformer(settings.MODEL_NAME)
        return cls._instance

    @classmethod
    def embed(cls, text: str) -> list[float]:
        """
        Generate embedding for text với cache.

        Check cache trước, nếu miss → encode và cache lại.
        """
        # Check cache
        cached = CacheService.get_embedding(text)
        if cached is not None:
            return cached

        # Cache miss → encode
        model = cls.get_model()
        embedding = model.encode(text, convert_to_tensor=False)
        vector = embedding.tolist()

        # Cache result
        CacheService.set_embedding(text, vector)

        return vector

