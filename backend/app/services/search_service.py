"""Search service with RRF, reranker, fallback."""
from typing import List, Dict, Any, Tuple
from ..services.es_client import ESClient
from ..services.embedding import EmbeddingService
from ..services.location_service import LocationService
from ..config import settings
import json

class SearchService:
    """Search service với RRF + reranker + fallback."""

    def __init__(self):
        self.es = ESClient.get_client()
        self.index = settings.ES_INDEX

    async def search_with_fallback(self, query: str, filters: Dict[str, Any], method: str = "hybrid", top_k: int = 10) -> Tuple[List[Dict], List[str]]:
        # FIX LỖI 5: Dừng ở bước 4, không bỏ location
        steps = [
            (filters.copy(), []),
            ({k: v for k, v in filters.items() if k not in ["max_price"]}, ["max_price"]),
            ({k: v for k, v in filters.items() if k not in ["max_price", "min_price", "bidForm"]}, ["max_price", "min_price", "bidForm"]),
            ({k: v for k, v in filters.items() if k in ["location"]}, ["max_price", "min_price", "bidForm", "year"]),
        ]

        for step_filters, relaxed in steps:
            if method == "hybrid":
                results = await self.hybrid_search_rrf(query, top_k=50, filters=step_filters)
            elif method == "bm25_code":
                results = await self.bm25_search(query, top_k=top_k, filters=step_filters)
            else:
                results = await self.metadata_only_search(query, filters=step_filters, top_k=top_k)

            if results and len(results) > 0:
                # Conditional rerank
                if method == "hybrid" and len(results) > 10:
                    if results[0].get("_score", 0) <= results[1].get("_score", 0) * 1.5:
                        results = await self._rerank(query, results, top_k)
                return results[:top_k], relaxed

        # Không có kết quả sau 4 bước → signal hỏi user
        if "location" in filters:
            return [], ["ASK_USER_EXPAND_LOCATION"]
        return [], list(filters.keys())

    async def bm25_search(self, query: str, top_k: int = 10, filters: Dict[str, Any] = None) -> List[Dict]:
        query_clause = {"multi_match": {"query": query, "fields": ["search_text^3", "bidName^2", "procuringEntityName"], "type": "best_fields", "fuzziness": "AUTO", "prefix_length": 2}}
        filter_clauses = self._build_filter_clauses(filters) if filters else []
        body = {"query": {"bool": {"must": [query_clause], "filter": filter_clauses}} if filter_clauses else query_clause, "size": top_k}
        result = self.es.search(index=self.index, body=body)
        return [hit["_source"] for hit in result.get("hits", {}).get("hits", [])]

    async def vector_search(self, query: str, top_k: int = 10, filters: Dict[str, Any] = None) -> List[Dict]:
        query_vector = EmbeddingService.embed(query)
        filter_clauses = self._build_filter_clauses(filters) if filters else []
        knn_clause = {"field": "embedding", "query_vector": query_vector, "k": top_k, "num_candidates": top_k * 10}
        if filter_clauses:
            knn_clause["filter"] = {"bool": {"must": filter_clauses}}
        body = {"knn": knn_clause}
        result = self.es.search(index=self.index, body=body)
        hits = result.get("hits", {}).get("hits", [])
        if hits and hits[0]["_score"] < 0.7:
            return []
        return [hit["_source"] for hit in hits]

    async def hybrid_search_rrf(self, query: str, top_k: int = 10, filters: Dict[str, Any] = None) -> List[Dict]:
        # Manual merge: BM25 + vector with RRF-like scoring
        bm25_results = await self.bm25_search(query, top_k=50, filters=filters)
        vector_results = await self.vector_search(query, top_k=50, filters=filters)

        # FIX MAPPING #2: Dùng bidId (UUID) thay vì bidCode (không tồn tại)
        # RRF scoring: 1/(k + rank)
        k = 60
        scores = {}
        for rank, doc in enumerate(bm25_results):
            doc_id = doc.get('bidId', doc.get('bidName'))  # bidId thay vì bidCode
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        for rank, doc in enumerate(vector_results):
            doc_id = doc.get('bidId', doc.get('bidName'))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

        # Merge unique docs
        seen = {}
        for doc in bm25_results + vector_results:
            doc_id = doc.get('bidId', doc.get('bidName'))
            if doc_id not in seen:
                seen[doc_id] = doc

        # Sort by RRF score
        ranked = sorted(seen.items(), key=lambda x: scores.get(x[0], 0), reverse=True)
        return [doc for _, doc in ranked[:top_k]]

    async def metadata_only_search(self, query: str, filters: Dict[str, Any], top_k: int = 10) -> List[Dict]:
        filter_clauses = self._build_filter_clauses(filters)
        q_lower = query.lower()
        # FIX MAPPING #1: bidCloseDate thay vì deadline (field không tồn tại)
        if "sắp hết hạn" in q_lower or "deadline" in q_lower:
            sort = [{"bidCloseDate": "asc"}]
        elif "lớn nhất" in q_lower or "cao nhất" in q_lower:
            sort = [{"bidPrice": {"order": "desc", "missing": "_last"}}]
        elif "nhỏ nhất" in q_lower or "thấp nhất" in q_lower:
            sort = [{"bidPrice": {"order": "asc", "missing": "_last"}}]
        else:
            sort = [{"publicDate": "desc"}]
        body = {"query": {"bool": {"filter": filter_clauses}} if filter_clauses else {"match_all": {}}, "sort": sort, "size": top_k}
        result = self.es.search(index=self.index, body=body)
        return [hit["_source"] for hit in result.get("hits", {}).get("hits", [])]

    async def _rerank(self, query: str, results: List[Dict], top_k: int = 10) -> List[Dict]:
        if len(results) <= top_k:
            return results
        candidates = results[:20]
        titles = [f"{i+1}. {r.get('bidName', '')}" for i, r in enumerate(candidates)]
        prompt = f'Câu hỏi: "{query}"\n\nXếp hạng 20 gói thầu sau theo độ relevant (1=rất relevant, 5=không relevant):\n\n' + '\n'.join(titles) + '\n\nTrả về JSON array: [{"index": 1, "score": 1}, ...]'
        try:
            import asyncio
            from ..services.deepseek_client import DeepSeekClient
            response = await asyncio.wait_for(
                DeepSeekClient.chat(messages=[{"role": "user", "content": prompt}], response_format="json", temperature=0.1, max_tokens=400),
                timeout=3.0
            )
            scores = json.loads(response)
            scored = [(candidates[s["index"]-1], s["score"]) for s in scores if s["index"] <= len(candidates)]
            scored.sort(key=lambda x: x[1])
            return [item[0] for item in scored][:top_k]
        except (asyncio.TimeoutError, Exception):
            return results[:top_k]

    def _build_filter_clauses(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        clauses = []
        for field, value in filters.items():
            if field == "location":
                # FIX MAPPING #4: value là list codes, dùng terms thay vì term
                if isinstance(value, list) and value:
                    clauses.append({
                        "nested": {
                            "path": "locations",
                            "query": {"terms": {"locations.provCode": value}}
                        }
                    })
            elif field == "year":
                clauses.append({"range": {"publicDate": {"gte": f"{value}-01-01", "lte": f"{value}-12-31"}}})
            elif field == "min_price":
                clauses.append({"range": {"bidPrice": {"gte": value}}})
            elif field == "max_price":
                clauses.append({"range": {"bidPrice": {"lte": value}}})
            elif field == "bidForm":
                clauses.append({"term": {"bidForm": value}})
            elif isinstance(value, list):
                clauses.append({"terms": {field: value}})
            else:
                clauses.append({"term": {field: value}})
        return clauses
