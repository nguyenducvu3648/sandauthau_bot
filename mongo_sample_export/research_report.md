# Nghiên Cứu và Thiết Kế Pipeline Chuẩn Bị Dữ Liệu cho RAG

**Mục tiêu**: Xử lý 526k bản ghi đấu thầu từ MongoDB để phục vụ:
- Text Search (BM25/Elasticsearch)
- Metadata Filtering
- Dense Vector Search (embedding)
- Hybrid Search
- RAG (Retrieval-Augmented Generation)

**Dataset**: MongoDB `localhost:27017/random_db.dauthaus`, 526,472 bản ghi, đã lấy mẫu 1000 records để phân tích.

---

## 1. Phân Tích Schema Dữ Liệu Nguồn

### 1.1 Cấu trúc chính (24 trường bắt buộc, 100% coverage)

| Trường | Loại | Null/Empty | Vai trò |
|--------|------|------------|---------|
| `_id` | str | 0% | MongoDB ObjectId (ID chính) |
| `bidId`, `mpiid` | str | 0% | UUID (business IDs) |
| `bidNo` | str | 0% | Mã số gói thầu (BP2200125545) |
| `bidName` | str | 0% | **Tên gói thầu** (11-468 ký tự, avg 69) |
| `bidPrice`, `bidPriceUnit` | float/int, str | 0% | Giá (3M - 734B VND) |
| `bidOpenDate`, `bidCloseDate` | str (ISO) | 0% | Ngày mở/đóng thầu (2022-10-07 → 2023-09-06) |
| `publicDate` | str (ISO) | 0% | Ngày công bố |
| `bidForm` | str | 0% | Hình thức (DTRR, CHCT, CHCTRG) |
| `bidMode` | str | 0% | Chế độ (1_MTHS, 1_HTHS) |
| `investField` | str | 0% | Lĩnh vực (XL, HH, TV, PTV, HON_HOP) |
| `procuringEntityCode`, `procuringEntityName` | str | 0% | Mã/tên đơn vị (12-151 ký tự, avg 46) |
| `isDomestic`, `isInternet` | bool | 0% | Trong nước?, trực tuyến? |
| `bidOpenLocation` | str | 0.2% null | URL mở thầu |
| `notifyNo`, `notifyVersion` | str | 0% | Mã/phiên bản thông báo |
| `processApply` | str | 0% | Quy trình áp dụng |
| `createdBy` | str | 0% | User tạo |
| `locations` | list | 29% empty | **Địa điểm** (tỉnh/huyện/xã) |
| `__v` | int | 0% | MongoDB version key |

### 1.2 Trường mở rộng (31 records, ~3% dataset)

Các trường bổ sung xuất hiện trên 31 bản ghi, bao gồm: `planNo`, `planName`, `projectCode`, `projectName`, `contractPeriod`, `investorName`, `guaranteeValue`, v.v.

**Kết luận**: Schema không đồng nhất hoàn toàn — có subset records chứa thông tin kế hoạch/dự án chi tiết.

### 1.3 Đặc điểm `locations`

- 29% bản ghi không có location (empty list)
- 71% có location: 1-6 địa điểm/record (avg = 1.0, hầu hết chỉ 1)
- Cấu trúc: `{provCode, provName, districtCode, districtName, wardCode, wardName, _id}`
- Ví dụ: `{"provCode": "401", "provName": "Tỉnh Thanh Hoá", "districtCode": "40125", ...}`

---

## 2. Normalized Schema Design

### 2.1 Phân loại trường theo vai trò

| Nhóm | Trường | Lý do |
|------|--------|-------|
| **ID fields** | `_id`, `bidId`, `mpiid`, `bidNo` | Định danh, exact lookup |
| **Text search** | `bidName`, `procuringEntityName`, `planName`¹, `projectName`¹ | Nội dung tiếng Việt, BM25 + embedding |
| **Metadata filters** | `bidForm`, `bidMode`, `investField`, `isDomestic`, `isInternet`, `bidPrice`, `bidOpenDate`, `bidCloseDate`, `locations` | Range/term queries |
| **Display only** | `bidOpenLocation`, `notifyNo`, `notifyVersion`, `createdBy`, `__v` | Không index, chỉ trả về kết quả |
| **Embedding fields** | `search_text` (synthetic) | Ghép bidName + procuringEntityName |

