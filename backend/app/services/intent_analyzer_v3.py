"""Intent analyzer v3 - Fix 5 lỗi chính + 4 lỗi mapping (deadline, bidCode, regex mã, location multi-code)."""
import re
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from app.services.deepseek_client import DeepSeekClient
from app.services.location_service import LocationService

@dataclass
class QueryAnalysis:
    intent: str
    filters: Dict[str, Any]
    residual: str
    method: str
    llm_calls: List[str] = field(default_factory=list)
    code: Optional[str] = None  # bidNo (mã gói thầu)

class IntentAnalyzerV3:
    """Fix 5 lỗi ban đầu + 4 lỗi mapping index thật."""

    STOPWORDS = {
        "tìm", "cho", "tôi", "mình", "giúp", "danh sách", "các", "gói thầu",
        "gói", "thầu", "dự án", "cho xem", "xem", "liệt kê", "hãy", "em", "anh", "chị",
        "ở", "tại", "năm", "của",
        # ASCII versions
        "goi", "thau", "du", "an", "o", "tai", "nam", "cua"
    }

    # FIX MAPPING #3: Regex mã gói thầu thật (BP + 10 số), không phải DT-2024-123
    CODE_PATTERNS = [
        r'\b[A-Z]{2}\d{10}\b',  # BP2200225863
    ]

    @classmethod
    async def analyze(cls, query: str, session_context: Optional[Dict] = None) -> QueryAnalysis:
        """3 bước: intent → filter → method. Fix lỗi 1-5."""
        llm_calls = []
        intent = cls._detect_intent(query, session_context)

        if intent == "casual":
            return QueryAnalysis("casual", {}, query, "none", llm_calls)

        # FIX LỖI 2: Phát hiện mã TRƯỚC khi extract filters
        code = cls._extract_code(query)
        masked_query = query.replace(code, "<CODE>") if code else query

        # FIX LỖI 4: Aggregation/continuation đi qua bước filter
        filters, residual = cls._extract_filters_and_residual(masked_query)

        # FIX LỖI 3: Làm sạch residual với stopwords
        residual = cls._clean_residual(residual)

        # FIX LỖI 1: Chỉ gọi LLM khi có tín hiệu cụ thể
        signals = cls._detect_llm_signals(query, filters, residual)
        if signals:
            llm_result = await cls._refine_with_llm(query, filters, residual, signals)
            if llm_result:
                filters = llm_result.get("filters", filters)
                residual = llm_result.get("residual", residual)
                llm_calls.append(f"filter:{signals}")

        if intent == "aggregation":
            return QueryAnalysis("aggregation", filters, residual, "aggregation", llm_calls)

        if intent == "continuation" and session_context:
            filters = {**session_context.get("filters", {}), **filters}

        method = cls._choose_method(residual, code)
        return QueryAnalysis(intent, filters, residual, method, llm_calls, code)

    @classmethod
    def _detect_intent(cls, query: str, session_context: Optional[Dict]) -> str:
        q = query.lower()
        if any(x in q for x in ["xin chào", "hello", "cảm ơn", "thank"]):
            return "casual"
        if any(x in q for x in ["top", "bao nhiêu", "thống kê", "tổng"]):
            return "aggregation"
        if session_context and any(x in q for x in ["tiếp", "thêm", "còn"]):
            return "continuation"
        return "search"

    @classmethod
    def _extract_code(cls, query: str) -> Optional[str]:
        for pattern in cls.CODE_PATTERNS:
            m = re.search(pattern, query)
            if m:
                return m.group(0)
        return None

    @classmethod
    def _extract_filters_and_residual(cls, query: str) -> Tuple[Dict[str, Any], str]:
        filters = {}
        residual = query

        # Location - FIX MAPPING #4: match tất cả codes (101, 01, 213, 15 cho Hà Nội)
        provinces = LocationService._load_provinces()
        for prov_name, prov_data in provinces.items():
            # Check tên chính
            pattern = re.compile(rf'\b{re.escape(prov_name)}\b', re.IGNORECASE)
            if pattern.search(residual):
                filters["location"] = prov_data["codes"]  # list codes thay vì 1 code
                residual = pattern.sub(' <LOC> ', residual)
                break
            # Check aliases
            for alias in prov_data.get("aliases", []):
                pattern = re.compile(rf'\b{re.escape(alias)}\b', re.IGNORECASE)
                if pattern.search(residual):
                    filters["location"] = prov_data["codes"]
                    residual = pattern.sub(' <LOC> ', residual)
                    break
            if "location" in filters:
                break

        # Year
        year_match = re.search(r'\b(20\d{2})\b', residual)
        if year_match:
            filters["year"] = int(year_match.group(1))
            residual = residual[:year_match.start()] + ' <YEAR> ' + residual[year_match.end():]

        # Price
        price_match = re.search(r'(\d+)\s*(?:ty|trieu|tr)\b', residual, re.IGNORECASE)
        if price_match:
            val = int(price_match.group(1))
            price_text = price_match.group(0).lower()
            if "ty" in price_text:
                val *= 1_000_000_000
            else:
                val *= 1_000_000

            if any(x in query.lower() for x in ["duoi", "nho hon", "toi da"]):
                filters["max_price"] = val
            elif any(x in query.lower() for x in ["tren", "lon hon", "toi thieu"]):
                filters["min_price"] = val
            else:
                filters["max_price"] = val
            residual = residual[:price_match.start()] + ' <PRICE> ' + residual[price_match.end():]

        # bidForm
        bid_forms = ["dau thau rong rai", "chi dinh thau", "mua sam truc tiep", "chao hang canh tranh"]
        for bf in bid_forms:
            pattern = re.compile(rf'\b{re.escape(bf)}\b', re.IGNORECASE)
            if pattern.search(residual):
                filters["bidForm"] = bf.replace(' ', ' ').title()
                residual = pattern.sub(' <FORM> ', residual)
                break

        # Xóa masks và normalize spaces
        residual = re.sub(r'<\w+>', ' ', residual)
        residual = re.sub(r'\s+', ' ', residual).strip()

        return filters, residual

    @classmethod
    def _clean_residual(cls, residual: str) -> str:
        words = residual.lower().split()
        words = [w for w in words if w not in cls.STOPWORDS]
        return " ".join(words).strip()

    @classmethod
    def _detect_llm_signals(cls, query: str, filters: Dict, residual: str) -> Optional[str]:
        q = query.lower()

        # Phủ định
        if any(x in q for x in ["không phải", "ngoài", "trừ", "không bao gồm"]):
            return "negation"

        # So sánh
        if "so sánh" in q and " và " in q:
            return "comparison"

        # Thời gian tương đối
        if any(x in q for x in ["sắp", "gần đây", "tháng này", "tuần này"]):
            return "relative_time"

        # Đại từ
        if any(x in q for x in ["nó", "cái này", "cái đó", "gói đó"]):
            return "pronoun"

        # Location + phủ định
        if "location" in filters and any(x in q for x in ["không phải", "ngoài"]):
            return "location_negation"

        return None

    @classmethod
    async def _refine_with_llm(cls, query: str, filters: Dict, residual: str, signal: str) -> Optional[Dict]:
        prompt = f"""Phân tích câu hỏi có tín hiệu phức tạp ({signal}):
"{query}"

Filters hiện tại: {filters}
Residual: {residual}

Trả về JSON với filters và residual đã chỉnh sửa (nếu cần)."""

        try:
            response = await DeepSeekClient.chat(
                messages=[{"role": "user", "content": prompt}],
                response_format="json",
                temperature=0.1,
                max_tokens=300
            )
            return response
        except:
            return None

    @classmethod
    def _choose_method(cls, residual: str, code: Optional[str]) -> str:
        if code:
            return "bm25_code"
        if not residual:
            return "metadata_only"
        return "hybrid"
