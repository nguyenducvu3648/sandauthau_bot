# Search Optimization - 7 Bước Triển Khai

Triển khai đầy đủ 7 bước tối ưu search theo kiến trúc mới.

## ✅ Đã triển khai

### 0. Bộ đánh giá (Evaluation)
- `scripts/generate_eval_dataset.py`: Sinh 50 câu query + gán nhãn bằng LLM
- `scripts/evaluate_search.py`: Đo Recall@50, nDCG@10, MRR
- Chạy: `python -m scripts.generate_eval_dataset && python -m scripts.evaluate_search`

### 1. BM25 - Tiếng Việt
- `config/synonyms.txt`: 50+ cặp từ đồng nghĩa (xd → xây dựng, ms → mua sắm)
- `config/es_mapping.json`: Analyzer `vi_search` với asciifolding + synonym
- Fuzziness AUTO (prefix_length=2) cho typo
- Boost: `search_text^3`, `bidName^2`, `procuringEntityName`
- Reindex: `python -m scripts.reindex_with_analyzer`

### 2. Vector - Threshold
- Ngưỡng similarity: 0.7 (loại kết quả yếu)
- Text embed: `bidName + linhVuc + procuringEntityName` (bỏ mô tả dài)
- Model hiện tại: `paraphrase-multilingual-MiniLM-L12-v2` (384 dim)
- TODO: Benchmark `bge-m3`, `vietnamese-sbert`

### 3. Hybrid - RRF
- **Thay script_score bằng RRF** (ES 8.8+)
- BM25 retriever: top 50, filters trong `bool.filter`
- KNN retriever: k=50, num_candidates=200, filters trong `knn.filter`
- RRF params: `rank_window_size=100`, `rank_constant=60`
- Không còn hardcode weight 0.3/0.7

### 4. Reranker - LLM
- LLM chấm lại top 20 → top 10
- Prompt: "Xếp hạng theo độ relevant (1-5)"
- Fallback: giữ nguyên thứ tự RRF nếu LLM fail
- Chỉ chạy cho hybrid với >10 results

### 5. Location - Mã thay wildcard
- `config/provinces.json`: 63 tỉnh/thành + aliases
- `services/location_service.py`: Map tên → mã
- Filter: `{"term": {"provCode": "01"}}` thay vì wildcard nested
- Index cần thêm field: `provCode`, `districtCode` (keyword)

### 6. Fallback Ladder
- Nới dần: full → no_price → no_price_bidForm_year → location_only → no_filter
- Trả về: `(results, relaxed_filters)`
- Bot thông báo: "Đã nới: max_price, bidForm. Còn 134 gói"

### 7. Metadata-only - Sort động
- `sắp hết hạn` → `{"deadline": "asc"}`
- `lớn nhất` → `{"bidPrice": "desc"}`
- Default → `{"publicDate": "desc"}`

## 🔧 Cách dùng

### SearchService mới
```python
from app.services.search_service import SearchService

search = SearchService()

# Search với fallback
results, relaxed = await search.search_with_fallback(
    query="xây dựng cầu Hà Nội",
    filters={"location": "Hà Nội", "year": 2024},
    method="hybrid",  # hybrid|bm25_code|metadata_only
    top_k=10
)

if relaxed:
    print(f"Đã nới: {', '.join(relaxed)}")
```

### RRF trực tiếp
```python
results = await search.hybrid_search_rrf(
    query="xây dựng cầu",
    top_k=50,
    filters={"location": "Hà Nội"}
)
```

## 📊 Checklist triển khai

- [x] Config: provinces.json, synonyms.txt, es_mapping.json
- [x] Services: search_service.py, location_service.py
- [x] Scripts: generate_eval_dataset.py, evaluate_search.py, reindex_with_analyzer.py
- [ ] **Reindex ES**: `python -m scripts.reindex_with_analyzer`
- [ ] **Copy synonyms.txt vào ES config**: `cp config/synonyms.txt /path/to/elasticsearch/config/`
- [ ] **Restart ES** để load synonym file
- [ ] **Update index mapping**: Index cần thêm `provCode`, `districtCode`
- [ ] **Generate eval dataset**: `python -m scripts.generate_eval_dataset`
- [ ] **Run baseline eval**: `python -m scripts.evaluate_search`
- [ ] **Integrate vào API**: Thay SearchService cũ bằng mới
- [ ] **Test end-to-end**: Chatbot → intent → search_with_fallback → response

## 🎯 Kết quả mong đợi

| Metric | Trước | Sau |
|--------|-------|-----|
| Recall@50 | - | >85% |
| nDCG@10 | - | >75% |
| MRR | - | >0.6 |
| Zero results | - | <5% |

## 🚀 Next steps

1. **Benchmark vector models** (bge-m3 vs hiện tại)
2. **Tune RRF params** (grid search rank_constant: 20, 60, 100)
3. **A/B test reranker** (LLM vs no reranker)
4. **Monitor production**: Log relaxed filters, zero results
5. **Fine-tune embedding** nếu gap còn lớn (dùng LLM sinh câu hỏi + hard negatives)
