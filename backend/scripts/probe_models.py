import httpx, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings

H = {"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
URL = "https://api.xah.io/v1/chat/completions"

models = [
    settings.DEEPSEEK_MODEL,
    "deepseek-v4.1-flash",
    "tuanxedich28/DeepSeek-V4.1-Flash",
    "dungcsnd113/DeepSeek-V4.1-Flash-1017",
    "sypham98/deepseek-v4-pro",
    "gemini-2.5-flash-lite",
    "claude-haiku-4.5",
]

for m in models:
    try:
        r = httpx.post(URL, json={"model": m, "messages": [{"role": "user", "content": "Nói: OK"}], "max_tokens": 10}, headers=H, timeout=90)
        txt = r.text[:200].replace("\n", " ")
        print(f"{m} -> {r.status_code} | {txt}")
    except Exception as e:
        print(f"{m} -> ERROR {type(e).__name__}: {e}")
