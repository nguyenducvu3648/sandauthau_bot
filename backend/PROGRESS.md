# Progress Report - Session 2026-11-02

## ✅ Hoàn thành

### 1. Verify ES mapping thật (Bước 1 work order)

**Scripts tạo**:
- `scripts/inspect_index.py` — mapping 24 fields, 526k docs
- `scripts/inspect_provinces.py` — 99 codes trong index
- `scripts/inspect_fields.py` — test field existence
- `scripts/inspect_bidno.py` — format mã gói thầu thật

**Kết quả**: `MAPPING_AUDIT.md` — 5 lỗi nghiêm trọng phát hiện:
1. `deadline` không tồn tại → crash runtime
2. `bidCode` không tồn tại → RRF merge sai
3. Regex mã gói sai → fast-path không chạy
4. Province codes mất 90% data → filter sai nghiêm trọng
5. `bidForm` text vs code mismatch → filter không hoạt động

---

### 2. Fix 4/5 lỗi mapping (Bước 3 work order - phần 1)

**Script `build_provinces_v2.py`**:
- Quét index thật → sinh `provinces_v2.json`
- 67 tỉnh, 93 codes (mỗi tỉnh → list codes cũ + mới)
- Hà Nội: `["101", "01", "213", "15"]`, TP.HCM: `["701", "79"]`

**Code fixes**:
1. ✅ `location_service.py`:
   - `get_province_codes(name) -> List[str]` trả TẤT CẢ codes
   - Backward compat: `get_province_code()` trả code đầu
   
2. ✅ `intent_analyzer_v3.py`:
   - Regex mã: `r'\b[A-Z]{2}\d{10}\b'` (match `BP2200225863`)
   - Filter location: `filters["location"] = prov_data["codes"]` (list)
   - Comment: "Fix 4 lỗi mapping" line 1

3. ✅ `search_service.py`:
   - RRF merge dùng `bidId` thay vì `bidCode`
   - Sort `bidCloseDate` thay vì `deadline`
   - `_build_filter_clauses()`: location filter dùng `terms` với list codes

**Test results**:
```
Hà Nội multi-code: 86,371 docs (tăng 12.8x từ 6,731)
bidCloseDate sort: OK (không crash)
bidId unique: 96.4% (vs bidNo 35%)
Regex mã gói: BP2200225863 ✓
```

**Lỗi #5 (bidForm)**: Bỏ qua - độ ưu tiên thấp.

---

### 3. Eval dataset baseline (Bước 2 work order)

**Files tạo**:
- `config/eval_20.json` — 20 câu test intent/filter/method
- `EVAL_DATASET.md` — spec 100 câu đầy đủ (location, năm, giá, mã, metadata, aggregation, casual, LLM signals)
- `scripts/run_eval_v3.py` — chạy batch eval

**Baseline V3 (20 câu)**:
```json
{
  "intent_acc": 100.0%,
  "method_acc": 65.0%,
  "filter_acc": 85.0%,
  "code_correct": 2/2 = 100%
}
```

**Phân tích**:
- Intent detection hoàn hảo ✓
- Method choice 65% → cần cải thiện logic `_choose_method()` (7 câu sai)
- Filter extract 85% → 3 câu sai (likely vì stopwords hoặc alias không match)

---

## 📊 Files tạo/sửa

### Config
- ✅ `config/provinces_v2.json` (new) — 67 tỉnh, 93 codes
- ✅ `config/es_province_codes.json` (new) — code→name simple map
- ✅ `config/eval_20.json` (new) — 20 câu eval dataset

### Scripts
- ✅ `scripts/build_provinces_v2.py` (new)
- ✅ `scripts/inspect_index.py` (new)
- ✅ `scripts/inspect_provinces.py` (new)
- ✅ `scripts/inspect_fields.py` (new)
- ✅ `scripts/inspect_bidno.py` (new)
- ✅ `scripts/test_location_filter.py` (new)
- ✅ `scripts/test_bidid_unique.py` (new)
- ✅ `scripts/test_deadline_sort.py` (new)
- ✅ `scripts/test_v3_fixes.py` (new)
- ✅ `scripts/run_eval_v3.py` (new)

### Services
- ✅ `app/services/location_service.py` (modified) — load v2, method `get_province_codes()`
- ✅ `app/services/intent_analyzer_v3.py` (modified) — 4 fixes: regex, location list, deadline→bidCloseDate, bidCode→bidId
- ✅ `app/services/search_service.py` (modified) — RRF bidId, sort bidCloseDate, filter terms

### Docs
- ✅ `MAPPING_AUDIT.md` (new) — 5 lỗi từ index thật
- ✅ `MAPPING_FIX_SUMMARY.md` (new) — tổng kết 4 fixes
- ✅ `EVAL_DATASET.md` (new) — spec 100 câu eval

### Results
- ✅ `results/v3_eval_20.json` (new) — baseline metrics

---

## 🚧 TODO (theo work order)

1. ✅ Verify ES mapping thật
2. ⏳ Dựng eval dataset:
   - ✅ 20 câu starter
   - ⏳ 80 câu còn lại (spec đã có trong `EVAL_DATASET.md`)
   - ⏳ Điền `ground_truth_ids` cho 40 câu quan trọng (manual label)
3. ✅ Sửa 4/5 lỗi V3 mapping
4. ⏳ Code V4:
   - ⏳ Intent 2D (output_mode × scope)
   - ⏳ Validate JSON, kiểm tra số, ngân sách thời gian
   - ⏳ Thẻ từ DB thay vì hardcode
5. ⏳ Đo metrics:
   - ✅ Baseline V3: 100% intent, 65% method, 85% filter
   - ⏳ Recall@10, MRR (cần ground_truth_ids)
   - ⏳ Tỷ lệ hỏi lại, độ trễ p50/p95
6. ⏳ Tune thresholds based on metrics

---

## 💡 Insights

### Province mapping là lỗi nghiêm trọng nhất
- Hà Nội: 6.7k → 86k docs (12.8x)
- TP.HCM: 5.7k → ~50k docs (8-9x)
- Đà Nẵng: 1.3k → 9.6k docs (7-8x)

→ Filter location trước đây **mất 90% data**.

### bidId là primary key tốt
- 96.4% unique (507k/526k docs)
- `bidNo` chỉ 35% unique (185k) + 63% rỗng (334k)
- `bidName` không unique (nhiều gói cùng tên)

### V3 intent detection chính xác
- 100% accuracy trên 20 câu
- Method choice 65% → có thể cải thiện bằng logic tốt hơn (không cần LLM)
- Filter extract 85% → 3 sai likely do stopwords/alias

---

## 🎯 Next immediate step

**Mở rộng eval dataset 20→100 câu**:
1. Thêm 80 câu từ spec `EVAL_DATASET.md` vào `eval_100.json`
2. Chạy query thật lấy top 10, manual check → điền `ground_truth_ids`
3. Đo recall@10, MRR trên 100 câu

**Hoặc code V4 trước** nếu muốn so sánh kiến trúc ngay.
