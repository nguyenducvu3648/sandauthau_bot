# Index Mapping Audit - 5 phát hiện nghiêm trọng

**Index**: `dauthaus_prod_526k` (526.472 docs)  
**Ngày kiểm tra**: 2026-11-02

## 🔴 1. Field `deadline` KHÔNG tồn tại → lỗi runtime

**Hiện trạng**:
- `search_service.py:95` sort theo `{"deadline": "asc"}`
- Index chỉ có `bidCloseDate` (date), không có `deadline`

**Hậu quả**: 
- Mỗi khi user hỏi "sắp hết hạn", ES trả `BadRequestError: No mapping found for [deadline]`
- Bot crash, không trả lời được

**Fix**: Thay mọi tham chiếu `deadline` → `bidCloseDate`

---

## 🔴 2. Field `bidCode` KHÔNG tồn tại → RRF merge sai

**Hiện trạng**:
- `search_service.py`, `intent_analyzer_v3.py` dùng `doc.get('bidCode', doc.get('bidName'))`
- Index chỉ có `bidId` (UUID), `bidNo` (mã thầu, 63% rỗng), `bidName` (tên, không unique)

**Hậu quả**:
- Fallback về `bidName` → nhiều gói cùng tên → RRF merge trùng ID → kết quả ít hơn dự kiến
- Session không lưu được danh sách ID chính xác

**Fix**: Thay `bidCode` → `bidId` làm primary key

---

## 🔴 3. Regex mã gói thầu V3 không match format thật → nhánh `bm25_code` chưa bao giờ chạy

**Hiện trạng**:
- V3: `(DT|DTXD|MSC|CHHC)-\d{4}-\d+` (ví dụ: `DT-2024-123`)
- Thật: `BP2200225863` (2 chữ + 10 số), 334.605/526.472 docs có `bidNo` rỗng

**Hậu quả**: 
- Fast-path mã gói thầu (0.01s) không bao giờ được kích hoạt
- Mọi câu hỏi đều đi qua phân tích chậm

**Fix**: 
1. Regex mới: `r'\b[A-Z]{2}\d{10}\b'` (match `BP2200225863`)
2. Search theo `bidNo` (keyword exact match)
3. Nếu `bidNo` rỗng → fallback về `bidId` term query

---

## 🔴 4. Filter địa điểm chỉ match ~8% dữ liệu → mất 90% kết quả

**Hiện trạng**:
- `provinces.json` dùng mã cũ 2 chữ số (`01`, `79`, `48`, ...)
- Index chứa **2 hệ mã** cho cùng tỉnh:

| Tỉnh | Code cũ | Docs | Code mới | Docs |
|---|---|---|---|---|
| Hà Nội | `01` | 6.731 | `101` | **77.113** |
| TP.HCM | `79` | 5.720 | `701` | **44.303** |
| Đà Nẵng | `48` | 1.272 | `501` | **9.616** |

- Thêm nữa: Hà Nội có `213`, `15`; một số tỉnh có 3-4 codes

**Hậu quả**: 
- User hỏi "gói thầu ở Hà Nội" chỉ trả 6.731 docs thay vì 77.113 (mất 91%)
- Aggregation theo tỉnh sai số nghiêm trọng

**Fix**:
1. Sinh `provinces_v2.json`: mỗi tỉnh → **tất cả codes** (script: `build_provinces_v2.py`)
2. Filter địa điểm dùng `terms` (array) thay vì `term` (single):
   ```python
   {"terms": {"locations.provCode": ["101", "01", "213", "15"]}}  # Hà Nội
   ```
3. 29 codes trong `provinces.json` không tồn tại trong ES → bỏ
4. 67 codes trong ES không có trong `provinces.json` → bổ sung

**Kết quả**: 67 đơn vị hành chính, 93/99 codes được map (6 codes là "Toàn quốc"/"Ngoài lãnh thổ")

---

