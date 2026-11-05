"""Lay danh sach provCode -> provName tu index that + mau bidNo de suy ra regex ma goi thau."""
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

    aggs = es.search(index=index, body={
        "size": 0,
        "aggs": {
            "loc": {
                "nested": {"path": "locations"},
                "aggs": {"p": {"terms": {"field": "locations.provCode", "size": 200}}},
            }
        },
    })
    buckets = aggs.get("aggregations", {}).get("loc", {}).get("p", {}).get("buckets", [])
    print(f"PROV CODE COUNT = {len(buckets)}")

    # mapping code -> name
    names = {}
    for b in buckets:
        code = b["key"]
        r = es.search(index=index, body={
            "size": 1,
            "query": {"nested": {"path": "locations",
                                 "query": {"term": {"locations.provCode": code}}}},
            "_source": ["locations.provName"],
        })
        hits = r.get("hits", {}).get("hits", [])
        nm = hits[0]["_source"]["locations"][0].get("provName") if hits else "?"
        names[code] = nm
        print(f"  {code} = {nm.encode('ascii','backslashreplace').decode()}  ({b['doc_count']})")

    out = Path(__file__).resolve().parent.parent / "config" / "es_province_codes.json"
    out.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved -> {out}")

    # Mau bidNo de suy ra format ma goi thau
    print("\n--- bidNo samples ---")
    r = es.search(index=index, body={"size": 200, "_source": ["bidNo", "bidId"]})
    samples = [h["_source"].get("bidNo") for h in r.get("hits", {}).get("hits", [])]
    pats = {}
    for s in samples:
        if not s:
            continue
        p = re.sub(r"\d", "9", s)
        pats[p] = pats.get(p, 0) + 1
    for p, c in sorted(pats.items(), key=lambda x: -x[1])[:15]:
        print(f"  {p}  x{c}")

    # So sanh voi provinces.json
    print("\n--- provinces.json codes vs ES provCodes ---")
    pj = json.loads((Path(__file__).resolve().parent.parent / "config" / "provinces.json")
                    .read_text(encoding="utf-8"))
    print(f"provinces.json entries = {len(pj)}")
    pj_codes = {v["code"]: k for k, v in pj.items()}
    es_codes = set(names.keys())
    print(f"codes in provinces.json not in ES: {sorted(set(pj_codes) - es_codes)}")
    print(f"codes in ES not in provinces.json: {sorted(es_codes - set(pj_codes))[:80]}")


if __name__ == "__main__":
    main()
