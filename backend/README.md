# Tender Search Backend

FastAPI backend cho hệ thống RAG tìm kiếm gói thầu với 526k records.

## Features

### Core Search
- **BM25 Text Search**: Keyword-based search
- **Vector Similarity**: Semantic search với 384-dim embeddings
- **Hybrid Search**: RRF merge BM25 + Vector
- **Filter Search**: Metadata filtering + vector

### Intelligence
- **Intent Analysis**: Tự động phân loại casual vs search queries
- **Auto-routing**: Chọn search methods phù hợp
- **Filter Extraction**: Tự động extract năm, địa điểm, loại hình
- **Multi-criteria Ranking**: Search score + recency + value + exact match

### Cache (3-tier)
- **Query Cache**: 15 phút, 1000 entries
- **Embedding Cache**: 1 giờ, 5000 vectors
- **User Context**: Session-based, track frequent filters & interests

### RAG Answer Generation
- **Streaming Response**: Server-Sent Events
- **Context-aware**: Sử dụng search history
- **Citations**: Cite nguồn cho mỗi gói thầu
- **Natural Language**: Trả lời tự nhiên, dễ hiểu

## Cài đặt

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Sửa DEEPSEEK_API_KEY trong .env
```

## Chạy server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## Endpoints

### 1. BM25 Text Search
```bash
POST /search/bm25
{
  "query": "xây dựng cầu đường",
  "top_k": 10
}
```

### 2. Vector Similarity Search
```bash
POST /search/vector
{
  "query": "xây dựng cầu đường",
  "top_k": 10,
  "min_score": 0.5
}
```

### 3. Hybrid Search (BM25 + Vector)
```bash
POST /search/hybrid
{
  "query": "xây dựng cầu đường",
  "top_k": 10,
  "min_score": 0.5,
  "text_weight": 0.3
}
```

### 4. Filter + Vector Search
```bash
POST /search/filter
{
  "query": "xây dựng cầu đường",
  "filters": {
    "bidForm": "Đấu thầu rộng rãi",
    "year": 2024,
    "location": "Hà Nội"
  },
  "top_k": 10,
  "min_score": 0.5
}
```

### 5. Auto Search (Intelligent Routing) ⭐
```bash
POST /search/auto
{
  "query": "xây dựng cầu Hà Nội 2024",
  "top_k": 10,
  "session_id": "user123"  # Optional
}

Response:
{
  "query": "...",
  "total": 15,
  "results": [...],
  "took_ms": 234,
  "intent": "search",
  "methods_used": ["filter", "hybrid"],
  "filters_applied": {"location": "Hà Nội", "year": 2024}
}
```

### 6. RAG Answer (Streaming) ⭐
```bash
POST /search/answer
{
  "query": "tìm gói thầu xây dựng cầu ở Hà Nội",
  "top_k": 10,
  "session_id": "user123"  # Optional
}

Response: Server-Sent Events stream
data: {"type": "metadata", "took_ms": 234, "total_docs": 15, ...}
data: {"type": "chunk", "content": "Tôi tìm thấy "}
data: {"type": "chunk", "content": "15 gói thầu "}
data: {"type": "chunk", "content": "xây dựng cầu..."}
data: {"type": "citations", "content": "[1] Gói thầu ..."}
data: {"type": "done"}
```

### 7. Cache Stats
```bash
GET /search/cache/stats

