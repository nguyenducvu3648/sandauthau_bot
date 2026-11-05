"""
Search Service V4 - Full 8-step implementation theo Sandauthau_Search_V4_Spec.md.
Không chia layer, code toàn bộ luồng trong 1 file.
"""
import re
import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from elasticsearch import Elasticsearch, AsyncElasticsearch
from anthropic import AsyncAnthropic

from app.services.location_service import LocationService
from app.services.deepseek_client import DeepSeekClient
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class IntentAnalysis:
    """Kết quả phân tích từ LLM (bước 3)."""
    scope: str  # "new" | "continuation"
    output_mode: str  # "list" | "aggregate" | "compare" | "chat"
    topic: Optional[str]
    filters: Dict[str, Any]
    clear: List[str]
    sort: Optional[str]
    aggregate_by: Optional[str]
    top_n: Optional[int]
    compare_entities: Optional[List[str]]
    needs_clarification: bool
    clarification_question: Optional[str]
    fallback_to_v3: bool = False
    parse_time_ms: float = 0


@dataclass
class SearchResult:
    """Kết quả cuối cùng trả về user."""
    bids: List[Dict[str, Any]]
    total: int
    took_ms: float
    filters_applied: Dict[str, Any]
    relaxed_filters: List[str]
    clarification: Optional[str]
    aggregation: Optional[Dict[str, Any]]
    session_id: str
    method: Optional[str] = None  # Search method used (hybrid, filter_only, etc.)
    timings: Optional[Dict[str, float]] = None  # Timing breakdown
    _debug_intent: Optional[Dict[str, Any]] = None  # Debug field


# ============================================================================
# STEP 1: FAST PATH
# ============================================================================

class FastPath:
    """Bước 1 - Fast path không qua LLM."""

    # Regex mã gói thầu (P4 - từ data thật)
    # Support: pure 12 digits, XX+6-10 digits, hoặc XX-YYYY-NNN
    BID_CODE_PATTERN = re.compile(r'\b(\d{12}|[A-Z]{2}[-]?\d{4}[-]?\d{1,6}|[A-Z]{2}\d{6,10})\b')

    # Stopwords xã giao
    GREETINGS = {
        'xin chào', 'chào bạn', 'hello', 'hi',
        'cảm ơn', 'thank you', 'thanks', 'cám ơn'
    }

    @classmethod
    def extract_bid_code(cls, query: str) -> Optional[str]:
        """Extract mã gói thầu, mask để không bị bóc filter."""
        match = cls.BID_CODE_PATTERN.search(query.upper())
        return match.group(0) if match else None

    @classmethod
    def is_pure_greeting(cls, query: str) -> bool:
        """Check xã giao thuần (sau khi bỏ lời chào, còn rỗng)."""
        q_lower = query.lower().strip()

        # Bỏ stopwords
        for greeting in cls.GREETINGS:
            q_lower = re.sub(rf'\b{re.escape(greeting)}\b', '', q_lower)

        # Sau khi bỏ, chỉ còn dấu câu/khoảng trắng → thuần
        return len(q_lower.strip(' ,.!?')) == 0


# ============================================================================
# STEP 2: PAGINATION
# ============================================================================

class PaginationHandler:
    """Bước 2 - Phân trang nhanh từ ranked_ids."""

    PAGINATION_PATTERNS = [
        r'^\s*(thêm|xem thêm|tiếp|trang tiếp)\s*(\d+)?\s*(gói|kết quả|nữa)?\s*$',
        r'^\s*trang\s+(tiếp theo|sau)\s*$',
        r'^\s*next\s*$'
    ]

    @classmethod
    def is_pagination(cls, query: str, session: Optional[Dict]) -> bool:
        """Check câu hỏi là pagination và session có ranked_ids."""
        if not session or not session.get('ranked_ids'):
            return False

        q_lower = query.lower().strip()
        return any(re.match(p, q_lower) for p in cls.PAGINATION_PATTERNS)

    @classmethod
    def extract_limit(cls, query: str) -> int:
        """Extract số lượng gói cần lấy thêm (default 10)."""
        match = re.search(r'(\d+)', query)
        return int(match.group(1)) if match else 10


