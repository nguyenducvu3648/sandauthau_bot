# THIẾT KẾ LUỒNG TÌM KIẾM V4 — Chatbot sandauthau.vn

**Mục đích:** tài liệu duy nhất để agent triển khai V4. Gộp V3 (đã sửa lỗi), đánh giá của 2 agent và review.
**Trạng thái:** luồng đã chốt. Các ngưỡng số (mục 12) chỉ chốt được bằng bộ đánh giá, không chốt bằng cảm tính.
**Lưu ý:** mọi đoạn code trong tài liệu là pseudocode minh họa, không merge trực tiếp.

---

## 1. Nguyên tắc cốt lõi (không được vi phạm)

1. **LLM hiểu câu hỏi, code chọn cách chạy, DB tính số liệu.** LLM không tự viết query, không tự chọn phương thức search, không tự đếm.
2. **Không bao giờ âm thầm đổi điều kiện của user.** Nới điều kiện phụ phải báo rõ; điều kiện cốt lõi (địa điểm, chủ đề) phải hỏi lại.
3. **Mã, giá, ngày, link luôn lấy từ DB** (thẻ gói thầu), LLM chỉ viết đoạn dẫn và tóm tắt.
4. **Mọi bước LLM đều có đường lui** (timeout, JSON hỏng, validate fail) để user luôn nhận được kết quả.
5. **Đo trước khi chỉnh.** Không thêm độ phức tạp (tách BM25/vector, cross-encoder, fine-tune) nếu số liệu chưa chỉ ra chỗ sai.

---

## 2. Điều kiện tiên quyết (làm TRƯỚC khi code)

| # | Việc | Vì sao |
|---|---|---|
| P1 | Lấy `_mapping` thật của index ES, xác định `locations` là **nested** hay **phẳng** (`provCode`, `districtCode`) | File config có thể lệch index thật. Quyết định hình dạng filter địa điểm và aggregation |
| P2 | Cập nhật danh mục tỉnh/thành: **34 đơn vị sau sáp nhập 2025** (kiểm tra lại với danh mục chính thức), giữ alias tên cũ → mới | `provinces.json` còn 63 tỉnh |
| P3 | Dựng **bộ đánh giá 100–200 câu hỏi thật** (log tìm kiếm web, câu CSKH) có đáp án. Bộ sinh tự động chỉ để bổ sung vì câu sinh từ dữ liệu sẽ giống tiêu đề gói thầu, làm BM25 đạt điểm cao ảo | Mọi ngưỡng chỉ chốt được bằng bộ này |
| P4 | Xác định định dạng mã gói thầu **từ dữ liệu thật** (không dùng 4 tiền tố cứng) | Tránh bỏ sót mã |
| P5 | Kiểm tra dữ liệu có trường **lĩnh vực / loại gói chuẩn hóa** (category) hay không | Quyết định thống kê chính xác hay ước tính (mục 8) |

---

## 3. Luồng tổng thể

```
Câu hỏi + session
 │
 ├─ [1] FAST PATH (regex, không LLM phân tích)
 │     ├─ Có mã gói thầu hợp lệ → by_code → trả thẻ
 │     └─ Xã giao thuần → LLM nhỏ trả lời tự nhiên (cache "xin chào")
 │
 ├─ [2] PAGINATION nhanh (regex chặt, chỉ khi session có danh sách xếp hạng)
 │     └─ "thêm 5 gói nữa" → lấy tiếp từ danh sách đã xếp hạng, 0 lần search
 │
 ├─ [3] PHÂN TÍCH (1 lần gọi LLM, JSON) → validate → lỗi thì V3 dự phòng
 │
 ├─ [4] THỰC THI: gộp state → chọn method (code) → search / aggregation
 │
 ├─ [5] XỬ LÝ KẾT QUẢ: RRF → rerank có điều kiện → cắt theo liên quan
 │
 ├─ [6] FALLBACK / HỎI LẠI nếu 0 hoặc quá nhiều kết quả
 │
 ├─ [7] TRẢ LỜI: thẻ từ DB + đoạn dẫn LLM + kiểm tra số
 │
 └─ [8] CẬP NHẬT SESSION + GHI LOG
```

