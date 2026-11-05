# Eval Dataset - 100 câu hỏi thật có đáp án

**Mục đích**: Đo recall@10, MRR, tỷ lệ hỏi lại, latency cho V3/V4.

## Cấu trúc

Mỗi câu hỏi có:
- `query`: Câu hỏi user thật
- `intent`: Loại ý định (search/aggregation/continuation/casual)
- `expected_filters`: Filters đúng cần extract
- `expected_method`: Method search đúng (bm25_code/metadata_only/hybrid)
- `ground_truth_ids`: List bidId relevant (top 10 nếu có)
- `notes`: Ghi chú case đặc biệt

## Dataset 100 câu

### 1. Search queries - Địa điểm (20 câu)

```json
[
  {
    "id": 1,
    "query": "gói thầu ở Hà Nội",
    "intent": "search",
    "expected_filters": {"location": ["101", "01", "213", "15"]},
    "expected_method": "hybrid",
    "notes": "Test multi-code location filter"
  },
  {
    "id": 2,
    "query": "dự án xây dựng tại TP.HCM",
    "intent": "search",
    "expected_filters": {"location": ["701", "79"]},
    "expected_method": "hybrid"
  },
  {
    "id": 3,
    "query": "tìm gói thầu ở Đà Nẵng",
    "intent": "search",
    "expected_filters": {"location": ["501", "48"]},
    "expected_method": "hybrid"
  },
  {
    "id": 4,
    "query": "gói thầu tại HN",
    "intent": "search",
    "expected_filters": {"location": ["101", "01", "213", "15"]},
    "expected_method": "hybrid",
    "notes": "Alias HN"
  },
  {
    "id": 5,
    "query": "dự án ở Cần Thơ",
    "intent": "search",
    "expected_filters": {"location": ["815", "92"]},
    "expected_method": "hybrid"
  },
  {
    "id": 6,
    "query": "gói thầu Hải Phòng",
    "intent": "search",
    "expected_filters": {"location": ["103", "31"]},
    "expected_method": "hybrid"
  },
  {
    "id": 7,
    "query": "xây dựng ở Nghệ An",
    "intent": "search",
    "expected_filters": {"location": ["403", "40"]},
    "expected_method": "hybrid"
  },
  {
    "id": 8,
    "query": "mua sắm thiết bị y tế ở Thanh Hóa",
    "intent": "search",
    "expected_filters": {"location": ["401", "38"]},
    "expected_method": "hybrid"
  },
  {
    "id": 9,
    "query": "gói thầu tại Bình Dương",
    "intent": "search",
    "expected_filters": {"location": []},
    "expected_method": "hybrid",
    "notes": "Bình Dương không trong PROVINCE_CODES → rơi vào residual"
  },
  {
    "id": 10,
    "query": "đấu thầu xây dựng cầu ở Đồng Nai",
    "intent": "search",
    "expected_filters": {"location": ["713", "75"]},
    "expected_method": "hybrid"
  }
]
```

### 2. Search queries - Năm (10 câu)

```json
[
  {
    "id": 11,
    "query": "gói thầu năm 2024",
    "intent": "search",
    "expected_filters": {"year": 2024},
    "expected_method": "hybrid"
  },
  {
    "id": 12,
    "query": "dự án năm 2023 ở Hà Nội",
    "intent": "search",
    "expected_filters": {"year": 2023, "location": ["101", "01", "213", "15"]},
    "expected_method": "hybrid"
  },
  {
    "id": 13,
    "query": "gói thầu 2022",
    "intent": "search",
    "expected_filters": {"year": 2022},
    "expected_method": "hybrid"
  },
  {
    "id": 14,
    "query": "dự án xây dựng năm 2025",
    "intent": "search",
    "expected_filters": {"year": 2025},
    "expected_method": "hybrid"
  },
  {
    "id": 15,
    "query": "mua sắm thiết bị 2024 ở TP.HCM",
    "intent": "search",
    "expected_filters": {"year": 2024, "location": ["701", "79"]},
    "expected_method": "hybrid"
  }
]
```

### 3. Search queries - Giá (15 câu)

```json
[
  {
    "id": 16,
    "query": "gói thầu dưới 5 tỷ",
    "intent": "search",
    "expected_filters": {"max_price": 5000000000},
    "expected_method": "hybrid"
  },
  {
    "id": 17,
    "query": "dự án trên 10 tỷ",
    "intent": "search",
    "expected_filters": {"min_price": 10000000000},
    "expected_method": "hybrid"
  },
  {
    "id": 18,
    "query": "gói thầu dưới 500 triệu",
    "intent": "search",
    "expected_filters": {"max_price": 500000000},
    "expected_method": "hybrid"
  },
  {
    "id": 19,
    "query": "dự án lớn hơn 20 ty",
    "intent": "search",
    "expected_filters": {"min_price": 20000000000},
    "expected_method": "hybrid"
  },
  {
    "id": 20,
    "query": "gói thầu 3 tỷ",
    "intent": "search",
    "expected_filters": {"max_price": 3000000000},
    "expected_method": "hybrid",
    "notes": "Không có từ khóa trên/dưới → default max_price"
  },
  {
    "id": 21,
    "query": "gói thầu dưới 1 tỷ ở Hà Nội năm 2024",
    "intent": "search",
    "expected_filters": {"max_price": 1000000000, "location": ["101", "01", "213", "15"], "year": 2024},
    "expected_method": "hybrid"
  }
]
```