# ============================================================================
# STEP 3: LLM INTENT ANALYSIS
# ============================================================================

class IntentAnalyzer:
    """Bước 3 - Phân tích intent bằng LLM."""

    # Schema JSON (cố định)
    SCHEMA = {
        "type": "object",
        "properties": {
            "scope": {"type": "string", "enum": ["new", "continuation"]},
            "output_mode": {"type": "string", "enum": ["list", "aggregate", "compare", "chat"]},
            "topic": {"type": ["string", "null"]},
            "filters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "object",
                        "properties": {
                            "include": {"type": "array", "items": {"type": "string"}},
                            "exclude": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "year": {"type": ["integer", "null"]},
                    "price_min": {"type": ["number", "null"]},
                    "price_max": {"type": ["number", "null"]},
                    "bid_form": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"], "enum": ["open", "closed", "awarded", None]},
                    "deadline_from": {"type": ["string", "null"]},
                    "deadline_to": {"type": ["string", "null"]}
                }
            },
            "clear": {"type": "array", "items": {"type": "string"}},
            "sort": {"type": ["string", "null"]},
            "aggregate_by": {"type": ["string", "null"]},
            "top_n": {"type": ["integer", "null"]},
            "compare_entities": {"type": ["array", "null"]},
            "needs_clarification": {"type": "boolean"},
            "clarification_question": {"type": ["string", "null"]}
        },
        "required": ["scope", "output_mode"]
    }

    def __init__(self, llm_client, location_service: LocationService):
        """
        Args:
            llm_client: LLM client (OpenAI-compatible hoặc Anthropic)
            location_service: LocationService instance
        """
        self.client = llm_client
        self.location = location_service
        self.is_anthropic = hasattr(llm_client, 'messages')  # Detect if Anthropic client

    async def analyze(
        self,
        query: str,
        session: Optional[Dict],
        today: str,
        timeout_ms: int = 6000
    ) -> IntentAnalysis:
        """Phân tích câu hỏi bằng LLM, trả về JSON."""
        start = time.time()

        # Build prompt
        prompt = self._build_prompt(query, session, today)

        try:
            # Call LLM với timeout
            if self.is_anthropic:
                # Anthropic client
                response = await asyncio.wait_for(
                    self.client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1024,
                        temperature=0,
                        messages=[{"role": "user", "content": prompt}]
                    ),
                    timeout=timeout_ms / 1000
                )
                content = response.content[0].text
            else:
                # OpenAI-compatible / Ollama-compatible client (DeepSeek qua xah.io)
                content = await asyncio.wait_for(
                    DeepSeekClient.chat(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0,
                        max_tokens=1024
                    ),
                    timeout=timeout_ms / 1000
                )

            # Debug: print raw LLM response
            if settings.DEBUG_LLM:
                print(f"\n=== LLM RAW RESPONSE ===\n{content}\n=== END ===\n")

            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group(0))

            # Validate
            validated = self._validate(data)
            validated.parse_time_ms = (time.time() - start) * 1000

            return validated

        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError, Exception) as e:
            # Fallback: hybrid search với query gốc, không filters
            logger.warning(f"LLM ANALYSIS FAILED: {type(e).__name__}: {e}")
            if settings.DEBUG_LLM:
                import traceback
                traceback.print_exc()

            return IntentAnalysis(
                scope="new",
                output_mode="list",
                topic=query,  # dùng query gốc làm topic
                filters={},  # không filters khi timeout
                clear=[],
                sort=None,
                aggregate_by=None,
                top_n=None,
                compare_entities=None,
                needs_clarification=False,
                clarification_question=None,
                fallback_to_v3=True,
                parse_time_ms=(time.time() - start) * 1000
            )

    def _build_prompt(self, query: str, session: Optional[Dict], today: str) -> str:
        """Build prompt cho LLM."""
        # Load provinces from JSON
        provinces = self.location._load_provinces()
        province_list = ", ".join(f'"{name}"' for name in provinces.keys())

        session_ctx = {}
        if session:
            session_ctx = {
                "last_filters": session.get("filters", {}),
                "last_topic": session.get("topic", ""),
                "last_operation": session.get("operation", "")
            }

        return f"""Phân tích câu hỏi tìm kiếm gói thầu, trả về JSON theo schema.

**Câu hỏi:** {query}
**Hôm nay:** {today}
**Session:** {json.dumps(session_ctx, ensure_ascii=False)}

**Danh mục tỉnh:** {json.dumps(list(provinces.keys())[:10], ensure_ascii=False)}... (34 tỉnh)

**Quy tắc:**
1. Phủ định ("không phải", "ngoài", "trừ") → exclude
2. So sánh → output_mode=compare
3. Thống kê ("bao nhiêu", "top", "tổng") → output_mode=aggregate
4. Tham chiếu ("còn", "nó", "thêm") → scope=continuation
5. Bỏ stopword khỏi topic
6. Chỉ dùng giá trị trong danh mục, không biết thì null

**Trả về JSON:**
```json
{json.dumps(self.SCHEMA, ensure_ascii=False, indent=2)}
```"""

    def _validate(self, data: Dict) -> IntentAnalysis:
        """Validate và chuẩn hóa JSON."""
        # Check required
        if "scope" not in data or "output_mode" not in data:
            raise ValueError("Missing required fields")

        # Chuẩn hóa location codes
        filters = data.get("filters", {})
        if "location" in filters and "include" in filters["location"]:
            codes = []
            for name in filters["location"]["include"]:
                prov_codes = self.location.get_province_codes(name)
                if prov_codes:
                    codes.extend(prov_codes)
            filters["location"]["include"] = codes

        return IntentAnalysis(
            scope=data["scope"],
            output_mode=data["output_mode"],
            topic=data.get("topic"),
            filters=filters,
            clear=data.get("clear", []),
            sort=data.get("sort"),
            aggregate_by=data.get("aggregate_by"),
            top_n=data.get("top_n"),
            compare_entities=data.get("compare_entities"),
            needs_clarification=data.get("needs_clarification", False),
            clarification_question=data.get("clarification_question")
        )