---

## 4. Bước 1 — Fast path

**1.1 Mã gói thầu**
- Regex theo định dạng lấy từ dữ liệu thật (P4). Chuẩn hóa: chữ hoa, bỏ khoảng trắng, thống nhất dấu gạch.
- Tìm bằng `term` trên field `bidCode` (keyword).
- **Không tồn tại** → không dừng, chuyển xuống bước 3 (có thể là "ISO 9001", "COVID-19").
- **Nhiều mã** trong câu → chuyển bước 3 với `output_mode=compare`.
- Mã trong câu phải được **mask** trước mọi bước trích filter (tránh bóc "2024" trong "DT-2024-123" thành năm).

**1.2 Xã giao thuần**
- Chỉ coi là xã giao khi **sau khi bỏ lời chào/cảm ơn, phần còn lại rỗng**. "Xin chào, tìm gói thầu xây cầu" **không** phải xã giao.
- Dùng ranh giới từ, không dùng `in` (chứa chuỗi).
- Trả lời bằng LLM nhỏ, prompt ngắn: giới thiệu vai trò, trả lời tự nhiên, kéo nhẹ về tra cứu đấu thầu nếu lạc đề. Chỉ cache câu chào thuần.
- Câu hỏi về chính bot ("bạn là ai", "bạn làm được gì") lọt xuống bước 3 và được nhận bằng `output_mode=chat`.

---

## 5. Bước 2 — Pagination nhanh

- Điều kiện: session có `ranked_ids` (danh sách đã xếp hạng) **và** câu khớp mẫu chặt: ngắn, dạng "thêm N gói nữa / tiếp / xem thêm".
- Hành động: lấy N gói tiếp từ `ranked_ids[offset: offset+N]`, **không search lại, không gọi LLM phân tích**, chỉ 1 lần LLM viết đoạn dẫn (hoặc dùng mẫu).
- Câu có thêm điều kiện mới ("thêm điều kiện giá dưới 5 tỷ") **không** khớp mẫu → đi bước 3.

---

## 6. Bước 3 — Phân tích bằng LLM (1 lần gọi)

### 6.1 Đầu vào
```json
{
  "query": "...",
  "today": "YYYY-MM-DD",
  "session": { "last_filters": {}, "last_topic": "", "last_operation": "" },
  "regex_hints": {
    "locations": [], "years": [], "prices": [], "signals": ["negation", "aggregation_keyword"]
  },
  "catalogs": { "provinces": "<danh mục mã tỉnh + alias>", "bid_forms": [], "statuses": [], "categories": [] }
}
```
`today` bắt buộc, nếu không LLM đoán sai "tuần này", "sắp hết hạn".

### 6.2 Đầu ra (schema cố định)
```json
{
  "scope": "new | continuation",
  "output_mode": "list | aggregate | compare | chat",
  "topic": "chủ đề đã bỏ stopword, hoặc null",
  "filters": {
    "location": { "include": ["<mã>"], "exclude": ["<mã>"] },
    "year": null,
    "price_min": null, "price_max": null,
    "bid_form": null,
    "category": null,
    "status": "open | closed | awarded | null",
    "deadline_from": null, "deadline_to": null
  },
  "clear": [],
  "sort": "newest | deadline_asc | price_desc | null",
  "aggregate_by": "province | month | bid_form | category | null",
  "top_n": null,
  "compare_entities": null,
  "needs_clarification": false,
  "clarification_question": null
}
```

