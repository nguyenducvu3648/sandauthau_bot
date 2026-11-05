"""Intent analysis cho user queries."""
import json
import re
from typing import Dict, Any, Optional
from app.services.deepseek_client import DeepSeekClient


class IntentAnalyzer:
    """Phân tích intent và extract metadata từ query."""

    SYSTEM_PROMPT = """Bạn là chuyên gia phân tích câu hỏi về đấu thầu/thầu Việt Nam.

Nhiệm vụ: Phân tích câu hỏi user và trả về JSON với format:
{
  "intent": "casual" hoặc "search",
  "filters": {
    "year": "2024",
    "location": "Hà Nội",
    "bidForm": "Đấu thầu rộng rãi"
  },
  "search_methods": ["bm25", "vector", "hybrid", "filter"]
}

Rules:
1. Intent "casual" nếu:
   - Chào hỏi: "xin chào", "hello", "hi"
   - Cảm ơn: "cảm ơn", "thanks"
   - Hỏi về bot: "bạn là ai", "bạn làm được gì"

2. Intent "search" nếu hỏi về gói thầu/đấu thầu

3. Filters (chỉ extract nếu có rõ ràng trong query):
   - year: năm (VD: "2024", "năm 2023")
   - location: tỉnh/thành phố (VD: "Hà Nội", "TP.HCM", "Đà Nẵng", "Thủ Đức")
   - bidForm: loại hình (VD: "Đấu thầu rộng rãi", "Chỉ định thầu", "Mua sắm trực tiếp")

4. Search methods:
   - Chỉ có filters (không có keyword) → ["filter"]
   - Có mã gói thầu (DT-123, số hiệu) → thêm "bm25"
   - Query dài >10 từ, phức tạp → thêm "hybrid"
   - Query ngắn, đơn giản → "vector"
   - Có thể trả nhiều methods

Trả ONLY JSON, không giải thích."""

    PROVINCES = [
        "Hà Nội", "TP.HCM", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
        "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu",
        "Bắc Ninh", "Bến Tre", "Bình Dương", "Bình Định", "Bình Phước",
        "Bình Thuận", "Cà Mau", "Cao Bằng", "Đắk Lắk", "Đắk Nông",
        "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Giang",
        "Hà Nam", "Hà Tĩnh", "Hải Dương", "Hậu Giang", "Hòa Bình",
        "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu",
        "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An", "Nam Định",
        "Nghệ An", "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên",
        "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị",
        "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên",
        "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh", "Tuyên Quang",
        "Vĩnh Long", "Vĩnh Phúc", "Yên Bái", "Thủ Đức"
    ]

    BID_FORMS = [
        "Đấu thầu rộng rãi", "Chỉ định thầu", "Mua sắm trực tiếp",
        "Chào hàng cạnh tranh", "Tự thực hiện"
    ]

    @classmethod
    async def analyze(cls, query: str) -> Dict[str, Any]:
        """
        Phân tích query và trả intent + metadata.

        Returns:
            {
                "intent": "casual" | "search" | "aggregation",
                "filters": {...},
                "search_methods": [...]
            }
        """
        # Quick check: casual queries
        if cls._is_casual_quick(query):
            return {
                "intent": "casual",
                "filters": {},
                "search_methods": []
            }

        # Check aggregation intent (thống kê, đếm, top N)
        if cls._is_aggregation(query):
            filters = cls._extract_filters_regex(query)
            return {
                "intent": "aggregation",
                "filters": filters,
                "search_methods": ["aggregation"]
            }

        # Try rule-based extraction first
        filters = cls._extract_filters_regex(query)
        methods = cls._guess_methods_regex(query, filters)

        # Nếu rõ ràng → skip LLM
        if methods and (filters or len(query.split()) <= 5):
            return {
                "intent": "search",
                "filters": filters,
                "search_methods": methods
            }

        # Fallback: gọi LLM cho queries phức tạp
        return await cls._analyze_with_llm(query)

    @classmethod
    def _is_casual_quick(cls, query: str) -> bool:
        """Quick regex check cho casual queries - chỉ match pure greetings."""
        q = query.lower().strip()

        # Chỉ match pure greetings (không có từ khóa search)
        pure_casual_patterns = [
            r'^(xin )?chào\s*$',
            r'^hi\s*$',
            r'^hello\s*$',
            r'^(cảm ơn|thanks|thank you)\s*$',
            r'^bạn là ai\??$',
            r'^bạn làm (được )?gì\??$',
        ]

        # Nếu match pure pattern → casual
        if any(re.search(p, q) for p in pure_casual_patterns):
            return True

        # Mixed queries như "Xin chào, tìm giúp tôi..." → search (strip greeting)
        return False

    @classmethod
    def _is_aggregation(cls, query: str) -> bool:
        """Detect aggregation/statistics queries."""
        q = query.lower()
        agg_patterns = [
            r'bao nhiêu',
            r'số lượng',
            r'đếm',
            r'tổng',
            r'trung bình',
            r'cao nhất',
            r'thấp nhất',
            r'top \d+',
            r'nhiều nhất',
            r'ít nhất',
            r'tỉnh nào',
            r'thành phố nào',
        ]
        return any(re.search(p, q) for p in agg_patterns)

    @classmethod
    def _extract_filters_regex(cls, query: str) -> Dict[str, Any]:
        """Extract filters bằng regex."""
        filters = {}

        # Year
        if match := re.search(r'năm\s+(\d{4})|(\d{4})', query):
            year = match.group(1) or match.group(2)
            filters["year"] = int(year)

        # Location
        q_lower = query.lower()
        for province in cls.PROVINCES:
            if province.lower() in q_lower:
                filters["location"] = province
                break

        # Bid form
        for form in cls.BID_FORMS:
            if form.lower() in q_lower:
                filters["bidForm"] = form
                break

        # Price filters (giá trị gói thầu)
        # "dưới 5 tỷ" → max_price: 5000000000
        # "trên 10 triệu" → min_price: 10000000
        # "từ 2 tỷ đến 10 tỷ" → min_price: 2000000000, max_price: 10000000000
        if match := re.search(r'dưới\s+(\d+)\s*(tỷ|triệu)', query):
            value = float(match.group(1))
            unit = match.group(2)
            filters["max_price"] = int(value * (1_000_000_000 if unit == "tỷ" else 1_000_000))

        if match := re.search(r'trên\s+(\d+)\s*(tỷ|triệu)', query):
            value = float(match.group(1))
            unit = match.group(2)
            filters["min_price"] = int(value * (1_000_000_000 if unit == "tỷ" else 1_000_000))

        if match := re.search(r'từ\s+(\d+)\s*(tỷ|triệu)\s+đến\s+(\d+)\s*(tỷ|triệu)', query):
            min_val = float(match.group(1))
            min_unit = match.group(2)
            max_val = float(match.group(3))
            max_unit = match.group(4)
            filters["min_price"] = int(min_val * (1_000_000_000 if min_unit == "tỷ" else 1_000_000))
            filters["max_price"] = int(max_val * (1_000_000_000 if max_unit == "tỷ" else 1_000_000))

        return filters

    @classmethod
    def _guess_methods_regex(cls, query: str, filters: Dict) -> list[str]:
        """Đoán search methods bằng rules."""
        words = query.split()

        # 1. Có mã gói thầu → BM25 (ưu tiên cao nhất)
        has_code = bool(re.search(r'\b[A-Z]{2,}-?\d+', query))
        if has_code:
            return ["bm25"]

        # 2. Có filters rõ ràng (location, year, price, bidForm) → filter + vector
        # Không cần hybrid vì đã có filter cụ thể
        if filters:
            # Đếm meaningful keywords (bỏ qua location names, years, bidForm names)
            keywords = [w for w in words if len(w) > 2]

            # Nếu ít keyword (≤3) → chủ yếu dựa vào filter
            if len(keywords) <= 3:
                return ["filter"]

            # Có cả keyword và filter → vector + filter
            return ["vector"]

        # 3. Query dài (≥15 từ) KHÔNG có filter → hybrid
        # VD: "gói thầu xây dựng hạ tầng giao thông kết nối..."
        if len(words) >= 15:
            return ["hybrid"]

        # 4. Query ngắn, không có filter → vector
        # VD: "xây dựng cầu", "mua sắm thiết bị y tế"
        return ["vector"]

    @classmethod
    async def _analyze_with_llm(cls, query: str) -> Dict[str, Any]:
        """Fallback: phân tích bằng DeepSeek."""
        messages = [
            {"role": "system", "content": cls.SYSTEM_PROMPT},
            {"role": "user", "content": f'Phân tích: "{query}"'}
        ]

        try:
            response = await DeepSeekClient.chat(
                messages=messages,
                response_format="json"
            )
            result = json.loads(response)

            # Validate structure
            if "intent" not in result:
                result["intent"] = "search"
            if "filters" not in result:
                result["filters"] = {}
            if "search_methods" not in result:
                result["search_methods"] = ["vector"]

            return result

        except Exception as e:
            # Fallback nếu LLM fail
            return {
                "intent": "search",
                "filters": cls._extract_filters_regex(query),
                "search_methods": ["vector"]
            }