### 4. Search queries - Mã gói thầu (10 câu)

```json
[
  {
    "id": 22,
    "query": "gói thầu BP2200225863",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "bm25_code",
    "code": "BP2200225863",
    "notes": "Fast-path exact code lookup"
  },
  {
    "id": 23,
    "query": "thông tin gói BP2200094095",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "bm25_code",
    "code": "BP2200094095"
  },
  {
    "id": 24,
    "query": "chi tiết BP2200106605",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "bm25_code",
    "code": "BP2200106605"
  }
]
```

### 5. Metadata-only queries (10 câu)

```json
[
  {
    "id": 25,
    "query": "gói thầu sắp hết hạn",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "metadata_only",
    "notes": "Sort bidCloseDate asc"
  },
  {
    "id": 26,
    "query": "gói thầu giá trị lớn nhất",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "metadata_only",
    "notes": "Sort bidPrice desc"
  },
  {
    "id": 27,
    "query": "gói thầu mới nhất ở Hà Nội",
    "intent": "search",
    "expected_filters": {"location": ["101", "01", "213", "15"]},
    "expected_method": "metadata_only",
    "notes": "Sort publicDate desc"
  },
  {
    "id": 28,
    "query": "gói thầu nhỏ nhất",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "metadata_only",
    "notes": "Sort bidPrice asc"
  }
]
```

### 6. Aggregation queries (15 câu)

```json
[
  {
    "id": 29,
    "query": "có bao nhiêu gói thầu ở Hà Nội",
    "intent": "aggregation",
    "expected_filters": {"location": ["101", "01", "213", "15"]},
    "expected_method": "aggregation"
  },
  {
    "id": 30,
    "query": "thống kê gói thầu năm 2024",
    "intent": "aggregation",
    "expected_filters": {"year": 2024},
    "expected_method": "aggregation"
  },
  {
    "id": 31,
    "query": "top 5 tỉnh có nhiều gói thầu nhất",
    "intent": "aggregation",
    "expected_filters": {},
    "expected_method": "aggregation",
    "notes": "Aggregation locations.provCode terms, size=5"
  },
  {
    "id": 32,
    "query": "tổng giá trị gói thầu ở TP.HCM",
    "intent": "aggregation",
    "expected_filters": {"location": ["701", "79"]},
    "expected_method": "aggregation",
    "notes": "Sum bidPrice"
  },
  {
    "id": 33,
    "query": "bao nhiêu gói thầu xây dựng",
    "intent": "aggregation",
    "expected_filters": {},
    "expected_method": "aggregation"
  }
]
```

### 7. Casual queries (5 câu)

```json
[
  {
    "id": 34,
    "query": "xin chào",
    "intent": "casual",
    "expected_filters": {},
    "expected_method": "none"
  },
  {
    "id": 35,
    "query": "cảm ơn bạn",
    "intent": "casual",
    "expected_filters": {},
    "expected_method": "none"
  },
  {
    "id": 36,
    "query": "hello",
    "intent": "casual",
    "expected_filters": {},
    "expected_method": "none"
  }
]
```

### 8. LLM signal queries (15 câu)

```json
[
  {
    "id": 37,
    "query": "gói thầu không phải ở Hà Nội",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "hybrid",
    "llm_signal": "negation",
    "notes": "Negation → cần LLM refine"
  },
  {
    "id": 38,
    "query": "so sánh gói thầu A và gói B",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "hybrid",
    "llm_signal": "comparison"
  },
  {
    "id": 39,
    "query": "gói thầu gần đây",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "hybrid",
    "llm_signal": "relative_time"
  },
  {
    "id": 40,
    "query": "gói đó như thế nào",
    "intent": "search",
    "expected_filters": {},
    "expected_method": "hybrid",
    "llm_signal": "pronoun",
    "notes": "Cần session context"
  }
]
```

---

## Cách dùng

1. **Ground truth bidId**: Chạy query thật trên index, lấy top 10 relevant manual check.
2. **Đo metrics**:
   - Recall@10: Có bao nhiêu ground_truth_ids trong top 10 kết quả?
   - MRR: Mean Reciprocal Rank của bidId đầu tiên xuất hiện
   - Tỷ lệ hỏi lại: Bao nhiêu query không trả kết quả (fallback hết)?
   - Latency: p50, p95 thời gian xử lý

3. **Script eval**:
```python
python scripts/run_eval.py --dataset config/eval_100.json --output results/v3_eval.json
```

---

## TODO

- [ ] Điền ground_truth_ids cho 40 câu quan trọng (chạy query thật, manual label)
- [ ] Viết script `run_eval.py` chạy batch 100 câu
- [ ] Tạo report metrics: recall, MRR, latency, tỷ lệ hỏi lại