### 6.3 Quy tắc cho LLM (đưa vào prompt)
1. Phủ định ("không phải/không ở/ngoài/trừ/loại/khác/ngoại trừ X") → `exclude`.
2. So sánh → `output_mode=compare`, `compare_entities`.
3. Thời gian tương đối quy ra ngày cụ thể dựa trên `today`. "Sắp hết hạn" = `deadline_from=today`, `status=open`.
4. Thống kê ("top", "bao nhiêu", "tổng", "thống kê") → `output_mode=aggregate`.
5. Tham chiếu hội thoại ("còn", "nó", "thêm", "rẻ hơn") → `scope=continuation`.
6. Bỏ stopword khỏi `topic` ("tìm", "cho tôi", "gói thầu", "dự án", "ở", "tại", "năm").
7. Chỉ dùng giá trị trong `catalogs`; không biết thì để null, không bịa.
8. Muốn bỏ một điều kiện đã có từ lượt trước → ghi vào `clear`.

### 6.4 Validate (backend, bắt buộc)
- JSON hợp lệ theo schema; mã tỉnh, `bid_form`, `status`, `category` thuộc danh mục; ngày hợp lệ; `price_min ≤ price_max`.
- Giá trị lạ → bỏ khỏi filter (không bịa), nếu là điều kiện quan trọng thì hỏi lại.
- **Validate fail / timeout / JSON hỏng → chạy analyzer V3 (keyword)** để vẫn search được. Không crash.

### 6.5 Đường tắt (quyết định bằng số liệu)
Mặc định: LLM-first cho mọi câu không có mã. Chỉ thêm "cổng tín hiệu V3" làm đường tắt nếu bộ đánh giá cho thấy, trên các câu **không có tín hiệu**, V3 và LLM cho phân tích giống nhau từ ~95% trở lên. Không giữ hai đường song song khi chưa có số liệu.

---

## 7. Bước 4 — Thực thi

### 7.1 Gộp state (continuation)
```python
# pseudocode
merged = dict(prev_filters)
for k, v in new_filters.items():
    if v is not None:          # KHÔNG để null đè giá trị cũ
        merged[k] = v
for k in analysis.clear:       # chỉ xóa khi LLM yêu cầu rõ
    merged.pop(k, None)
topic = analysis.topic or prev_topic
```

### 7.2 Chọn method (code, không phải LLM)
```python
def choose_method(a):
    if a.code:       return "by_code"       # không thấy → rơi xuống hybrid
    if not a.topic:  return "filter_only"
    return "hybrid"                          # filter áp bên trong cả hai nhánh
```
`output_mode=aggregate/compare` chạy **cùng bộ filter** nhưng thao tác là aggregation (mục 8), không phải method search.

### 7.3 filter_only
- Query `bool.filter` + `sort` theo `sort` (mặc định `newest`; "sắp hết hạn" → `deadline_asc` **kèm `deadline >= now` và `status=open`**).
- Dùng `track_total_hits` để biết tổng số (phục vụ bước hỏi lại).
- Trả top 10 + tổng + (nếu quá nhiều) gợi ý thu hẹp.

### 7.4 hybrid
- **Filter áp ở cả hai nhánh, ngay trong query** (pre-filter), không lọc sau trong code.
- Nhánh BM25: `multi_match` trên `search_text^3`, `bidName^2`, `procuringEntityName`; `fuzziness: AUTO` chỉ cho từ ≥5 ký tự (`prefix_length: 2`); lấy **30–50** ứng viên.
- Nhánh vector: kNN với `k` 30–50, `num_candidates` ≈ 5×k, dùng tham số **`similarity`** (cosine thô, mặc định khởi điểm 0,45, chỉnh bằng bộ đánh giá). Nếu model yêu cầu tiền tố query/passage thì dùng đúng.
- Embedding của `topic` tính **một lần**, dùng lại cho mọi bước fallback.
- **RRF theo thứ hạng**, `rank_constant=60`, khóa theo `_id` của ES (không dùng `bidCode` nếu một mã có nhiều thông báo). Dùng `scores.get(id, 0)`.
- Giữ **~50 ứng viên đã xếp hạng** để phân trang; khi trả chỉ cắt xuống ít gói.

---