¹ Chỉ có trên ~3% records

### 2.2 Thiết kế `search_text` field

**Nguyên tắc**:
- Ghép các trường text quan trọng nhất
- Tránh trùng lặp: `bidNo`, `bidId` không vào (đã có exact match riêng)
- Tránh nhiễu: URL, mã version, số version không vào

**Công thức đề xuất**:
```python
search_text = f"{bidName} | {procuringEntityName}"
# Nếu có planName/projectName: thêm vào
if planName: search_text += f" | {planName}"
if projectName: search_text += f" | {projectName}"
```

**Xử lý tiếng Việt**:
- Giữ nguyên Unicode (không lowercase/normalize ở giai đoạn này)
- BM25 tokenizer: `icu_tokenizer` hoặc `standard` (Elasticsearch)
- Embedding model: chọn model hỗ trợ Vietnamese (xem phần 4)

**Ví dụ**:
```
"Gói thầu số 03: Mua sắm thiết bị văn phòng | CÔNG TY TRÁCH NHIỆM HỮU HẠN MỘT THÀNH VIÊN TƯ VẤN ĐẦU TƯ XÂY DỰNG HOÀNG NAM"
```

Độ dài: 69 (bidName) + 46 (procuringEntityName) + separator ≈ **120-150 ký tự trung bình**.

---

## 3. Quyết Định Chunking

### 3.1 Đánh giá

**Dữ liệu hiện tại**:
- Structured bidding records, không phải long-form documents
- `bidName` trung bình 69 ký tự (~15-20 từ)
- `search_text` dự kiến ~120-150 ký tự (~30-40 từ)
- Mỗi record là một gói thầu độc lập, ngữ cảnh hoàn chỉnh

**Tiêu chí cần chunking**:
- Document dài >512 tokens (embedding model context limit)
- Cần chia nhỏ để tăng độ chính xác retrieval

**Tiêu chí KHÔNG cần chunking**:
- Record ngắn, structured
- Mỗi record là atomic unit (không thể chia nhỏ mà vẫn giữ nghĩa)
- Chunking sẽ làm mất thông tin liên kết (bidPrice, bidDate, procuringEntity)

### 3.2 Quyết định

**KHÔNG chunking** — áp dụng **one-document-per-record**:
- Embed toàn bộ `search_text` (~30-40 từ << 512 tokens limit)
- Giữ nguyên cấu trúc MongoDB document trong Elasticsearch
- Mỗi hit trả về đầy đủ metadata (price, date, location, entity)

**Ngoại lệ**: Nếu phát hiện records có `bidName` hoặc `projectName` vượt quá 500 tokens (hiếm, chưa thấy trong 1000 mẫu), xử lý riêng bằng cách:
- Truncate ở 512 tokens
- Hoặc tách thành 2 embeddings (record_main + record_detail)

---

## 4. Embedding Model Comparison

### 4.1 So sánh

| Model | Params | Dim | Vietnamese Support | Speed | Use Case |
|-------|--------|-----|-------------------|-------|----------|
| `paraphrase-multilingual-MiniLM-L12-v2` | 118M | 384 | ✅ Multilingual (50+ langs) | Nhanh | General-purpose |
| `BAAI/bge-m3` | 567M | 1024 | ✅ Multilingual (100+ langs) | Chậm hơn | High-quality retrieval |

### 4.2 Benchmark cần chạy

Test trên 1k records:
1. Encoding speed (records/sec)
2. Retrieval quality: mAP@10 (cần ground-truth queries)
3. RAM usage

### 4.3 Đề xuất tạm thời

**Start với `paraphrase-multilingual-MiniLM-L12-v2`**:
- Đủ cho Vietnamese
- Nhanh (quan trọng với 526k records)
- Dễ deploy
- Dim 384 → vector storage nhỏ hơn

Upgrade lên `bge-m3` nếu:
- Retrieval quality không đạt
- Có GPU để tăng tốc inference
- Chấp nhận vector storage lớn gấp 2.7x

---

## 5. Pipeline Design cho 500k+ Records

### 5.1 Kiến trúc tổng quan