## 🟡 5. `bidForm` là keyword code, V3 đang so text → không match

**Hiện trạng**:
- Index: `bidForm` = `DTRR` (305k), `CHCT` (192k), `CHCTRG` (22k), `CGTTRG`, `DTHC`, `CDTRG`, ...
- V3 regex: `"dau thau rong rai"`, `"chi dinh thau"`, `"mua sam truc tiep"`, `"chao hang canh tranh"`

**Hậu quả**: Không match được field keyword → filter `bidForm` không có tác dụng

**Fix**: Map text → code:
```python
BIDFORM_MAP = {
    "đấu thầu rộng rãi": "DTRR",
    "chào hàng cạnh tranh": "CHCT",
    "chào giá cạnh tranh": "CHCTRG",
    "chỉ định thầu": "CDT",
    # ...
}
```

---

## 🟢 Tin tốt

1. **`locations` đúng là nested** → filter hiện tại chạy đúng ✓
2. **`investField`** = `HH, XL, PTV, TV, HON_HOP, KHAC` → **đây là trường lĩnh vực chuẩn** để đếm aggregation chính xác (fix lỗi #2 trong review) ✓
3. **`search_text`** = `bidName | procuringEntityName` với analyzer `vi_search` + synonym ✓
4. **Embedding** = `dense_vector` 384-dim, `cosine` similarity ✓

---

## Độ ưu tiên fix

| # | Lỗi | Nghiêm trọng | Ảnh hưởng | Fix ngay |
|---|---|---|---|---|
| 1 | `deadline` không tồn tại | **Cao** | Crash runtime mỗi khi sort "sắp hết hạn" | ✅ |
| 4 | Filter địa điểm mất 90% | **Cao** | Kết quả sai nghiêm trọng | ✅ |
| 2 | `bidCode` không tồn tại | Trung bình | RRF merge sai, session lỗi | ✅ |
| 3 | Regex mã gói thầu sai | Trung bình | Fast-path không chạy, tốn LLM | ✅ |
| 5 | `bidForm` text vs code | Thấp | Filter hình thức đấu thầu không hoạt động | ⏭️ sau |

---

## Files cần sửa

1. ✅ `config/provinces_v2.json` — đã sinh (67 tỉnh, 93 codes)
2. `app/services/location_service.py` — load `provinces_v2.json`, trả **list codes** thay vì 1 code
3. `app/services/intent_analyzer_v3.py`:
   - Thay `deadline` → `bidCloseDate`
   - Thay `bidCode` → `bidId`
   - Regex mã: `r'\b[A-Z]{2}\d{10}\b'`
   - Filter location: `terms` thay vì `term`
   - Map `bidForm` text → code
4. `app/services/search_service.py`:
   - Thay `deadline` → `bidCloseDate`
   - Thay `bidCode` → `bidId`
   - `_build_filter_clauses`: location filter dùng `terms` + list codes
   - RRF merge key: `bidId`
5. `app/services/session_store.py` — `_doc_id`: dùng `bidId`

---

## Test sau khi fix

```bash
# 1. Filter Hà Nội phải trả ~77k docs
curl -X POST "localhost:9200/dauthaus_prod_526k/_search" -H 'Content-Type: application/json' -d'
{"size":0,"track_total_hits":true,"query":{"nested":{"path":"locations","query":{"terms":{"locations.provCode":["101","01","213","15"]}}}}}'

# 2. Sort bidCloseDate phải OK
curl -X POST "localhost:9200/dauthaus_prod_526k/_search" -H 'Content-Type: application/json' -d'
{"size":1,"sort":[{"bidCloseDate":"asc"}]}'

# 3. Term query bidNo exact
curl -X POST "localhost:9200/dauthaus_prod_526k/_search" -H 'Content-Type: application/json' -d'
{"size":1,"query":{"term":{"bidNo":"BP2200225863"}}}'
```

Kết quả: (1) ~77k, (2) OK, (3) 1 hit ✓