## 8. Thống kê và so sánh

**Nguyên tắc:** số do DB tính. Thống kê dùng **toàn bộ tập khớp filter**, không chỉ 10 gói đang hiện. Câu nối tiếp ("thống kê giúp tôi") dùng lại filter và topic từ state.

**Hai nhánh, không trộn:**

| Nhánh | Khi nào | Cách đếm | Cờ |
|---|---|---|---|
| Chính xác | Có `category` chuẩn hóa | `filter: term category` | `estimated: false` |
| Ước tính | Chỉ có `topic` | `must: match(search_text, operator: and)` | `estimated: true` |

Khi `estimated: true`, câu trả lời **bắt buộc** ghi rõ "ước tính theo từ khóa". Không trả số ước tính như số tuyệt đối.

**Aggregation theo địa điểm:**
- Dựa vào kết quả P1. Nếu `provCode` phẳng → `terms` đơn giản. Nếu nested → `nested` + `reverse_nested` (+ `cardinality` nếu cần đếm gói duy nhất).
- Gói nhiều địa điểm được tính ở nhiều tỉnh → tổng các tỉnh có thể vượt tổng thật; câu trả lời ghi chú điều này.
- Số bucket theo danh mục tỉnh (34, không phải 63).

**So sánh (giai đoạn đầu):** chỉ hỗ trợ **hai tỉnh** hoặc **hai năm**: chạy hai aggregation song song với cùng các filter còn lại. Các loại so sánh khác (hai chủ đề, hai gói cụ thể) → hỏi lại user.

---

## 9. Bước 5 — Xử lý kết quả (hybrid)

1. RRF → danh sách xếp hạng (~50).
2. **Rerank có điều kiện:** chỉ khi > 10 ứng viên **và** điểm sít nhau. Cách xác định "đã rõ": cả hai nhánh cùng xếp một gói ở top 1–2 thì **bỏ qua rerank**. (Không so tỷ lệ điểm RRF vì điểm RRF trải hẹp 0,01–0,03.)
3. Rerank trả về, theo `index`: `{index, relevant: true/false}`. Parse theo trường `index`, không theo vị trí mảng; thiếu thì mặc định `relevant=false`. Timeout/JSON hỏng → giữ thứ tự RRF.
4. **Cắt theo liên quan:**
   - Có nhãn rerank: giữ các gói `relevant=true`, tối đa 10.
   - Không có rerank: giữ các gói vượt ngưỡng `similarity` ở nhánh vector hoặc xuất hiện ở top của cả hai nhánh.
   - **Cho phép trả 0 gói** (kích hoạt hỏi lại). Không có luật "luôn giữ top 3".
5. Lưu vào session toàn bộ `ranked_ids` đã xếp hạng cuối cùng (kể cả phần chưa hiển thị) để phân trang.

---

## 10. Bước 6 — Fallback và hỏi lại

**Chẩn đoán khi 0 kết quả:** đếm số kết quả khi bỏ **từng** điều kiện (bao gồm cả `topic`), tìm điều kiện "chặn".

| Tình huống | Hành động |
|---|---|
| Điều kiện chặn là phụ (giá, `bid_form`) | Nới và **báo rõ**: "Không có gói nào dưới 5 tỷ; đã bỏ điều kiện giá, còn 134 gói" |
| Điều kiện chặn là cốt lõi (địa điểm, năm, topic) | **Hỏi lại**, gợi ý từ aggregation thật: "Hà Nội chưa có. Hải Phòng 12 gói, Quảng Ninh 8 gói. Anh/chị muốn xem khu vực nào?" |
| Quá nhiều kết quả (dùng `track_total_hits`, ngưỡng ~500) | Trả top 10 + hỏi thu hẹp theo lĩnh vực/khoảng giá/tỉnh |
| Không có topic và không có filter | Hỏi một câu để làm rõ |
| Phủ định ("không phải Hà Nội") | `must_not`, không bao giờ biến thành lọc ngược khi nới điều kiện |

