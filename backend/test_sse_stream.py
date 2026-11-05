"""Test SSE stream from V4 RAG endpoint - do thoi gian tung event."""
import json
import time
import urllib.request

URL = "http://localhost:8000/search/v4/answer"
payload = json.dumps({"query": "goi thau thiet bi y te", "session_id": "ssetest"}).encode()
req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})

start = time.time()
counts = {}
first_chunk_at = None

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            evt = json.loads(line[6:])
            t = evt.get("type")
            counts[t] = counts.get(t, 0) + 1
            el = time.time() - start

            if t == "metadata":
                print(f"[{el:6.1f}s] metadata: total_docs={evt.get('total_docs')}")
            elif t == "chunk":
                if first_chunk_at is None:
                    first_chunk_at = el
                    print(f"[{el:6.1f}s] FIRST CHUNK arrived")
            elif t == "error":
                print(f"[{el:6.1f}s] ERROR EVENT: {evt.get('content')}")
            else:
                print(f"[{el:6.1f}s] {t}")
except Exception as e:
    print(f"[{time.time()-start:6.1f}s] CONNECTION FAILED: {type(e).__name__}: {e}")

print(f"\nTotal elapsed: {time.time()-start:.1f}s")
print(f"Event counts: {counts}")
if first_chunk_at:
    print(f"Time to first chunk: {first_chunk_at:.1f}s")
else:
    print("NO CHUNKS RECEIVED")
