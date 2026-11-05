import httpx, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings

MODEL = settings.DEEPSEEK_MODEL
H = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

variants = [
    ("generate+prompt", "https://api.xah.io/api/generate", {"model": MODEL, "prompt": "hi", "stream": False}),
    ("generate+messages", "https://api.xah.io/api/generate", {"model": MODEL, "messages": [{"role": "user", "content": "hi"}], "stream": False}),
    ("v1/chat/completions", "https://api.xah.io/v1/chat/completions", {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}),
    ("api/v1/chat/completions", "https://api.xah.io/api/v1/chat/completions", {"model": MODEL, "messages": [{"role": "user", "content": "hi"}]}),
    ("tags", "https://api.xah.io/api/tags", None),
]

for name, url, body in variants:
    try:
        r = httpx.get(url, headers=H, timeout=30) if body is None else httpx.post(url, json=body, headers=H, timeout=90)
        print(f"=== {name} [{url}] -> {r.status_code}")
        print(r.text[:500])
    except Exception as e:
        print(f"=== {name} [{url}] -> ERROR {type(e).__name__}: {e}")
    print()
