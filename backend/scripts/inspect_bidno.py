"""Lay nhieu format bidNo that de suy ra regex ma goi thau."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.es_client import ESClient


def main():
    es = ESClient.get_client()
    index = settings.ES_INDEX

    print("--- bidNo by year (query prefixes) ---")
    pats = {}
    # quet theo prefix goc de lay nhieu format khac nhau
    for prefix in ("BP", "NT", "TB", "CG", "TT", "KH", "MT", "XD", "XDCT", "HH", "01", "22"):
        try:
            r = es.search(index=index, body={
                "size": 100,
                "query": {"prefix": {"bidNo": prefix}},
                "_source": ["bidNo", "publicDate", "bidName"],
            })
            for h in r.get("hits", {}).get("hits", []):
                s = h["_source"].get("bidNo")
                if not s:
                    continue
                p = re.sub(r"[0-9]", "9", s)
                pats[p] = pats.get(p, 0) + 1
        except Exception as e:
            print(f"  prefix {prefix}: ERR {str(e)[:100]}")
    for p, c in sorted(pats.items(), key=lambda x: -x[1])[:30]:
        print(f"  {p}  x{c}")

    print("\n--- terms agg on bidNo prefix-ish (keyword) ---")
    try:
        r = es.search(index=index, body={
            "size": 0,
            "aggs": {"v": {"terms": {"field": "bidNo", "size": 40}}},
        })
        for b in r.get("aggregations", {}).get("v", {}).get("buckets", []):
            print(f"  {b['key']} = {b['doc_count']}")
    except Exception as e:
        print("  ERR", str(e)[:200])

    print("\n--- bidNo unique count vs docs ---")
    r = es.search(index=index, body={
        "size": 0,
        "aggs": {"card": {"cardinality": {"field": "bidNo"}}},
    })
    print("  cardinality(bidNo) =", r.get("aggregations", {}).get("card", {}).get("value"))

    print("\n--- test term query bidNo exact ---")
    r = es.search(index=index, body={"size": 1, "query": {"term": {"bidNo": "BP2200225863"}}})
    print("  hits:", r["hits"]["total"]["value"])


if __name__ == "__main__":
    main()
