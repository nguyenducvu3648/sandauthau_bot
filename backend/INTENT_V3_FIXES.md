# Intent Analyzer V3 - 5 Fixes Chính

## Lỗi 1: Confidence giả → gọi LLM không cần thiết

**Trước:**
```python
# Search có confidence=0.90, ngưỡng <0.97 → gọi LLM mọi câu
if confidence < 0.97:
    llm_intent = await _analyze_intent_with_llm(query)
```

**Sau:**
```python
# Chỉ gọi LLM khi có tín hiệu cụ thể:
signals = _detect_llm_signals(query, filters, residual)
# - Phủ định: "không phải", "ngoài", "trừ"
# - So sánh: "so sánh X và Y"
# - Thời gian tương đối: "sắp", "gần đây", "tháng này"
# - Đại từ: "nó", "cái này", "gói đó"
# - Regex mâu thuẫn: location + "không phải"

if signals:
    llm_result = await _refine_with_llm(query, filters, residual, signals)
    llm_calls.append(f"filter:{signals}")
```

---

## Lỗi 2: Thứ tự mã/filter → mã bị bóc nhầm năm

**Trước:**
```python
# "DT-2024-123" → year=2024, residual="DT--123"
filters, residual = _extract_filters_and_residual(query)
code = _extract_verified_code(query)
```

**Sau:**
```python
# Phát hiện mã TRƯỚC, mask nó đi
code = _extract_code(query)  # → "DT-2024-123"
masked_query = query.replace(code, "<CODE>") if code else query
filters, residual = _extract_filters_and_residual(masked_query)

# Verify mã tồn tại trong DB
if code and not _code_exists_in_db(code):
    code = None  # Tránh nhầm "ISO 9001"
    # Fallback về hybrid search
```

---

## Lỗi 3: Residual không sạch → metadata_only ít chạy

**Trước:**
```python
# "gói thầu ở Hà Nội năm 2024" → residual="gói thầu" → đi hybrid
if not residual:
    return "metadata_only"
```

**Sau:**
```python
STOPWORDS = {"tìm", "cho", "tôi", "giúp", "danh sách", "các", 
             "gói thầu", "gói", "thầu", "dự án", "xem", "liệt kê"}

def _clean_residual(residual: str) -> str:
    words = residual.lower().split()
    words = [w for w in words if w not in STOPWORDS]
    return " ".join(words).strip()

# "gói thầu ở Hà Nội năm 2024" → residual="" → metadata_only
```

---

## Lỗi 4: Aggregation/continuation thoát sớm → mất filter

**Trước:**
```python
if intent == "aggregation":
    return QueryAnalysis(intent="aggregation", filters={}, ...)
    # "top 5 tỉnh nhiều gói thầu năm 2024" → mất year filter
```

**Sau:**
```python
# Aggregation/continuation đều đi qua bước filter
code = _extract_code(query)
masked_query = _mask_code(query, code) if code else query
filters, residual = _extract_filters_and_residual(masked_query)

if intent == "aggregation":
    # Giữ filters cho aggregation pipeline
    return QueryAnalysis(
        intent="aggregation",
        filters=filters,  # ✓ Có year=2024
        residual=residual,
        method="aggregation"
    )

if intent == "continuation" and session_context:
    # Merge filters từ câu trước
    filters = {**session_context.get("filters", {}), **filters}
```

---

## Lỗi 5: Ladder bước 5 → trả sai ngầm

**Trước:**
```python
steps = [
    (filters, []),
    (no_price, ["max_price"]),
    (no_price_bidForm, ["max_price", "min_price", "bidForm"]),
    (location_only, ["price", "bidForm", "year"]),
    ({}, list(filters.keys())),  # ← Bỏ location, trả toàn quốc
]
```

