"""Search service."""
from typing import List, Dict, Any
from ..services.es_client import ESClient
from ..services.embedding import EmbeddingService
from ..services.location_mapping import get_location_terms
from ..config import settings

class SearchService:
    """Search service for all query types."""

    def __init__(self):
        self.es = ESClient.get_client()
        self.index = settings.ES_INDEX

    def bm25_search(self, query: str, top_k: int = 10, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """BM25 text search."""
        query_clause = {
            "multi_match": {
                "query": query,
                "fields": ["search_text^2", "bidName^1.5", "procuringEntityName"]
            }
        }

        # Apply filters
        if filters:
            filter_clauses = self._build_filter_clauses(filters)
            body = {
                "query": {
                    "bool": {
                        "must": [query_clause],
                        "filter": filter_clauses
                    }
                },
                "size": top_k
            }
        else:
            body = {
                "query": query_clause,
                "size": top_k
            }

        return self.es.search(index=self.index, body=body)

    def vector_search(self, query: str, top_k: int = 10, min_score: float = 0.5, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Vector similarity search."""
        query_vector = EmbeddingService.embed(query)

        knn_clause = {
            "field": "embedding",
            "query_vector": query_vector,
            "k": top_k,
            "num_candidates": top_k * 10
        }

        # Apply filters
        if filters:
            filter_clauses = self._build_filter_clauses(filters)
            knn_clause["filter"] = {"bool": {"must": filter_clauses}}

        body = {
            "knn": knn_clause,
            "min_score": min_score
        }
        return self.es.search(index=self.index, body=body)

    def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.5,
        text_weight: float = 0.3,
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Hybrid search (BM25 + Vector)."""
        query_vector = EmbeddingService.embed(query)
        vector_weight = 1.0 - text_weight

        query_clause = {
            "multi_match": {
                "query": query,
                "fields": ["search_text^2", "bidName^1.5", "procuringEntityName"]
            }
        }

        # Apply filters
        if filters:
            filter_clauses = self._build_filter_clauses(filters)
            query_clause = {
                "bool": {
                    "must": [query_clause],
                    "filter": filter_clauses
                }
            }

        body = {
            "query": {
                "script_score": {
                    "query": query_clause,
                    "script": {
                        "source": f"_score * {text_weight} + cosineSimilarity(params.query_vector, 'embedding') * {vector_weight}",
                        "params": {"query_vector": query_vector}
                    }
                }
            },
            "size": top_k,
            "min_score": min_score
        }
        return self.es.search(index=self.index, body=body)

    def filter_search(
        self,
        query: str,
        filters: Dict[str, Any],
        top_k: int = 10,
        min_score: float = 0.5
    ) -> Dict[str, Any]:
        """Vector search with metadata filters."""
        query_vector = EmbeddingService.embed(query)

        # Build filter clauses
        filter_clauses = self._build_filter_clauses(filters)

        body = {
            "knn": {
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": top_k * 10,
                "filter": {"bool": {"must": filter_clauses}} if filter_clauses else None
            },
            "min_score": min_score
        }
        return self.es.search(index=self.index, body=body)

    def _build_filter_clauses(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build ES filter clauses từ filters dict."""
        clauses = []

        for field, value in filters.items():
            if field == "location":
                # Dùng canonical mapping thay vì wildcard
                terms = get_location_terms(value)
                clauses.append({
                    "nested": {
                        "path": "locations",
                        "query": {
                            "bool": {
                                "should": [
                                    {"terms": {"locations.provName.keyword": terms}},
                                    {"terms": {"locations.districtName.keyword": terms}}
                                ]
                            }
                        }
                    }
                })
            elif field == "year":
                # Year filter trên publicDate
                clauses.append({
                    "range": {
                        "publicDate": {
                            "gte": f"{value}-01-01",
                            "lte": f"{value}-12-31"
                        }
                    }
                })
            elif field == "min_price":
                # Giá tối thiểu
                clauses.append({
                    "range": {
                        "bidPrice": {"gte": value}
                    }
                })
            elif field == "max_price":
                # Giá tối đa
                clauses.append({
                    "range": {
                        "bidPrice": {"lte": value}
                    }
                })
            elif field == "bidForm":
                clauses.append({"term": {"bidForm": value}})
            elif isinstance(value, list):
                clauses.append({"terms": {field: value}})
            else:
                clauses.append({"term": {field: value}})

        return clauses