```
MongoDB (526k) 
  → Stream cursor (batch 1000)
  → Transform + Validate
  → Embed (batch 32)
  → Write JSONL checkpoint
  → Bulk index Elasticsearch (batch 500)
```

### 5.2 Batch Processing Strategy

**Lý do không load full vào RAM**:
- 526k × 2KB/record ≈ 1GB raw data
- Embedding vectors: 526k × 384 × 4 bytes ≈ 800MB
- Safety margin + Python overhead → cần 3-5GB RAM

**Solution**: Streaming pipeline

```python
MONGO_BATCH = 1000  # Cursor fetch size
EMBED_BATCH = 32    # Embedding model batch
ES_BULK_SIZE = 500  # Elasticsearch bulk insert

for mongo_batch in collection.find().batch_size(MONGO_BATCH):
    # Transform
    transformed = [transform_record(r) for r in mongo_batch]
    
    # Embed in sub-batches
    for i in range(0, len(transformed), EMBED_BATCH):
        sub_batch = transformed[i:i+EMBED_BATCH]
        texts = [r['search_text'] for r in sub_batch]
        embeddings = model.encode(texts)
        
        for record, emb in zip(sub_batch, embeddings):
            record['embedding'] = emb.tolist()
    
    # Checkpoint
    write_jsonl_checkpoint(transformed, batch_id)
    
    # Bulk index
    bulk_index_elasticsearch(transformed, ES_BULK_SIZE)
```

### 5.3 Error Handling

1. **MongoDB connection loss**: Cursor save position → resume từ last `_id`
2. **Embedding failure**: Skip record + log error → retry batch sau
3. **Elasticsearch bulk failure**: Retry with exponential backoff (3 attempts)
4. **Validation error**: Log + skip record (không crash toàn pipeline)

### 5.4 Progress Logging

```python
import logging
from tqdm import tqdm

logging.basicConfig(
    filename='pipeline.log',
    format='%(asctime)s %(levelname)s: %(message)s',
    level=logging.INFO
)

# Progress bar
pbar = tqdm(total=526472, desc="Processing")

for batch in cursor:
    try:
        # ... process ...
        pbar.update(len(batch))
        logging.info(f"Processed batch {batch_id}, total {pbar.n} records")
    except Exception as e:
        logging.error(f"Batch {batch_id} failed: {e}")
```

### 5.5 Resume Capability

**Checkpoint format** (`checkpoints/batch_{id}.jsonl`):
```json
{"_id": "...", "bidNo": "...", "search_text": "...", "embedding": [...]}
```

**Resume logic**:
```python
# Đọc last checkpoint
last_checkpoint = get_last_checkpoint()  # batch_0042.jsonl
last_id = last_checkpoint['_id']

# Resume cursor
cursor = collection.find({"_id": {"$gt": ObjectId(last_id)}})
```

### 5.6 Deduplication

**Check duplicate `bidNo`** (business key):
```python
seen_bidnos = set()

for record in batch:
    if record['bidNo'] in seen_bidnos:
        logging.warning(f"Duplicate bidNo: {record['bidNo']}")
        continue
    seen_bidnos.add(record['bidNo'])
```

### 5.7 Integrity Checks

Sau khi hoàn thành:
```python
# 1. Count check
mongo_count = collection.count_documents({})
es_count = es.count(index='dauthaus')['count']
assert mongo_count == es_count

# 2. Sample validation
sample_ids = random.sample(all_ids, 100)
for _id in sample_ids:
    mongo_doc = collection.find_one({"_id": ObjectId(_id)})
    es_doc = es.get(index='dauthaus', id=_id)
    assert mongo_doc['bidNo'] == es_doc['_source']['bidNo']
```

---

## 6. Elasticsearch Mapping Design