Response:
{
  "query_cache": {"size": 123, "maxsize": 1000, "ttl": 900},
  "embed_cache": {"size": 456, "maxsize": 5000, "ttl": 3600},
  "user_context": {"sessions": 10, "total_queries": 234}
}
```

### 8. Clear User Cache
```bash
POST /search/cache/clear/{session_id}
```

## Cấu trúc

```
backend/
├── app/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Settings
│   ├── models/
│   │   ├── request.py           # Request schemas
│   │   └── response.py          # Response schemas
│   ├── services/
│   │   ├── es_client.py         # Elasticsearch client
│   │   ├── embedding.py         # Embedding service (với cache)
│   │   ├── search.py            # Basic search methods
│   │   ├── advanced_search.py   # RRF + ranking
│   │   ├── intent_analyzer.py   # Intent analysis
│   │   ├── cache_service.py     # 3-tier cache
│   │   ├── rag_service.py       # RAG answer generation
│   │   └── deepseek_client.py   # DeepSeek API client
│   └── routers/
│       └── search.py            # API endpoints
├── requirements.txt
├── .env.example
└── README.md
```

## Environment Variables

Xem `.env.example` để biết đầy đủ config.

**Required:**
- `DEEPSEEK_API_KEY`: DeepSeek API key
- `ES_URL`, `ES_USER`, `ES_PASSWORD`: Elasticsearch connection
- `ES_INDEX`: Index name (default: dauthaus_prod_526k)

**Optional (có defaults):**
- `RRF_WEIGHT_BM25`, `RRF_WEIGHT_VECTOR`: RRF weights
- `RANK_WEIGHT_*`: Multi-criteria ranking weights
- `DEEPSEEK_TEMPERATURE`, `DEEPSEEK_MAX_TOKENS`: LLM params

## Workflow

### Query Flow (với RAG)
```
User Query
    ↓
Intent Analysis (rule-based + DeepSeek fallback)
    ├─ casual → Stream chat response
    └─ search ↓
         ↓
Check Cache (query + embed)
         ↓
Apply User Context (frequent filters)
         ↓
Auto-routing (chọn methods)
         ↓
Execute Search (RRF merge nếu multi-method)
         ↓
Multi-criteria Ranking
         ↓
Cache Results + Update User Context
         ↓
Format Context (top 15 docs)
         ↓
DeepSeek Streaming (RAG answer)
         ↓
Stream to Client (SSE)
```

### Cache Strategy
- **Query Cache**: Toàn bộ query + methods + filters → results
- **Embed Cache**: Query text → vector (skip encode nếu hit)
- **User Context**: Session → frequent filters, interests, history
  - Auto-apply frequent filters nếu query không có explicit filters
  - Track interests để recommend sau này

### Ranking Logic
```
Final Score = 
  0.5 * search_score +     # RRF score từ merge
  0.2 * recency +          # 2024→1.0, 2023→0.9, ...
  0.15 * value +           # log(bidPrice), 1 tỷ~0.75, 1000 tỷ~1.0
  0.15 * exact_match       # Bonus nếu match bidNo/bidId
```

## Performance

**Latency (ước tính với 384-dim):**
- BM25 only: ~30ms
- Vector only: ~130ms (50ms encode + 80ms search)
- Hybrid (RRF): ~170ms
- Auto search (cache hit): ~5ms
- Auto search (cache miss): ~150-250ms
- RAG answer TTFT: ~450ms (search + format + first token)

**Cache hit rates (ước tính):**
- Query cache: ~30-40% (user hỏi lại câu tương tự)
- Embed cache: ~50-60% (nhiều queries dùng keywords giống nhau)
- User context: 100% (luôn có nếu có session_id)

## Testing

```bash
# Health check
curl http://localhost:8000/health

# Simple search
curl -X POST http://localhost:8000/search/auto \
  -H "Content-Type: application/json" \
  -d '{"query": "xây dựng cầu", "top_k": 5}'

# RAG answer (streaming)
curl -X POST http://localhost:8000/search/answer \
  -H "Content-Type: application/json" \
  -d '{"query": "tìm gói thầu xây dựng ở Hà Nội", "session_id": "test123"}' \
  --no-buffer

# Cache stats
curl http://localhost:8000/cache/stats
```

## Notes

### Future: Rerank
Hiện tại chưa implement rerank (ColBERT + BAAI). Nếu sau khi test 384-dim baseline accuracy < 80%, sẽ thêm miniLM-L6 rerank (~200ms overhead).

### Future: 768-dim
Khi nâng lên 768-dim embeddings, chỉ cần:
1. Update `MODEL_NAME` và `EMBEDDING_DIM` trong config
2. Re-embed 526k records
3. Re-index vào ES

Code không cần thay đổi.

### Query Rewrite
Hiện tại chưa có query rewrite (dành cho tư vấn pháp lý). Nếu sau này nâng cấp lên tư vấn đấu thầu, thêm:
- `rewrite_query()` trong `intent_analyzer.py`
- Intent mới: `advisory` (tư vấn) vs `search` (tìm kiếm)
