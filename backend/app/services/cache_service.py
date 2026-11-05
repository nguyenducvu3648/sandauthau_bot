"""3-tier cache service."""
from typing import Any, Optional, Dict
from cachetools import TTLCache
from collections import defaultdict
import hashlib
import json


class CacheService:
    """3-tier cache: query results, embeddings, user context."""

    # Cache Level 1: Query results (15 phút)
    _query_cache = TTLCache(maxsize=1000, ttl=900)

    # Cache Level 2: Embedding vectors (1 giờ)
    _embed_cache = TTLCache(maxsize=5000, ttl=3600)

    # Cache Level 3: User context (session-based, không expire tự động)
    _user_context_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_query_cache(cls, query: str, methods: list, filters: dict) -> Optional[list]:
        """Get cached query results."""
        key = cls._make_query_key(query, methods, filters)
        return cls._query_cache.get(key)

    @classmethod
    def set_query_cache(cls, query: str, methods: list, filters: dict, results: list):
        """Cache query results."""
        key = cls._make_query_key(query, methods, filters)
        cls._query_cache[key] = results

    @classmethod
    def get_embedding(cls, text: str) -> Optional[list]:
        """Get cached embedding vector."""
        key = cls._make_embed_key(text)
        return cls._embed_cache.get(key)

    @classmethod
    def set_embedding(cls, text: str, vector: list):
        """Cache embedding vector."""
        key = cls._make_embed_key(text)
        cls._embed_cache[key] = vector

    @classmethod
    def get_user_context(cls, session_id: str) -> Dict[str, Any]:
        """
        Get user context cho session.

        Returns:
            {
                "frequent_filters": {"location": "Hà Nội", ...},
                "interests": ["xây dựng", "y tế"],
                "query_history": [...],
                "query_count": 10
            }
        """
        if session_id not in cls._user_context_cache:
            cls._user_context_cache[session_id] = {
                "frequent_filters": defaultdict(int),
                "interests": defaultdict(int),
                "query_history": [],
                "query_count": 0
            }
        return cls._user_context_cache[session_id]

    @classmethod
    def update_user_context(
        cls,
        session_id: str,
        query: str,
        filters: dict,
        keywords: list[str]
    ):
        """
        Update user context sau mỗi query.

        Tracks:
        - Frequent filters (location, year, bidForm)
        - Interests (keywords)
        - Query history
        """
        context = cls.get_user_context(session_id)

        # Update filters frequency
        for field, value in filters.items():
            context["frequent_filters"][f"{field}:{value}"] += 1

        # Update interests (keywords trong query)
        for keyword in keywords:
            if len(keyword) > 3:  # Skip short words
                context["interests"][keyword.lower()] += 1

        # Update query history (keep last 10)
        context["query_history"].append({
            "query": query,
            "filters": filters
        })
        if len(context["query_history"]) > 10:
            context["query_history"].pop(0)

        context["query_count"] += 1

    @classmethod
    def get_frequent_filters(cls, session_id: str, threshold: int = 3) -> dict:
        """
        Lấy frequent filters của user (xuất hiện >= threshold lần).

        Returns:
            {"location": "Hà Nội", "year": 2024}
        """
        context = cls.get_user_context(session_id)
        frequent = {}

        for key, count in context["frequent_filters"].items():
            if count >= threshold:
                field, value = key.split(":", 1)
                # Parse value type
                if field == "year":
                    value = int(value)
                frequent[field] = value

        return frequent

    @classmethod
    def clear_user_context(cls, session_id: str):
        """Clear context cho session (khi user logout)."""
        if session_id in cls._user_context_cache:
            del cls._user_context_cache[session_id]

    @classmethod
    def _make_query_key(cls, query: str, methods: list, filters: dict) -> str:
        """Tạo cache key cho query."""
        data = {
            "query": query.lower().strip(),
            "methods": sorted(methods),
            "filters": sorted(filters.items())
        }
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()

    @classmethod
    def _make_embed_key(cls, text: str) -> str:
        """Tạo cache key cho embedding."""
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    @classmethod
    def get_cache_stats(cls) -> dict:
        """Get cache statistics."""
        return {
            "query_cache": {
                "size": len(cls._query_cache),
                "maxsize": cls._query_cache.maxsize,
                "ttl": cls._query_cache.ttl
            },
            "embed_cache": {
                "size": len(cls._embed_cache),
                "maxsize": cls._embed_cache.maxsize,
                "ttl": cls._embed_cache.ttl
            },
            "user_context": {
                "sessions": len(cls._user_context_cache),
                "total_queries": sum(
                    ctx["query_count"]
                    for ctx in cls._user_context_cache.values()
                )
            }
        }
