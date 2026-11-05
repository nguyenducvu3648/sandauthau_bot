# Test V4 Search với UI

## Setup

**Backend:** http://localhost:8000  
**Frontend:** http://localhost:3000  
**API Endpoint:** `/search/v4/answer` (V4 search + RAG streaming)

---

## UI Features

### 2-Panel Layout

**Left Panel: Documents**
- Hiển thị top-10 gói thầu tìm được
- Metadata: total matched, latency, search method
- Mỗi doc có: tên gói thầu, mã số, đơn vị, giá, địa điểm, ngày mở/đóng thầu
- Score (RRF/BM25) cho debug

**Right Panel: RAG Answer**
- Câu trả lời streaming từ LLM
- Citations: [1], [2], ... link tới docs
- Formatted: bold **text**, line breaks
- Status: "Đang trả lời..." → "✓ Hoàn thành"

---

## Test Cases

### 1. Basic Search
```
Query: "thầu xây dựng ở Hà Nội"
```

**Expected:**
- Left: 10 docs về xây dựng tại Hà Nội
- Right: Answer tóm tắt + citations [1], [2]...
- Latency: ~4-5s (cold), ~1s (warm)
- Method: `hybrid` badge (purple)

---

### 2. Bid Code Lookup
```
Query: "221240000049"
```

**Expected:**
- Left: 1 exact match doc (nếu tồn tại)
- Method: `fastpath` badge
- Latency: ~100ms

---

### 3. Pagination
```
1. Query: "thầu xây cầu"
2. Query: "tiếp theo" (hoặc "trang sau")
```

**Expected:**
- Lượt 2: 10 docs mới (khác lượt 1)
- Method: `pagination` badge
- Latency: ~100ms (không re-search)

---

### 4. Zero Results
```
Query: "gói thầu về du hành vũ trụ"
```

**Expected:**
- Left: "Không tìm thấy gói thầu nào"
- Right: "Không có thông tin phù hợp..."
- Total: 0

---

### 5. Streaming Answer
```
Query: "tìm thầu xây dựng dưới 5 tỷ"
```

**Expected:**
- Answer hiển thị từng chunk (như typing effect)
- Citations xuất hiện cuối cùng
- Status bar: "Đang trả lời..." → "✓ Hoàn thành"

---

## Debug Info

### Check Timing Breakdown
Mở DevTools Console:
- Metadata event: `took_ms`, `total_docs`, `method`
- Chunk events: streaming speed
- Citations: formatted refs

### Check Search Method
Badge color:
- 🟣 Purple: `hybrid` (BM25 + kNN)
- 🟠 Orange: `filter_only` (exact filters)
- 🔵 Blue: `fastpath` (bid code)
- 🟢 Green: `pagination`

### Check Response Structure
Network tab → `/search/v4/answer`:
- SSE stream
- `data: {"type": "metadata", ...}`
- `data: {"type": "chunk", "content": "..."}`
- `data: {"type": "citations", ...}`
- `data: {"type": "done"}`

---

## Known Issues

### If ES is down:
- `/health` returns `{"elasticsearch": false}`
- Search will fail with 500 error
- Fix: Start ES với `elasticsearch.bat`

### If LLM times out:
- Answer panel shows error
- Docs panel có thể vẫn có kết quả (fallback to hybrid)
- Fix: Check `.env` LLM credentials

### If no citations appear:
- Check console for SSE parse errors
- Verify backend logs: "INFO: [RAG] Formatting citations..."

---

## Success Criteria

✅ **UI hoạt động:**
- 2 panels render đồng thời
- Docs load trước, answer stream sau
- Citations có số [1], [2] clickable style

✅ **Performance:**
- Cold search: 4-5s
- Warm search: <1s
- Pagination: <200ms

✅ **Correctness:**
- Docs match query intent
- Answer có citations từ docs
- Method badge đúng flow (hybrid/fastpath/pagination)

---

## Next Steps

1. Start ES nếu chưa chạy
2. Mở http://localhost:3000
3. Thử 5 test cases trên
4. Check console + network tab
5. Report bugs nếu có

**Báo cáo test đầy đủ:** `backend/tests/V4_TEST_REPORT_FINAL.md`