# ============================================================================
# STEP 4: EXECUTION
# ============================================================================

class SearchExecutor:
    """Bước 4 - Thực thi search/aggregation."""

    def __init__(self, es: Elasticsearch):
        self.es = es

    def merge_state(
        self,
        analysis: IntentAnalysis,
        session: Optional[Dict]
    ) -> Tuple[Dict[str, Any], str]:
        """Gộp filters từ session + analysis, normalize location names to codes."""
        if analysis.scope == "new" or not session:
            filters = analysis.filters
        else:
            # Continuation: merge
            merged = dict(session.get("filters", {}))
            for k, v in analysis.filters.items():
                if v is not None:
                    merged[k] = v
            # Clear theo yêu cầu
            for k in analysis.clear:
                merged.pop(k, None)
            filters = merged

        # Normalize location names → codes
        if "location" in filters and "include" in filters["location"]:
            names = filters["location"]["include"]
            codes = []
            for name in names:
                # If already a code (2-digit), keep it
                if isinstance(name, str) and name.isdigit() and len(name) <= 3:
                    codes.append(name)
                else:
                    # Map name → code
                    code = LocationService.get_province_code(name)
                    if code:
                        codes.append(code)
            filters["location"]["include"] = codes

        topic = analysis.topic if analysis.scope == "new" else (analysis.topic or session.get("topic", ""))

        return filters, topic

    def choose_method(self, analysis: IntentAnalysis, code: Optional[str], topic: str) -> str:
        """Chọn method search (code, không LLM)."""
        if code:
            return "by_code"
        if not topic:
            return "filter_only"
        return "hybrid"

    def search_by_code(self, code: str) -> List[Dict]:
        """Search by bid code."""
        result = self.es.search(
            index=settings.ELASTICSEARCH_INDEX,
            body={
                "query": {"term": {"bidNo": code}},
                "size": 1
            }
        )
        return [hit["_source"] for hit in result["hits"]["hits"]]

    def search_filter_only(
        self,
        filters: Dict[str, Any],
        sort: Optional[str],
        size: int = 10
    ) -> Tuple[List[Dict], int]:
        """Search chỉ với filter, không có topic."""
        query_body = {
            "query": {"bool": {"filter": self._build_filter_clauses(filters)}},
            "size": size,
            "track_total_hits": True
        }

        # Sort
        if sort == "newest":
            query_body["sort"] = [{"publishedDate": "desc"}]
        elif sort == "deadline_asc":
            query_body["sort"] = [{"bidCloseDate": "asc"}]
        elif sort == "price_desc":
            query_body["sort"] = [{"bidValue": "desc"}]

        result = self.es.search(index=settings.ELASTICSEARCH_INDEX, body=query_body)

        bids = [hit["_source"] for hit in result["hits"]["hits"]]
        total = result["hits"]["total"]["value"]

        return bids, total

    def search_hybrid(
        self,
        topic: str,
        filters: Dict[str, Any],
        k: int = 40
    ) -> Tuple[List[str], Dict[str, float], int]:
        """Hybrid search: BM25 + vector parallel, trả ranked doc IDs + scores + total_matched."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        filter_clauses = self._build_filter_clauses(filters)

        # BM25 query
        bm25_query = {
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": topic,
                            "fields": ["search_text^3", "bidName^2", "procuringEntityName"],
                            "fuzziness": "AUTO",
                            "prefix_length": 2
                        }
                    },
                    "filter": filter_clauses
                }
            },
            "size": k,
            "track_total_hits": True
        }

        # Vector query
        def run_bm25():
            return self.es.search(index=settings.ELASTICSEARCH_INDEX, body=bm25_query)

        def run_vector():
            try:
                from app.services.embedding import EmbeddingService
                query_vector = EmbeddingService.embed(topic)
                knn_clause = {
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": k,
                    "num_candidates": max(k * 10, 100)
                }
                if filter_clauses:
                    knn_clause["filter"] = {"bool": {"must": filter_clauses}}

                return self.es.search(
                    index=settings.ELASTICSEARCH_INDEX,
                    body={"knn": knn_clause, "size": k, "track_total_hits": True}
                )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                return None

        # Run parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            bm25_future = executor.submit(run_bm25)
            vector_future = executor.submit(run_vector)

            bm25_result = bm25_future.result()
            vector_result = vector_future.result()

        bm25_ids = [hit["_id"] for hit in bm25_result["hits"]["hits"]]
        total_matched = bm25_result["hits"]["total"]["value"]

        vector_ids = []
        if vector_result:
            vector_ids = [hit["_id"] for hit in vector_result.get("hits", {}).get("hits", [])]
            # Lấy max của BM25 và vector total
            vector_total = vector_result.get("hits", {}).get("total", {}).get("value", 0)
            total_matched = max(total_matched, vector_total)

        # RRF
        merged_ids, scores = self._rrf(bm25_ids, vector_ids, k=60)

        return merged_ids[:50], scores, total_matched

    def _rrf(
        self,
        bm25_ids: List[str],
        vector_ids: List[str],
        k: int = 60
    ) -> Tuple[List[str], Dict[str, float]]:
        """Reciprocal Rank Fusion."""
        scores = {}

        for rank, doc_id in enumerate(bm25_ids, 1):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)

        for rank, doc_id in enumerate(vector_ids, 1):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)

        # Sort by score desc
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return sorted_ids, scores

    def _build_filter_clauses(self, filters: Dict[str, Any]) -> List[Dict]:
        """Build ES filter clauses."""
        clauses = []

        # Location (locations array, not nested)
        if "location" in filters and "include" in filters["location"]:
            codes = filters["location"]["include"]
            if codes:
                clauses.append({"terms": {"locations.provCode": codes}})

        # Year (use bidCloseDate instead of publishedDate which is always None)
        if "year" in filters and filters["year"]:
            year = filters["year"]
            clauses.append({
                "range": {
                    "bidCloseDate": {
                        "gte": f"{year}-01-01",
                        "lte": f"{year}-12-31"
                    }
                }
            })

        # Price
        if "price_min" in filters and filters["price_min"]:
            clauses.append({"range": {"bidValue": {"gte": filters["price_min"]}}})

        if "price_max" in filters and filters["price_max"]:
            clauses.append({"range": {"bidValue": {"lte": filters["price_max"]}}})

        # Status
        if "status" in filters and filters["status"] == "open":
            today = datetime.now().strftime("%Y-%m-%d")
            clauses.append({"range": {"bidCloseDate": {"gte": today}}})

        return clauses


# ============================================================================
# MAIN SERVICE
# ============================================================================

class SearchServiceV4:
    """Service chính V4 - orchestrate 8 bước."""

    def __init__(self):
        # Setup Elasticsearch with verify_certs=False
        self.es = Elasticsearch(
            [settings.ELASTICSEARCH_URL],
            basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
            verify_certs=False,
            ssl_show_warn=False
        )

        # Setup LLM client based on provider
        if settings.LLM_PROVIDER == "deepseek":
            from openai import AsyncOpenAI
            self.llm_client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_ENDPOINT
            )
        elif settings.LLM_PROVIDER == "anthropic":
            self.llm_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            from openai import AsyncOpenAI
            self.llm_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        self.location = LocationService()
        self.analyzer = IntentAnalyzer(self.llm_client, self.location)
        self.executor = SearchExecutor(self.es)

        # Warm-up embedding model
        from app.services.embedding import EmbeddingService
        EmbeddingService.embed("warm-up")

    async def search(
        self,
        query: str,
        session_id: str,
        session: Optional[Dict] = None
    ) -> SearchResult:
        """Entry point - full 8-step flow."""
        start = time.time()
        timings = {}  # ponytail: profile timing cho từng bước

        # STEP 1: Fast path
        t1 = time.time()
        bid_code = FastPath.extract_bid_code(query)
        if bid_code:
            bids = self.executor.search_by_code(bid_code)
            timings["fastpath"] = (time.time() - t1) * 1000
            logger.info(f"[V4] FastPath: {timings['fastpath']:.0f}ms")
            return SearchResult(
                bids=bids,
                total=len(bids),
                took_ms=(time.time() - start) * 1000,
                filters_applied={"bid_code": bid_code},
                relaxed_filters=[],
                clarification=None,
                aggregation=None,
                session_id=session_id,
                method="fastpath",
                timings=timings
            )

        if FastPath.is_pure_greeting(query):
            timings["fastpath"] = (time.time() - t1) * 1000
            logger.info(f"[V4] Greeting: {timings['fastpath']:.0f}ms")
            return SearchResult(
                bids=[],
                total=0,
                took_ms=(time.time() - start) * 1000,
                filters_applied={},
                relaxed_filters=[],
                clarification="Xin chào! Tôi có thể giúp bạn tìm kiếm gói thầu.",
                aggregation=None,
                session_id=session_id,
                method="greeting",
                timings=timings
            )
        timings["fastpath"] = (time.time() - t1) * 1000

        # STEP 2: Pagination
        t2 = time.time()
        if PaginationHandler.is_pagination(query, session):
            limit = PaginationHandler.extract_limit(query)
            offset = session.get("offset", 0)
            ranked_ids = session.get("ranked_ids", [])

            next_ids = ranked_ids[offset:offset + limit]
            bids = self._fetch_by_ids(next_ids)
            session["offset"] = offset + limit

            timings["pagination"] = (time.time() - t2) * 1000
            logger.info(f"[V4] Pagination: {timings['pagination']:.0f}ms")
            return SearchResult(
                bids=bids,
                total=len(ranked_ids),
                took_ms=(time.time() - start) * 1000,
                filters_applied=session.get("filters", {}),
                relaxed_filters=[],
                clarification=None,
                aggregation=None,
                session_id=session_id,
                method="pagination",
                timings=timings
            )
        timings["pagination"] = (time.time() - t2) * 1000

        # STEP 3: LLM Analysis (timeout 4s, fallback to hybrid search on timeout)
        t3 = time.time()
        today = datetime.now().strftime("%Y-%m-%d")
        analysis = await self.analyzer.analyze(query, session, today, timeout_ms=4000)
        timings["llm_analysis"] = (time.time() - t3) * 1000

        if analysis.fallback_to_v3:
            # V3 fallback (placeholder)
            pass

        # STEP 4: Execution
        t4 = time.time()
        merged_filters, topic = self.executor.merge_state(analysis, session)
        method = self.executor.choose_method(analysis, bid_code, topic)

        if method == "filter_only":
            bids, total = self.executor.search_filter_only(
                merged_filters,
                analysis.sort
            )
            ranked_ids = []
            timings["search"] = (time.time() - t4) * 1000

        elif method == "hybrid":
            ranked_ids, scores, total = self.executor.search_hybrid(topic, merged_filters)
            scores_map = scores
            timings["search"] = (time.time() - t4) * 1000

            # STEP 5: Conditional rerank
            t5 = time.time()
            if total > 5 and scores_map:
                now = datetime.now()
                docs_for_rerank = self._fetch_by_ids(ranked_ids[:50])
                doc_map = {d["_id"]: d for d in docs_for_rerank}

                final_scores = {}
                for doc_id in ranked_ids[:50]:
                    if doc_id not in doc_map:
                        continue

                    doc = doc_map[doc_id]
                    base_score = scores_map.get(doc_id, 0)

                    recency_boost = 0
                    if doc.get("bidCloseDate"):
                        try:
                            close_date = datetime.fromisoformat(doc["bidCloseDate"].replace("Z", "+00:00"))
                            days_until = (close_date - now).days
                            if 0 < days_until <= 30:
                                recency_boost = 0.2 * (1 - days_until / 30)
                        except:
                            pass

                    value_boost = 0
                    bid_value = doc.get("bidValue")
                    if bid_value and bid_value > 0:
                        value_boost = min(0.1, (bid_value / 1_000_000_000) * 0.05)

                    final_scores[doc_id] = base_score * (1 + recency_boost + value_boost)

                ranked_ids = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
                if final_scores:
                    max_score = max(final_scores.values())
                    threshold = max_score * 0.3
                    ranked_ids = [doc_id for doc_id in ranked_ids if final_scores.get(doc_id, 0) >= threshold]

                timings["rerank"] = (time.time() - t5) * 1000
            else:
                timings["rerank"] = 0

            t6 = time.time()
            bids = self._fetch_by_ids(ranked_ids[:10])
            timings["fetch_final"] = (time.time() - t6) * 1000

        else:
            bids, total = [], 0
            ranked_ids = []
            scores_map = {}

        # STEP 6: Fallback / Clarification - auto-relax filters
        clarification = None
        relaxed_filters = []
        if total == 0 and method != "by_code":
            # Try relaxing filters in priority order
            relax_order = ["price_min", "price_max", "year", "location"]
            for filter_key in relax_order:
                if filter_key in ["price_min", "price_max"]:
                    if merged_filters.get("price_min") or merged_filters.get("price_max"):
                        # Retry without price filter
                        relaxed = {k: v for k, v in merged_filters.items() if k not in ["price_min", "price_max"]}
                        if topic:
                            ranked_ids, scores = self.executor.search_hybrid(topic, relaxed)
                            if len(ranked_ids) > 0:
                                bids = self._fetch_by_ids(ranked_ids[:10])
                                total = len(ranked_ids)
                                relaxed_filters.append("price")
                                clarification = f"Không tìm thấy thầu với giá yêu cầu. Đã bỏ lọc giá → tìm được {total} thầu."
                                break
                elif filter_key == "year" and merged_filters.get("year"):
                    # Retry without year
                    relaxed = {k: v for k, v in merged_filters.items() if k != "year"}
                    if topic:
                        ranked_ids, scores = self.executor.search_hybrid(topic, relaxed)
                    else:
                        bids, total_new = self.executor.search_filter_only(relaxed, analysis.sort)
                        total = total_new
                        ranked_ids = []
                    if (topic and len(ranked_ids) > 0) or (not topic and total > 0):
                        if topic:
                            bids = self._fetch_by_ids(ranked_ids[:10])
                            total = len(ranked_ids)
                        relaxed_filters.append("year")
                        clarification = f"Không tìm thấy thầu năm {merged_filters['year']}. Đã bỏ lọc năm → tìm được {total} thầu."
                        break

            # If still zero, suggest keywords
            if total == 0:
                clarification = "Không tìm thấy thầu phù hợp. Thử từ khóa khác hoặc bỏ bớt điều kiện lọc?"

        # STEP 7: Aggregations & Response generation
        response_text = None
        aggregation = None

        if analysis.output_mode == "aggregate" and total > 0:
            # Aggregations: location, year, price range
            try:
                agg_query = {
                    "query": {"bool": {"filter": self.executor._build_filter_clauses(merged_filters)}},
                    "size": 0,
                    "aggs": {
                        "by_location": {
                            "terms": {"field": "locations.provName.keyword", "size": 10}
                        },
                        "by_year": {
                            "date_histogram": {
                                "field": "bidCloseDate",
                                "calendar_interval": "year",
                                "format": "yyyy"
                            }
                        },
                        "price_stats": {
                            "stats": {"field": "bidValue"}
                        }
                    }
                }

                agg_result = self.es.search(index=settings.ELASTICSEARCH_INDEX, body=agg_query)
                aggs = agg_result.get("aggregations", {})

                aggregation = {
                    "total": total,
                    "by_location": {
                        b["key"]: b["doc_count"]
                        for b in aggs.get("by_location", {}).get("buckets", [])[:5]
                    },
                    "by_year": {
                        b["key_as_string"]: b["doc_count"]
                        for b in aggs.get("by_year", {}).get("buckets", [])
                    },
                    "price_range": aggs.get("price_stats", {})
                }

                top_loc = list(aggregation["by_location"].keys())[0] if aggregation["by_location"] else "N/A"
                response_text = f"Tìm được {total} thầu. Nhiều nhất tại: {top_loc}."

            except Exception as e:
                logger.warning(f"Aggregation failed: {e}")
                response_text = f"Tìm được {total} thầu."

        elif analysis.output_mode == "compare" and total > 0:
            response_text = f"Tìm được {total} thầu để so sánh."

        elif analysis.output_mode == "chat":
            if total > 0:
                response_text = "Tìm được một số thầu. Bạn muốn biết gì?"
            else:
                response_text = clarification or "Chưa tìm thấy thầu nào."

        # STEP 8: Session update and logging
        if session:
            session.update({
                "filters": merged_filters,
                "topic": topic,
                "ranked_ids": ranked_ids[:50],
                "offset": 10,
                "total_matched": total,
                "output_mode": analysis.output_mode
            })

        took_ms = int((time.time() - start) * 1000)

        # Log timing breakdown
        print(
            f"[V4] {session_id}: {took_ms}ms total | "
            f"LLM: {timings.get('llm_analysis', 0):.0f}ms | "
            f"Search: {timings.get('search', 0):.0f}ms | "
            f"Rerank: {timings.get('rerank', 0):.0f}ms | "
            f"Fetch: {timings.get('fetch_final', 0):.0f}ms | "
            f"method={method} | total={total} | bids={len(bids)}"
        )

        return SearchResult(
            bids=bids,
            total=total,
            took_ms=took_ms,
            filters_applied=merged_filters,
            relaxed_filters=relaxed_filters,
            clarification=clarification or response_text,
            aggregation=aggregation,
            session_id=session_id,
            method=method,
            timings=timings,
            _debug_intent={
                "scope": analysis.scope,
                "output_mode": analysis.output_mode,
                "topic": topic,
                "filters": analysis.filters,
                "method": method
            }
        )

    def _fetch_by_ids(self, doc_ids: List[str]) -> List[Dict]:
        """Fetch documents by IDs, include _id field."""
        if not doc_ids:
            return []

        result = self.es.mget(
            index=settings.ELASTICSEARCH_INDEX,
            body={"ids": doc_ids}
        )

        docs = []
        for doc in result["docs"]:
            if doc.get("found"):
                d = doc["_source"]
                d["_id"] = doc["_id"]
                docs.append(d)
        return docs