**Sau:**
```python
# Dừng ở bước 4, không bỏ location
steps = [
    (filters, []),
    (no_max_price, ["max_price"]),
    (no_price_bidForm, ["max_price", "min_price", "bidForm"]),
    (location_only, ["price", "bidForm", "year"]),
    # Bước 5: Hỏi lại thay vì bỏ location
]

if not results and "location" in filters:
    return [], ["ASK_USER_EXPAND_LOCATION"]  # Signal bot hỏi lại

# Xử lý phủ định
if filter_type == "location" and is_negation:
    # "không phải Hà Nội" → must_not query
    clauses.append({"bool": {"must_not": [
        {"nested": {"path": "locations", "query": {"term": {"locations.provCode": code}}}}
    ]}})
```

---

## Điểm nhỏ

### 1. Danh mục tỉnh 2025
```python
# 34 tỉnh/thành mới + map tên cũ
PROVINCES = {
    "Hà Nội": ["HN", "Hanoi", "Thủ đô"],
    "TP.HCM": ["HCM", "Sài Gòn", "Saigon"],
    # ... (load từ provinces.json với old_names)
}
```

### 2. Rerank có điều kiện
```python
async def search_with_fallback(...):
    if method == "bm25_code":
        # Khớp mã chính xác, không cần rerank
        return results, relaxed
    
    if method == "metadata_only":
        # Sort động, không cần rerank
        return results, relaxed
    
    if method == "hybrid" and len(results) > 10:
        # Kiểm tra gap top vs rest
        if results[0].score > results[1].score * 1.5:
            # Top vượt xa, không cần rerank
            return results[:top_k], relaxed
        
        # Rerank với timeout
        try:
            results = await asyncio.wait_for(
                _rerank(query, results, top_k),
                timeout=3.0
            )
            llm_calls.append("rerank")
        except asyncio.TimeoutError:
            # Giữ thứ tự RRF
            pass
    
    return results[:top_k], relaxed
```

### 3. Verify mã gói thầu
```python
async def _code_exists_in_db(code: str) -> bool:
    """Check mã có tồn tại trong ES."""
    result = await es.search(
        index=index,
        body={"query": {"term": {"bidCode": code}}, "size": 1}
    )
    return result["hits"]["total"]["value"] > 0
```

### 4. LLM calls tracking
```python
@dataclass
class QueryAnalysis:
    llm_calls: List[str] = field(default_factory=list)
    # ["filter:negation", "rerank"] → track chi phí
```

### 5. Session state + logging
```python
session_context = {
    "last_query": query,
    "last_filters": filters,
    "last_results": [r["bidCode"] for r in results[:5]],
    "timestamp": datetime.now().isoformat()
}

# Log mỗi query
logger.info({
    "query": query,
    "analysis": analysis.dict(),
    "method": analysis.method,
    "relaxed": relaxed,
    "llm_calls": analysis.llm_calls,
    "latency_ms": latency,
    "results_count": len(results)
})
```

---

## So sánh V2 vs V3

| Khía cạnh | V2 | V3 |
|-----------|----|----|
| LLM calls | Mọi search (confidence < 0.97) | Chỉ khi có signal cụ thể |
| Mã gói thầu | Extract sau filter | Extract + mask trước filter |
| Residual | "gói thầu" → hybrid | Clean stopwords → metadata |
| Aggregation | Thoát sớm, mất filter | Đi qua filter step |
| Ladder bước 5 | Bỏ location → toàn quốc | Dừng + hỏi user |
| LLM tracking | `needs_llm: bool` | `llm_calls: List[str]` |
| Rerank | Luôn chạy | Có điều kiện + timeout |
| Verify mã | Regex only | Regex + DB check |

---

## Implementation priority

1. **Fix lỗi 1 (LLM signals)** - Giảm 80% LLM calls không cần thiết
2. **Fix lỗi 3 (stopwords)** - Tăng tỷ lệ dùng metadata_only
3. **Fix lỗi 2 (mask mã)** - Sửa bug nghiêm trọng với mã có năm
4. **Fix lỗi 5 (ladder)** - UX tốt hơn khi không có kết quả
5. **Fix lỗi 4 (aggregation)** - Enable aggregation với filter
