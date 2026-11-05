"""Kiem tra format ma goi thau that + cac field dung trong sort/filter."""
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

    # 1. Format bidNo that (random nhieu trang)
    print("--- bidNo patterns (random sample) ---")
    pats = {}
    for _ in range(20):
        r = es.search(index=index, body={
            "size": 500,
            "query": {"function_score": {
                "query": {"match_all": {}},
                "random_score": {"seed": None, "field": "_seq_no"},
            }},
            "_source": ["bidNo"],
        })
        for h in r.get("hits", {}).get("hits", []):
            s = h["_source"].get("bidNo")
            if not s:
                continue
            p = re.sub(r"\d", "9", s)
            pats[p] = pats.get(p, 0) + 1
    for p, c in sorted(pats.items(), key=lambda x: -x[1])[:25]:
        print(f"  {p}  x{c}")

    # 2. Co field 'deadline' / 'bidCode' khong? -> sort test
    print("\n--- sort tests ---")
    for field, order in (("deadline", "asc"), ("bidCloseDate", "asc"),
                         ("bidPrice", "desc"), ("publicDate", "desc")):
        try:
            es.search(index=index, body={"size": 1, "sort": [{field: order}]})
            print(f"  sort {field}: OK")
        except Exception as e:
            print(f"  sort {field}: FAIL -> {str(e)[:160]}")

    # 3. bidForm values mapping -> ten
    print("\n--- bidForm values ---")
    r = es.search(index=index, body={"size": 0, "aggs": {"v": {"terms": {"field": "bidForm", "size": 40}}}})
    for b in r.get("aggregations", {}).get("v", {}).get("buckets", []):
        print(f"  {b['key']} = {b['doc_count']}")

    # 4. investField values
    print("\n--- investField values ---")
    r = es.search(index=index, body={"size": 0, "aggs": {"v": {"terms": {"field": "investField", "size": 20}}}})
    for b in r.get("aggregations", {}).get("v", {}).get("buckets", []):
        print(f"  {b['key']} = {b['doc_count']}")

    # 5. Test filter location bang code cu (01) vs code moi (101)
    print("\n--- location filter impact ---")
    for code in ("01", "101", "79", "701"):
        r = es.search(index=index, body={
            "size": 0, "track_total_hits": True,
            "query": {"nested": {"path": "locations",
                                 "query": {"term": {"locations.provCode": code}}}},
        })
        print(f"  provCode={code}: {r['hits']['total']['value']}")

    # 6. Test query dang filter cu (nested bool must) co chay khong
    print("\n--- current _build_filter_clauses shape test ---")
    body = {"query": {"bool": {"must": {"multi_match": {
        "query": "xay dung", "fields": ["search_text^3", "bidName^2", "procuringEntityName"],
        "type": "best_fields", "fuzziness": "AUTO", "prefix_length": 2}},
        "filter": [{"nested": {"path": "locations",
                               "query": {"term": {"locations.provCode": "01"}}}}]}}, "size": 1}
    try:
        r = es.search(index=index, body=body)
        print("  OK total =", r["hits"]["total"]["value"])
    except Exception as e:
        print("  FAIL", str(e)[:200])

    # 7. Truong co trong _source khac 'deadline'/'bidCode'?
    print("\n--- _source fields (full) ---")
    r = es.search(index=index, body={"size": 1})
    src = r["hits"]["hits"][0]["_source"]
    print(" ", json.dumps(sorted(src.keys())))

    # 8. search_text co chua ten goi thau?
    print("\n--- search_text sample ---")
    st = src.get("search_text", "")
    print("  len =", len(st))
    print("  ", st[:300].encode("ascii", "backslashreplace").decode())


if __name__ == "__main__":
    main()
