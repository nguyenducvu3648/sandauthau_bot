"""Test sort bidCloseDate sau khi fix deadline."""
import sys
from pathlib import Path
import io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.es_client import ESClient
from app.config import settings


def main():
    es = ESClient.get_client()
    index = settings.ES_INDEX

    print("=== Test sort bidCloseDate ===")

    # Sort sắp hết hạn (asc)
    r = es.search(index=index, body={
        "size": 3,
        "sort": [{"bidCloseDate": "asc"}],
        "_source": ["bidName", "bidCloseDate", "bidNo"]
    })

    print("Top 3 sắp hết hạn:")
    for h in r["hits"]["hits"]:
        s = h["_source"]
        print(f"  {s.get('bidCloseDate')} | {s.get('bidNo', 'N/A')[:15]} | {s.get('bidName', '')[:50]}")

    # Sort mới nhất (desc)
    r = es.search(index=index, body={
        "size": 3,
        "sort": [{"publicDate": "desc"}],
        "_source": ["bidName", "publicDate", "bidNo"]
    })

    print("\nTop 3 mới nhất:")
    for h in r["hits"]["hits"]:
        s = h["_source"]
        print(f"  {s.get('publicDate')} | {s.get('bidNo', 'N/A')[:15]} | {s.get('bidName', '')[:50]}")


if __name__ == "__main__":
    main()