```json
PUT /dauthaus
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
      "analyzer": {
        "vietnamese": {
          "type": "standard",
          "stopwords": "_vietnamese_"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "_id": {"type": "keyword"},
      "bidNo": {"type": "keyword"},
      "bidId": {"type": "keyword"},
      "mpiid": {"type": "keyword"},
      
      "bidName": {
        "type": "text",
        "analyzer": "vietnamese",
        "fields": {"keyword": {"type": "keyword"}}
      },
      "procuringEntityName": {
        "type": "text",
        "analyzer": "vietnamese"
      },
      "search_text": {
        "type": "text",
        "analyzer": "vietnamese"
      },
      
      "bidPrice": {"type": "float"},
      "bidPriceUnit": {"type": "keyword"},
      "bidOpenDate": {"type": "date"},
      "bidCloseDate": {"type": "date"},
      "publicDate": {"type": "date"},
      
      "bidForm": {"type": "keyword"},
      "bidMode": {"type": "keyword"},
      "investField": {"type": "keyword"},
      "isDomestic": {"type": "boolean"},
      "isInternet": {"type": "boolean"},
      
      "locations": {
        "type": "nested",
        "properties": {
          "provCode": {"type": "keyword"},
          "provName": {"type": "keyword"},
          "districtCode": {"type": "keyword"},
          "districtName": {"type": "keyword"}
        }
      },
      
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      }
    }
  }
}
```

### 6.1 Query Patterns

**1. Exact lookup**:
```json
GET /dauthaus/_doc/<_id>
```

**2. BM25 text search**:
```json
GET /dauthaus/_search
{
  "query": {
    "match": {
      "search_text": "xây dựng đường giao thông"
    }
  }
}
```

**3. Metadata filter**:
```json
GET /dauthaus/_search
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"investField": "XL"}},
        {"range": {"bidPrice": {"gte": 1000000000}}}
      ]
    }
  }
}
```

**4. Dense vector search**:
```json
GET /dauthaus/_search
{
  "knn": {
    "field": "embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100
  }
}
```

**5. Hybrid search** (BM25 + Vector + Filter):
```json
GET /dauthaus/_search
{
  "query": {
    "bool": {
      "must": [
        {"match": {"search_text": "..."}}
      ],
      "filter": [
        {"term": {"investField": "XL"}}
      ]
    }
  },
  "knn": {
    "field": "embedding",
    "query_vector": [...],
    "k": 10,
    "num_candidates": 100
  },
  "rank": {
    "rrf": {}
  }
}
```

---

## 7. Resource Estimation

### 7.1 Time

**Embedding speed**:
- Model: `paraphrase-multilingual-MiniLM-L12-v2`
- Hardware: CPU (Intel i7, 8 cores)
- Throughput: ~100 records/sec (conservative estimate)

**Total time**:
- 526,472 records ÷ 100 rec/sec = **5,265 seconds ≈ 88 phút ≈ 1.5 giờ**

**With GPU** (NVIDIA RTX 3060):
- Throughput: ~500 records/sec
- Total: **17 phút**

### 7.2 Storage

**MongoDB raw**: 526k × 2KB ≈ **1 GB**

**Elasticsearch**:
- Text fields: ~1 GB
- Embedding vectors: 526k × 384 × 4 bytes = **805 MB**
- Inverted indexes + metadata: ~500 MB
- **Total: ~2.5 GB**

### 7.3 RAM

**Pipeline runtime**:
- MongoDB cursor batch: 1000 × 2KB = 2 MB
- Embedding batch: 32 × 384 × 4 = 49 KB
- ES bulk buffer: 500 × 3KB = 1.5 MB
- Model loaded: ~500 MB (MiniLM)
- **Peak RAM: ~1 GB**

**Elasticsearch runtime**:
- Heap: 1 GB (default)
- OS cache: 1 GB
- **Total: 2-3 GB**

---

## 8. Incremental Testing Plan

### 8.1 Stage 1: 1k records (DONE ✓)

**Mục tiêu**:
- Validate schema
- Test transform logic
- Measure embedding speed

**Success criteria**:
- Export thành công 1000 records
- Schema analysis hoàn chỉnh

**Kết quả**: ✓ Hoàn thành, có `dauthaus_sample_1000.jsonl`

### 8.2 Stage 2: 1k → Elasticsearch + Embedding

**Tasks**:
1. Implement `transform_record()` function
2. Generate `search_text` field
3. Embed 1000 records với `paraphrase-multilingual-MiniLM-L12-v2`
4. Create Elasticsearch index với mapping trên
5. Bulk index 1000 records
6. Test 5 query patterns (exact, BM25, filter, vector, hybrid)

