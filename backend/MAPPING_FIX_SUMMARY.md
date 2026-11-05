# Fix 4 lỗi mapping nghiêm trọng - Hoàn thành

**Ngày fix**: 2026-11-02

## Tóm tắt

Đã sửa xong **4/5 lỗi mapping** được phát hiện từ audit index thật:

| # | Lỗi | Trạng thái | Kết quả |
|---|---|---|---|
| 1 | `deadline` không tồn tại | ✅ Fixed | Thay → `bidCloseDate`, sort OK |
| 2 | `bidCode` không tồn tại | ✅ Fixed | Thay → `bidId` (UUID, 96.4% unique) |
| 3 | Regex mã gói thầu sai | ✅ Fixed | `r'\b[A-Z]{2}\d{10}\b'` match `BP2200225863` |
| 4 | Province codes mất 90% | ✅ Fixed | Multi-code: Hà Nội 86k docs (12.8x từ 6.7k) |
| 5 | bidForm text vs code | ⏭️ Bỏ qua | Độ ưu tiên thấp |

---

## Chi tiết fix

### 1️⃣ Province Multi-Code Mapping (Lỗi #4 - nghiêm trọng nhất)

**Vấn đề**: Mỗi tỉnh có 2 hệ mã (cũ 2 số + mới 3 số), `provinces.json` chỉ có code cũ → mất 90% data.

**Fix**:
- Script `build_provinces_v2.py`: quét index thật, sinh `provinces_v2.json`
  - 67 tỉnh, 93 codes (6 codes unmapped là "Toàn quốc"/"Ngoài lãnh thổ")
  - Mỗi tỉnh → list codes: `{"Hà Nội": {"codes": ["101", "01", "213", "15"], ...}}`
- `location_service.py`: 
  - Method mới `get_province_codes(name) -> List[str]` trả TẤT CẢ codes
  - `get_province_code(name)` giữ backward compat (trả code đầu)
  - `get_province_name(code)` check trong list codes
- `intent_analyzer_v3.py`: `filters["location"] = prov_data["codes"]` (list thay vì string)
- `search_service.py`: `_build_filter_clauses()` dùng `terms` query thay vì `term`:
  ```python
  {"nested": {"path": "locations", "query": {"terms": {"locations.provCode": ["101", "01", "213", "15"]}}}}
  ```

**Test**:
```
Hà Nội (codes=['101', '01', '213', '15']): 86,371 docs
Chỉ code 01: 6,731 docs
Tăng 12.8x
```

---

### 2️⃣ deadline → bidCloseDate (Lỗi #1)

**Vấn đề**: V3 sort theo field `deadline` không tồn tại → crash `BadRequestError`.

**Fix**:
- `search_service.py`: `metadata_only_search()` thay:
  ```python
  sort = [{"bidCloseDate": "asc"}]  # thay vì deadline
  ```

**Test**:
```
Top 3 sắp hết hạn:
  2022-09-23T01:30:00 | BP2200094095 | Bốc xếp xuất 2.325 tấn gạo...
```
→ Sort OK, không crash.

---

### 3️⃣ bidCode → bidId (Lỗi #2)

**Vấn đề**: 
- V3 dùng `bidCode` (không tồn tại) → fallback về `bidName` (không unique)
- RRF merge trùng ID → kết quả sai

**Fix**:
- `search_service.py`: `hybrid_search_rrf()` RRF merge key:
  ```python
  doc_id = doc.get('bidId', doc.get('bidName'))  # bidId thay vì bidCode
  ```

**Test**:
```
Total docs: 526,472
Unique bidId: 507,725
Ratio: 0.9644 (gần 1.0 = unique)

Unique bidNo: 185,429 (nhiều gói cùng bidNo → không dùng)
```
→ bidId là primary key tốt (96.4% unique, `bidNo` chỉ 35%).

---

### 4️⃣ Regex mã gói thầu (Lỗi #3)

**Vấn đề**: V3 regex `(DT|DTXD|MSC|CHHC)-\d{4}-\d+` không match format thật → fast-path không bao giờ chạy.

**Fix**:
- `intent_analyzer_v3.py`: regex mới:
  ```python
  CODE_PATTERNS = [r'\b[A-Z]{2}\d{10}\b']  # BP2200225863
  ```

**Thực tế**:
- 63% docs có `bidNo` rỗng (334k/526k)
- Format thật: `BP2200225863` (2 chữ + 10 số)
- Cardinality bidNo 185k < 526k docs → có trùng

---

## Files đã sửa

1. ✅ `config/provinces_v2.json` — 67 tỉnh, 93 codes
2. ✅ `app/services/location_service.py` — load v2, method `get_province_codes()` trả list
3. ✅ `app/services/intent_analyzer_v3.py`:
   - Line 1: Comment `Fix 4 lỗi mapping`
   - Line 15: `code: Optional[str] = None  # bidNo (mã gói thầu)`
   - Line 28-30: Regex mới `r'\b[A-Z]{2}\d{10}\b'`
   - Line 94-111: Location extract trả `prov_data["codes"]` (list)
4. ✅ `app/services/search_service.py`:
   - Line 70-85: RRF merge dùng `bidId`
   - Line 94-95: Sort `bidCloseDate` thay vì `deadline`
   - Line 129-137: `_build_filter_clauses()` location filter dùng `terms` với list codes

---

## Lỗi #5 (bidForm) - Chưa fix

**Vấn đề**: Index có code (`DTRR`, `CHCT`), V3 regex tìm text (`"đấu thầu rộng rãi"`).

**Tại sao bỏ qua**:
- Độ ưu tiên thấp (filter phụ, không critical như location/deadline)
- Cần BIDFORM_MAP text→code, thêm complexity
- User chưa yêu cầu fix ngay

**Khi nào fix**: Khi đo metrics V4 thấy filter bidForm quan trọng.

---

## Next steps (theo work order)

1. ✅ Verify ES mapping thật
2. ✅ Fix 4/5 lỗi V3 + mapping
3. TODO: Dựng eval dataset 100-200 câu hỏi
4. TODO: Code V4 với validate, checks, timeouts
5. TODO: Đo metrics (recall@10, MRR, độ trễ)
6. TODO: Tune thresholds
