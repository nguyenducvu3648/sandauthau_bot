"""Intent analyzer v2 - 3-step design."""
import re
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.deepseek_client import DeepSeekClient

@dataclass
class QueryAnalysis:
    intent: str  # casual/code_lookup/search/aggregation/continuation
    filters: Dict[str, Any]
    residual: str  # query sau khi bỏ filter
    method: str  # bm25_code/metadata_only/hybrid
    needs_llm: bool = False  # tín hiệu phức tạp


class IntentAnalyzerV2:
    """Phân tích query theo 3 bước rõ ràng."""

    # Danh sách tỉnh/thành phố (dùng cho validation)
    PROVINCES = {
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
    }

    BID_FORMS = {
        "Đấu thầu rộng rãi", "Chỉ định thầu", "Mua sắm trực tiếp",
        "Chào hàng cạnh tranh", "Tự thực hiện"
    }

    # Mẫu mã gói thầu thật (prefix validation)
    CODE_PATTERNS = [
        r'\b(DT|DTXD|MSC|CHHC)-\d{4}-\d+\b',  # DT-2024-123, DTXD-2024-45
        r'\b\d{8}-\w+-\d+\b',  # 20241015-ABC-123
    ]

    @classmethod
    async def analyze(cls, query: str, session_context: Optional[Dict] = None) -> QueryAnalysis:
        """
        Phân tích query theo 3 bước.

        Args:
            query: câu hỏi user
            session_context: context từ câu trước (để xử lý continuation)
        """
        # BƯỚC 1: Intent với confidence check
        intent_result = cls._detect_intent_with_confidence(query, session_context)
        intent = intent_result['intent']
        confidence = intent_result['confidence']

        # Nếu confidence < 97% → dùng LLM
        if confidence < 0.97:
            try:
                llm_intent = await cls._analyze_intent_with_llm(query, session_context)
                if llm_intent and llm_intent.get('confidence', 0) > confidence:
                    intent = llm_intent['intent']
            except Exception:
                # LLM fail → giữ regex result
                pass

        if intent == "casual":
            return QueryAnalysis(
                intent="casual",
                filters={},
                residual=query,
                method="none"
            )

        if intent == "aggregation":
            filters, _ = cls._extract_filters_and_residual(query)
            return QueryAnalysis(
                intent="aggregation",
                filters=filters,
                residual="",
                method="aggregation"
            )

        # BƯỚC 2: Extract filters + residual
        filters, residual = cls._extract_filters_and_residual(query)

        # BƯỚC 3: Chọn method
        code = cls._extract_verified_code(query)
        needs_llm = cls._needs_llm(query, residual)

        # Nếu phức tạp → gọi LLM để refine filters
        if needs_llm:
            llm_result = await cls._analyze_with_llm(query, filters, residual)
            if llm_result:
                filters = llm_result.get("filters", filters)
                residual = llm_result.get("residual", residual)

        method = cls._choose_method(residual, code, filters)

        return QueryAnalysis(
            intent=intent,
            filters=filters,
            residual=residual,
            method=method,
            needs_llm=needs_llm
        )

    @classmethod
    def _detect_intent_with_confidence(cls, query: str, session_context: Optional[Dict]) -> Dict[str, Any]:
        """
        Bước 1: Phát hiện intent với confidence score.

        Returns:
            {"intent": "casual|search|...", "confidence": 0.0-1.0}
        """
        q = query.lower().strip()

        # 1. Casual (pure greetings)
        if cls._is_pure_casual(q):
            # Nếu có thêm từ → confidence thấp
            words = q.split()
            if len(words) <= 2:  # "xin chào", "cảm ơn"
                return {"intent": "casual", "confidence": 0.99}
            else:  # "cảm ơn bạn", "xin chào bạn"
                return {"intent": "casual", "confidence": 0.85}

        # 2. Continuation
        if session_context and cls._is_continuation(q):
            return {"intent": "continuation", "confidence": 0.95}

        # 3. Aggregation
        if cls._is_aggregation(q):
            return {"intent": "aggregation", "confidence": 0.97}

        # 4. Mặc định: search
        return {"intent": "search", "confidence": 0.90}

    @classmethod
    async def _analyze_intent_with_llm(
        cls,
        query: str,
        session_context: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        LLM fallback cho intent detection.

        Returns:
            {"intent": "...", "confidence": 0.95, "reasoning": "..."} hoặc None nếu fail
        """
        system_prompt = """Bạn là chuyên gia phân tích câu hỏi về đấu thầu Việt Nam.

Phân loại intent thành 1 trong 4 loại:

1. **casual**: Chào hỏi, cảm ơn, hỏi về bot
   - VD: "xin chào", "cảm ơn bạn", "bạn là ai", "hi", "hello"
   - Có thêm từ "bạn", "ạ" vẫn là casual

2. **search**: Tìm kiếm gói thầu cụ thể
   - VD: "xây dựng cầu Hà Nội", "DT-2024-123", "gói thầu năm 2024"
   - Kể cả có filter location/year/price vẫn là search

3. **aggregation**: Thống kê, đếm, top N
   - VD: "bao nhiêu gói thầu", "top 10 giá cao nhất", "tỉnh nào nhiều nhất"
   - Keyword: bao nhiêu, số lượng, đếm, tổng, top, nhiều nhất, ít nhất

4. **continuation**: Tiếp nối câu trước
   - VD: "còn gói nào khác", "chi tiết hơn", "thêm nữa"
   - Keyword: còn, nó, gói đó, cái này, thêm

Trả về JSON:
{
  "intent": "casual|search|aggregation|continuation",
  "confidence": 0.95,
  "reasoning": "ngắn gọn tại sao"
}

QUAN TRỌNG:
- "cảm ơn bạn nhé", "xin chào bạn" → casual (có thêm từ vẫn OK)
- "Hà Nội năm 2024" → search (không hỏi số lượng)
- "so sánh X và Y" → search (tìm để so sánh)"""

        user_prompt = f'Câu hỏi: "{query}"'

        if session_context:
            user_prompt += f'\n\nContext câu trước: {json.dumps(session_context, ensure_ascii=False)}'

        try:
            response = await DeepSeekClient.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json",
                temperature=0.1,
                max_tokens=150
            )

            result = json.loads(response)

            # Validate structure
            if "intent" not in result:
                return None
            if "confidence" not in result:
                result["confidence"] = 0.90

            return result

        except Exception as e:
            # LLM fail → fallback regex
            return None

    @classmethod
    def _is_pure_casual(cls, q: str) -> bool:
        """Chỉ match pure greetings."""
        patterns = [
            r'^(xin )?chào\s*$',
            r'^hi\s*$',
            r'^hello\s*$',
            r'^(cảm ơn|thanks|thank you)\s*$',
            r'^bạn là ai\??$',
            r'^bạn làm (được )?gì\??$',
        ]
        return any(re.search(p, q) for p in patterns)

    @classmethod
    def _is_continuation(cls, q: str) -> bool:
        """Phát hiện câu nối tiếp."""
        continuation_words = ["còn", "nó", "gói đó", "cái này", "thêm"]
        return any(word in q for word in continuation_words)

    @classmethod
    def _is_aggregation(cls, q: str) -> bool:
        """Phát hiện aggregation."""
        patterns = [
            r'bao nhiêu', r'số lượng', r'đếm', r'tổng',
            r'trung bình', r'cao nhất', r'thấp nhất',
            r'top \d+', r'nhiều nhất', r'ít nhất',
            r'tỉnh nào', r'thành phố nào',
        ]
        return any(re.search(p, q) for p in patterns)

    @classmethod
    def _extract_filters_and_residual(cls, query: str) -> Tuple[Dict[str, Any], str]:
        """
        Bước 2: Extract filters và tách residual.

        Returns:
            (filters, residual_query)
        """
        filters = {}
        residual = query
        matched_spans = []  # [(start, end, text)] để loại bỏ

        # Year
        if match := re.search(r'năm\s+(\d{4})', query):
            filters["year"] = int(match.group(1))
            matched_spans.append((match.start(), match.end()))

        # Location (validate với danh sách)
        q_lower = query.lower()
        for province in cls.PROVINCES:
            if province.lower() in q_lower:
                filters["location"] = province
                # Tìm vị trí chính xác để loại bỏ
                idx = q_lower.index(province.lower())
                matched_spans.append((idx, idx + len(province)))
                break

        # Bid form
        for form in cls.BID_FORMS:
            if form.lower() in q_lower:
                filters["bidForm"] = form
                idx = q_lower.index(form.lower())
                matched_spans.append((idx, idx + len(form)))
                break

        # Price ranges
        if match := re.search(r'từ\s+(\d+)\s*(tỷ|triệu)\s+đến\s+(\d+)\s*(tỷ|triệu)', query):
            min_val = float(match.group(1))
            min_unit = match.group(2)
            max_val = float(match.group(3))
            max_unit = match.group(4)
            filters["min_price"] = int(min_val * (1_000_000_000 if min_unit == "tỷ" else 1_000_000))
            filters["max_price"] = int(max_val * (1_000_000_000 if max_unit == "tỷ" else 1_000_000))
            matched_spans.append((match.start(), match.end()))
        elif match := re.search(r'dưới\s+(\d+)\s*(tỷ|triệu)', query):
            value = float(match.group(1))
            unit = match.group(2)
            filters["max_price"] = int(value * (1_000_000_000 if unit == "tỷ" else 1_000_000))
            matched_spans.append((match.start(), match.end()))
        elif match := re.search(r'trên\s+(\d+)\s*(tỷ|triệu)', query):
            value = float(match.group(1))
            unit = match.group(2)
            filters["min_price"] = int(value * (1_000_000_000 if unit == "tỷ" else 1_000_000))
            matched_spans.append((match.start(), match.end()))

        # Loại bỏ matched spans khỏi query để lấy residual
        if matched_spans:
            matched_spans.sort()
            residual_parts = []
            last_end = 0
            for start, end in matched_spans:
                residual_parts.append(query[last_end:start])
                last_end = end
            residual_parts.append(query[last_end:])
            residual = ' '.join(residual_parts).strip()
            # Clean up multiple spaces
            residual = re.sub(r'\s+', ' ', residual)

        return filters, residual

    @classmethod
    def _extract_verified_code(cls, query: str) -> Optional[str]:
        """Extract và validate mã gói thầu."""
        for pattern in cls.CODE_PATTERNS:
            if match := re.search(pattern, query):
                return match.group(0)
        return None

    @classmethod
    def _needs_llm(cls, original_query: str, residual: str) -> bool:
        """
        Phát hiện tín hiệu phức tạp cần LLM.

        Tín hiệu:
        - Phủ định: "không", "ngoài", "trừ"
        - So sánh: "so sánh X và Y"
        - Thời gian tương đối: "sắp", "gần đây", "tháng này"
        """
        q = original_query.lower()

        # Phủ định
        if any(word in q for word in ["không phải", "ngoài", "trừ"]):
            return True

        # So sánh (chỉ khi có "so sánh")
        if "so sánh" in q:
            return True

        # Thời gian tương đối
        relative_time = ["sắp", "gần đây", "tháng này", "năm ngoái", "tuần trước"]
        if any(word in q for word in relative_time):
            return True

        return False

    @classmethod
    def _choose_method(cls, residual: str, code: Optional[str], filters: Dict) -> str:
        """
        Bước 3: Chọn method từ residual.

        Chỉ 3 nhánh:
        1. Có mã thật → bm25_code
        2. Không còn residual → metadata_only (filter + sort)
        3. Còn lại → hybrid (filter làm pre-filter)
        """
        if code:
            return "bm25_code"

        if not residual or len(residual.strip()) == 0:
            return "metadata_only"

        return "hybrid"

    @classmethod
    async def _analyze_with_llm(
        cls,
        query: str,
        regex_filters: Dict[str, Any],
        regex_residual: str
    ) -> Optional[Dict[str, Any]]:
        """
        LLM fallback cho queries phức tạp.

        Args:
            query: câu hỏi gốc
            regex_filters: filters từ regex
            regex_residual: residual từ regex

        Returns:
            {"filters": {...}, "residual": "..."} hoặc None nếu fail
        """
        # Danh sách tỉnh/thành phố cho LLM
        provinces_list = ", ".join(sorted(cls.PROVINCES))
        bid_forms_list = ", ".join(cls.BID_FORMS)

        system_prompt = f"""Bạn là chuyên gia phân tích câu hỏi về đấu thầu Việt Nam.

Nhiệm vụ: Phân tích câu hỏi phức tạp và trả về JSON:
{{
  "filters": {{
    "location": "...",      // từ danh sách: {provinces_list}
    "year": 2024,           // năm (int)
    "bidForm": "...",       // từ danh sách: {bid_forms_list}
    "min_price": 1000000,   // giá tối thiểu (VND)
    "max_price": 5000000000 // giá tối đa (VND)
  }},
  "residual": "..."         // phần còn lại để search
}}

**Xử lý đặc biệt:**
- Phủ định ("không phải Hà Nội") → KHÔNG thêm location filter
- So sánh ("so sánh X và Y") → residual giữ nguyên câu
- Thời gian tương đối: "sắp hết hạn" → không có filter year
- Đơn vị tiền: tỷ = 1,000,000,000 VND, triệu = 1,000,000 VND

Chỉ trả filters có trong câu hỏi. Trả ONLY JSON, không giải thích."""

        user_prompt = f"""Câu hỏi: "{query}"

Regex đã extract:
- Filters: {json.dumps(regex_filters, ensure_ascii=False)}
- Residual: "{regex_residual}"

Kiểm tra và sửa lại nếu regex sai (đặc biệt: phủ định, so sánh, thời gian tương đối)."""

        try:
            response = await DeepSeekClient.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format="json",
                temperature=0.1,
                max_tokens=300
            )

            result = json.loads(response)

            # Validate structure
            if "filters" not in result:
                result["filters"] = {}
            if "residual" not in result:
                result["residual"] = regex_residual

            return result

        except Exception as e:
            # LLM fail → fallback regex
            return None