Quy tắc:
- Mỗi lượt hỏi **một** điều, kèm lựa chọn nhanh.
- Tối đa **2 lượt hỏi liên tiếp**; sau đó trả cái tốt nhất có kèm giải thích.
- `clarification_count` **reset** khi user trả lời hoặc có kết quả.
- Khi user chọn mở rộng, **chỉ đổi điều kiện họ đồng ý**.
- Topic ≤ 1 từ **không** tự động coi là mơ hồ ("thuốc", "laptop" hợp lệ); chỉ hỏi lại khi không có cả topic lẫn filter.

---

## 11. Bước 7 — Trả lời

- **Thẻ gói thầu lấy trực tiếp từ DB** (mã, tên, đơn vị, giá, hạn, địa điểm, link). LLM chỉ viết đoạn dẫn và tóm tắt 3–5 gói nổi bật.
- Đưa cho LLM chỉ các trường cần thiết.
- **Kiểm tra số:** sau khi LLM viết, trích mọi con số/ngày trong câu trả lời, **parse thành giá trị** ("5,2 tỷ" = "5.200.000.000" = "5200 triệu") rồi đối chiếu với dữ liệu đầu vào. Lệch → bỏ đoạn LLM, chỉ trả thẻ (và ghi log).
- Luôn trả kèm điều kiện đang áp dụng ("Đang lọc: Hà Nội, 2024, dưới 5 tỷ") và danh sách điều kiện đã nới (nếu có).
- Dùng SSE: gửi thẻ/metadata trước, rồi stream đoạn dẫn.

---

## 12. Ngân sách thời gian và hạ cấp dần

| Tầng | Ngân sách khởi điểm | Khi quá hạn |
|---|---|---|
| Phân tích LLM | ~1,5 s | Dùng V3 |
| Search | ~1 s | Trả lỗi nhẹ, gợi ý thử lại |
| Rerank | ~2 s | Giữ thứ tự RRF |
| Viết câu trả lời | ~5 s (stream) | Chỉ trả thẻ gói thầu |

Các con số trên và các ngưỡng sau là **khởi điểm**, phải chỉnh bằng bộ đánh giá: số ứng viên mỗi nhánh (30–50), `similarity` (0,45), ngưỡng "quá nhiều" (500), điều kiện bỏ rerank, ngân sách thời gian.

---

## 13. Session state

```json
{
  "session_id": "",
  "last_query": "",
  "filters": {},
  "topic": "",
  "operation": "list | aggregate | compare",
  "ranked_ids": [],
  "offset": 0,
  "total_matched": 0,
  "relaxed": [],
  "clarification_count": 0,
  "updated_at": ""
}
```
Lưu Redis (hoặc collection riêng), TTL theo thời gian không hoạt động. Phục vụ: câu nối tiếp, phân trang không search lại, "so sánh chúng", "gói thứ 3 giá bao nhiêu".

---

## 14. Cache

- Khóa: câu hỏi **đã chuẩn hóa** (chữ thường, bỏ dấu câu) + tóm tắt state + **ngày hôm nay** (vì "tuần này" đổi theo ngày).
- Cache phân tích; cache rerank theo `(query, doc ids)`; hủy khi dữ liệu đổi.
- **Đo tỷ lệ trúng cache thật** trước khi tính tiết kiệm (người dùng ít gõ trùng câu).

---

## 15. Ghi log (bắt buộc, mỗi lượt)

`session_id`, câu hỏi gốc, JSON phân tích, cờ dùng V3 dự phòng, method, filter cuối cùng, các bước nới, số kết quả, có rerank không, số lần gọi LLM theo bước, độ trễ từng tầng, kết quả kiểm tra số, có hỏi lại không, feedback (thumbs). Log này là nguồn xây thêm bộ đánh giá từ lưu lượng thật.

---

## 16. Danh sách lỗi đã biết, phải tránh

