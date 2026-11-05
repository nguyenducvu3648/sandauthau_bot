# Frontend Test UI

UI đơn giản để test backend Tender Search.

## Features

- **2-panel layout**: Search results (trái) vs RAG answer (phải)
- **Auto Search**: Intelligent routing với intent analysis
- **RAG Streaming**: Real-time answer generation
- **Session tracking**: Tự động track user context
- **Metadata display**: Intent, methods, filters, latency

## Chạy

### Option 1: Python HTTP Server (khuyến nghị)

```bash
cd frontend
python -m http.server 3000
```

Mở: http://localhost:3000

### Option 2: Mở trực tiếp file

```bash
# Windows
start index.html

# Mac
open index.html

# Linux
xdg-open index.html
```

**Lưu ý**: Option 2 có thể gặp CORS error. Dùng Option 1 an toàn hơn.

## Sử dụng

### 1. Auto Search (JSON Response)

- Nhập query: "xây dựng cầu Hà Nội"
- Click **Auto Search**
- Kết quả:
  - Panel trái: Metadata + 10 docs
  - Panel phải: Rỗng (chưa có answer)

### 2. RAG Answer (Streaming)

- Nhập query: "tìm gói thầu xây dựng ở Hà Nội"
- Click **RAG Answer**
- Kết quả:
  - Panel trái: Metadata + docs (từ streaming metadata)
  - Panel phải: Answer streaming real-time + citations

### 3. Session Context

- Session ID tự động generate (hiển thị trên cùng)
- Backend track frequent filters & interests
- Sau vài queries về "Hà Nội", backend tự động apply filter này

## API Endpoints

Frontend gọi đến:
- `POST /search/auto` - Auto search
- `POST /search/answer` - RAG streaming (SSE)

Base URL: `http://localhost:8000` (config trong `app.js`)

## Troubleshooting

### CORS Error

Backend cần enable CORS cho frontend. Check `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # OK cho local test
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Backend không chạy

```bash
cd backend
uvicorn app.main:app --reload
```

Check: http://localhost:8000/health

### SSE không stream

Browser network tab → check response type là `text/event-stream`

## Test Cases

### Queries đơn giản:
- "xây dựng cầu"
- "mua thiết bị y tế"
- "cung cấp văn phòng phẩm"

### Queries có metadata:
- "xây dựng cầu Hà Nội 2024"
- "mua thiết bị y tế TP.HCM"
- "đấu thầu rộng rãi Đà Nẵng"

### Queries phức tạp:
- "tìm gói thầu xây dựng cơ sở hạ tầng giao thông giá trị cao"
- "các dự án y tế công năm 2024 tại miền Bắc"

### Casual queries:
- "xin chào"
- "cảm ơn"
- "bạn là ai"

## Screenshots

### Auto Search
```
┌─────────────────────┬─────────────────────┐
│ 📄 Search Results   │ 💡 RAG Answer       │
├─────────────────────┼─────────────────────┤
│ Metadata:           │                     │
│ - Total: 15 docs    │  (Chưa có câu trả   │
│ - Latency: 234ms    │   lời)              │
│ - Intent: search    │                     │
│ - Methods: filter   │                     │
│                     │                     │
│ [1] Gói thầu ABC    │                     │
│ - Score: 0.892      │                     │
│ - Đơn vị: ...       │                     │
│ ...                 │                     │
└─────────────────────┴─────────────────────┘
```

### RAG Answer (Streaming)
```
┌─────────────────────┬─────────────────────┐
│ 📄 Search Results   │ 💡 RAG Answer       │
├─────────────────────┼─────────────────────┤
│ Metadata:           │ Tôi tìm thấy 15 gói │
│ - Total: 15 docs    │ thầu xây dựng cầu   │
│ - Latency: 234ms    │ tại Hà Nội...       │
│                     │                     │
│ (Đang load docs...) │ Các gói nổi bật:    │
│                     │ - Xây cầu ABC [1]   │
│                     │ - Mở rộng [2]       │
│                     │                     │
│                     │ ---                 │
│                     │ [1] Gói thầu ABC    │
│                     │ [2] ...             │
└─────────────────────┴─────────────────────┘
```
