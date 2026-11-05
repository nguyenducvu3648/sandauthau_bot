"""Search request models."""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class BM25SearchRequest(BaseModel):
    """BM25 text search request."""
    query: str = Field(..., description="Search query text")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")

class VectorSearchRequest(BaseModel):
    """Vector similarity search request."""
    query: str = Field(..., description="Search query text")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    min_score: float = Field(0.5, ge=0, le=1, description="Minimum similarity score")

class HybridSearchRequest(BaseModel):
    """Hybrid search (BM25 + Vector) request."""
    query: str = Field(..., description="Search query text")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    min_score: float = Field(0.5, ge=0, le=1, description="Minimum similarity score")
    text_weight: float = Field(0.3, ge=0, le=1, description="BM25 weight (0-1)")

class FilterSearchRequest(BaseModel):
    """Metadata filter + vector search request."""
    query: str = Field(..., description="Search query text")
    filters: Dict[str, Any] = Field(..., description="Metadata filters")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    min_score: float = Field(0.5, ge=0, le=1, description="Minimum similarity score")

class AutoSearchRequest(BaseModel):
    """Auto-routing intelligent search request."""
    query: str = Field(..., description="Search query text")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    session_id: Optional[str] = Field(None, description="Session ID cho context tracking")