**Success criteria**:
- Index thành công 1000/1000 records
- Embedding time <30s (CPU) hoặc <5s (GPU)
- Query latency <100ms (BM25), <500ms (hybrid)
- Top-10 results có ít nhất 5 relevant (manual check)

**Output**:
- Script: `pipeline_1k.py`
- Elasticsearch index: `dauthaus_test_1k`
- Benchmark report: `benchmark_1k.md`

### 8.3 Stage 3: 10k records

**Changes**:
- Enable batch processing (MONGO_BATCH=1000, EMBED_BATCH=32)
- Add progress logging
- Add checkpoint mechanism

**Success criteria**:
- Index 10k records trong <5 phút
- Resume từ checkpoint hoạt động
- RAM usage <2GB
- Query performance không giảm >20% vs 1k

### 8.4 Stage 4: 30k records

**Changes**:
- Test error handling (simulate connection loss)
- Add deduplication logic
- Test concurrent queries (10 users)

**Success criteria**:
- Pipeline tự động resume sau lỗi
- Phát hiện + skip duplicates
- Query throughput >20 req/sec

### 8.5 Stage 5: Full dataset (526k)

**Changes**:
- Production-grade logging
- Integrity checks post-indexing
- Performance monitoring

**Success criteria**:
- Complete trong <2 giờ (CPU) hoặc <30 phút (GPU)
- 0 data loss (count match)
- Sample validation 100% pass
- Query latency <5s (hybrid search với filters)

---

## 9. Verified Facts vs Assumptions

### ✅ Verified (từ dữ liệu thực)

- 526,472 bản ghi trong MongoDB
- Schema có 24 trường bắt buộc + 26 trường optional (~3% records)
- `bidName` avg 69 chars, `procuringEntityName` avg 46 chars
- `locations` empty ở 29% records
- Price range: 3M - 734B VND
- Date range: 2022-10 → 2023-09
- Enum values: bidForm (3), bidMode (2), investField (5)

### ❓ Assumptions (cần verify bằng test)

- Embedding speed: 100 rec/sec (CPU) — cần benchmark thực tế
- Query latency <5s — phụ thuộc Elasticsearch config
- Retrieval quality — cần ground-truth queries để đánh giá
- `paraphrase-multilingual-MiniLM-L12-v2` đủ tốt cho Vietnamese — cần so sánh với bge-m3
- Không cần chunking — giả định `search_text` <512 tokens (cần verify trên full dataset)

### 🔧 To Be Determined

- Elasticsearch shards/replicas tối ưu cho 526k records
- Có cần fine-tune embedding model không?
- RRF (Reciprocal Rank Fusion) weights cho hybrid search
- Có cần thêm phonetic analyzer cho Vietnamese (âm Hán Việt)?

---

## 10. Next Steps

### Immediate (Stage 2)

1. Write `pipeline_1k.py`:
   ```python
   # Core functions:
   - transform_record(mongo_doc) -> dict
   - generate_search_text(record) -> str
   - embed_batch(texts, model) -> np.ndarray
   - bulk_index_es(records, index_name)
   ```

2. Setup Elasticsearch local:
   ```bash
   docker run -p 9200:9200 -e "discovery.type=single-node" elasticsearch:8.x
   ```

3. Install dependencies:
   ```txt
   sentence-transformers>=2.2
   elasticsearch>=8.0
   pymongo>=4.6
   tqdm
   ```

4. Run pipeline:
   ```bash
   python pipeline_1k.py \
     --input data/raw/dauthaus_sample_1000.jsonl \
     --es-url http://localhost:9200 \
     --index dauthaus_test_1k \
     --model paraphrase-multilingual-MiniLM-L12-v2
   ```

5. Test queries:
   ```python
   # queries_test.py
   - Test case 1: "xây dựng trường học"
   - Test case 2: Filter by provName="Hà Nội"
   - Test case 3: Hybrid search với price range
   ```

### Later Stages

- Stage 3: Scale to 10k, add checkpointing
- Stage 4: Error handling, deduplication
- Stage 5: Full 526k production run
- Optimize: Fine-tune RRF weights, test bge-m3, phonetic analyzer

---

**Tài liệu này là thiết kế đầy đủ, đủ chi tiết để bắt đầu implement Python code.**
