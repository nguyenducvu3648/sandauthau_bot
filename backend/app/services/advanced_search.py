"""Advanced search với RRF merge và multi-criteria ranking."""
import math
from typing import List, Dict, Any, Optional
from collections import defaultdict
from app.services.search import SearchService
from app.config import settings


class AdvancedSearchService:
    """Advanced search với multi-method execution, RRF, và ranking."""

    def __init__(self):
        self.search_service = SearchService()

    def execute_multi_method(
        self,
        query: str,
        methods: List[str],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute nhiều search methods và merge bằng RRF.

        Args:
            query: Search query
            methods: List của ["bm25", "vector", "hybrid", "filter"]
            filters: Metadata filters
            top_k: Số kết quả cuối cùng

        Returns:
            List docs đã ranked
        """
        all_results = []

        # Execute từng method
        for method in methods:
            if method == "bm25":
                results = self._execute_bm25(query, filters)
            elif method == "vector":
                results = self._execute_vector(query, filters)
            elif method == "hybrid":
                results = self._execute_hybrid(query, filters)
            elif method == "filter" and filters:
                results = self._execute_filter(query, filters)
            else:
                continue

            all_results.append({
                "method": method,
                "results": results
            })

        # Merge với RRF
        merged = self._rrf_merge(all_results, top_k=top_k * 2)

        # Multi-criteria ranking
        ranked = self._multi_criteria_rank(merged, query, filters)

        return ranked[:top_k]

    def metadata_only_search(
        self,
        filters: Dict[str, Any],
        top_k: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query thuần ES (không embed) khi chỉ có metadata.

        VD: "năm 2024 Hà Nội"
        """
        # Dùng SearchService._build_filter_clauses để xử lý đúng
        filter_clauses = self.search_service._build_filter_clauses(filters)

        body = {
            "query": {
                "bool": {
                    "must": filter_clauses
                }
            },
            "size": top_k,
            "sort": [
                {"publicDate": {"order": "desc"}},  # Mới nhất trước
                {"bidPrice": {"order": "desc"}}      # Giá trị cao
            ]
        }

        es_results = self.search_service.es.search(
            index=self.search_service.index,
            body=body
        )

        return self._parse_es_hits(es_results)

    def _execute_bm25(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute BM25 search."""
        results = self.search_service.bm25_search(query, top_k=50, filters=filters)
        return self._parse_es_hits(results)

    def _execute_vector(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute vector search."""
        results = self.search_service.vector_search(query, top_k=50, min_score=0.3, filters=filters)
        return self._parse_es_hits(results)

    def _execute_hybrid(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute hybrid search."""
        results = self.search_service.hybrid_search(
            query,
            top_k=50,
            min_score=0.3,
            text_weight=settings.RRF_WEIGHT_BM25 / (settings.RRF_WEIGHT_BM25 + settings.RRF_WEIGHT_VECTOR),
            filters=filters
        )
        return self._parse_es_hits(results)

    def _execute_filter(self, query: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute filter search."""
        results = self.search_service.filter_search(query, filters, top_k=50, min_score=0.3)
        return self._parse_es_hits(results)

    def _parse_es_hits(self, es_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse ES results thành list docs."""
        docs = []
        for hit in es_results.get("hits", {}).get("hits", []):
            doc = hit["_source"].copy()
            doc["_id"] = hit["_id"]
            doc["_score"] = hit.get("_score", 0)
            docs.append(doc)
        return docs

    def _rrf_merge(
        self,
        all_results: List[Dict[str, Any]],
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Reciprocal Rank Fusion merge.

        RRF score = sum(1 / (rank + k)) cho mỗi method
        """
        k = settings.RRF_K_CONSTANT
        doc_scores = defaultdict(float)
        doc_data = {}

        for method_result in all_results:
            method = method_result["method"]
            results = method_result["results"]

            for rank, doc in enumerate(results, start=1):
                doc_id = doc["_id"]
                doc_scores[doc_id] += 1 / (rank + k)

                # Lưu doc data (lấy từ method đầu tiên thấy)
                if doc_id not in doc_data:
                    doc_data[doc_id] = doc

        # Sort theo RRF score
        sorted_ids = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        merged = []
        for doc_id, rrf_score in sorted_ids[:top_k]:
            doc = doc_data[doc_id].copy()
            doc["rrf_score"] = rrf_score
            merged.append(doc)

        return merged

    def _multi_criteria_rank(
        self,
        docs: List[Dict[str, Any]],
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Multi-criteria ranking:
        Score = w1*search + w2*recency + w3*value + w4*exact_match
        """
        current_year = 2024  # TODO: dynamic

        for doc in docs:
            score = 0.0

            # 1. Search score (normalized RRF)
            rrf_score = doc.get("rrf_score", 0)
            if rrf_score > 0:
                # Normalize: max RRF thường ~0.05, scale lên 0-1
                normalized_search = min(1.0, rrf_score * 20)
                score += normalized_search * settings.RANK_WEIGHT_SEARCH

            # 2. Recency
            year = doc.get("year")
            if year:
                year_diff = current_year - int(year)
                recency_score = max(0, 1 - year_diff * 0.1)  # 2024→1.0, 2023→0.9, ...
                score += recency_score * settings.RANK_WEIGHT_RECENCY

            # 3. Value (bidPrice)
            price = doc.get("bidPrice", 0)
            if price and price > 0:
                # Log scale: 1 tỷ ~ 0.75, 1000 tỷ ~ 1.0
                value_score = min(1.0, math.log10(price) / 12)
                score += value_score * settings.RANK_WEIGHT_VALUE

            # 4. Exact match bonus
            if self._is_exact_match(query, doc):
                score += settings.RANK_WEIGHT_EXACT

            doc["final_score"] = score

        # Sort theo final score
        return sorted(docs, key=lambda x: x.get("final_score", 0), reverse=True)

    def _is_exact_match(self, query: str, doc: Dict[str, Any]) -> bool:
        """Check exact match: mã gói thầu, tên chính xác."""
        q_norm = query.lower().strip()

        # Check trong các fields quan trọng
        fields = ["bidNo", "bidId", "bidName"]
        for field in fields:
            value = doc.get(field, "")
            if value and q_norm in value.lower():
                return True

        return False
