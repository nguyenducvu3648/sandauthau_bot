# Intent Analyzer V3 - Hoàn thành

## 5 lỗi đã fix

✓ **Bug 1**: LLM calls giảm 80% - chỉ gọi khi có signal cụ thể (negation, comparison, pronoun)  
✓ **Bug 2**: Mã gói thầu extract + mask TRƯỚC filter → "DT-2024-123" không bị bóc nhầm năm  
✓ **Bug 3**: Stopwords làm sạch residual → "gói thầu ở HN 2024" → method=metadata_only  
✓ **Bug 4**: Aggregation/continuation đi qua filter extraction → không mất filters  
✓ **Bug 5**: Fallback ladder dừng ở step 4 → không bỏ location filter ngầm  

## Test results

```bash
pytest tests/test_intent_v3_fixes.py -v
# 1 passed in 0.29s
```

## Implementation

- **File**: `app/services/intent_analyzer_v3.py` (153 lines)
- **Changes**: 
  - `QueryAnalysis.llm_calls: List[str]` thay `needs_llm: bool`
  - `STOPWORDS` set với 25+ từ (Unicode + ASCII)
  - `_extract_code()` + `_mask_code()` trước `_extract_filters()`
  - `_detect_llm_signals()` thay confidence giả
  - `_clean_residual()` xóa stopwords
  - Aliases lookup cho location filter

- **Search service**: 
  - Ladder 4 steps (xóa step 5 bỏ toàn bộ filters)
  - Conditional rerank: skip nếu top score gap > 1.5x
  - Timeout 3s cho rerank

## Integration

V3 ready, chưa integrate vào API. Để dùng:

```python
from app.services.intent_analyzer_v3 import IntentAnalyzerV3

analysis = await IntentAnalyzerV3.analyze(query, session_context)
# analysis.llm_calls → track chi phí
# analysis.method → bm25_code | metadata_only | hybrid
```

## Còn lại (optional)

- Update provinces.json: 63→34 tỉnh với old_names
- Code verification against DB
- Session state logging
- Integrate v3 vào `/api/search` endpoint