1. Tách và mask mã trước khi trích filter; dùng ranh giới từ, không dùng `in`.
2. Trích **giá trước năm**; năm chỉ nhận trong khoảng hợp lý.
3. Stopword so theo **cụm trên văn bản có dấu**; bỏ stopword đơn lẻ như "o", "nam". Chuỗi gửi BM25/embedding giữ nguyên văn có dấu.
4. Bắt phủ định rộng tay: "không phải", "không ở", "ngoài", "trừ", "loại", "khác", "ngoại trừ".
5. kNN dùng `similarity`; coi "không có gói liên quan" là 0 kết quả.
6. "Sắp hết hạn" phải kèm `deadline >= now` và `status=open`.
7. Parse rerank theo trường `index`; lỗi thì giữ thứ tự RRF.
8. RRF: không để `KeyError` (`scores.get`), khóa theo `_id`.
9. Aggregate **không được bỏ qua topic**; phân biệt chính xác/ước tính.
10. Gộp filter: không để `null` đè giá trị cũ.
11. Cắt top-k **không** dựa vào điểm RRF; không dùng `len(results)` đã cắt để phát hiện "quá nhiều".
12. Ladder: không tự bỏ địa điểm; bước "bỏ price" bỏ qua nếu user dùng `price_min` mà code chỉ bỏ `price_max`.
13. Regex giá phải xử lý có dấu ("tỷ", "triệu"), "1,5 tỷ", "từ 2 tỷ đến 10 tỷ".
14. Alias địa danh ngắn ("HN") cần ranh giới từ; nhiều địa điểm là danh sách, không ghi đè.
15. Danh mục tỉnh 34 đơn vị, không còn 63.

---

## 17. Thứ tự triển khai và tiêu chí hoàn thành

| Giai đoạn | Việc | Hoàn thành khi |
|---|---|---|
| 0 | P1–P5 (mapping, danh mục tỉnh, bộ đánh giá, định dạng mã, category) | Có tài liệu mapping; bộ đánh giá ≥ 100 câu có đáp án |
| 1 | Sửa 5 lỗi của V3 (làm lưới dự phòng) + bộ chạy đánh giá | V3 chạy được trên bộ đánh giá, có số baseline |
| 2 | Phân tích LLM + schema + validate + dự phòng V3 | Tỷ lệ phân tích đúng (thao tác, filter) đo được; JSON hỏng không gây crash |
| 3 | Thực thi: gộp state, filter_only, by_code, hybrid (RRF, pre-filter, similarity) | Recall@10, MRR cao hơn baseline V3 |
| 4 | Rerank có điều kiện + cắt theo liên quan + pagination từ `ranked_ids` | "Thêm N gói" không search lại; có trường hợp trả 0 gói đúng |
| 5 | Thống kê (chính xác/ước tính), so sánh hai tỉnh/năm | Số khớp truy vấn đếm tay; câu trả lời ghi rõ ước tính |
| 6 | Fallback, hỏi lại, thẻ từ DB, kiểm tra số, ngân sách thời gian | Không còn câu trả lời "âm thầm sai"; hạ cấp đúng khi timeout |
| 7 | Cache, log, dashboard theo dõi | Có số p50/p95, tỷ lệ hỏi lại, số lần gọi LLM/câu |

**Chỉ số theo dõi xuyên suốt:** recall@10, MRR, tỷ lệ hỏi lại, tỷ lệ 0 kết quả, số lần gọi LLM mỗi câu, độ trễ p50/p95, tỷ lệ kiểm tra số thất bại.

---

## 18. Không làm ở giai đoạn này

- Không tách BM25/vector thành các method riêng (Hybrid là mặc định).
- Không dùng LLM tự chọn method hoặc tự viết query.
- Không fine-tune embedding, không cross-encoder tự host trước khi có số liệu chỉ ra cần.
- Không hỗ trợ so sánh ngoài hai tỉnh/hai năm.
- Không tư vấn pháp lý, không gợi ý "nên tham gia gói nào".
