"""In mapping that index thật đang dùng (không tin file config). ASCII-safe output."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.es_client import ESClient


def main():
    es = ESClient.get_client()
    index = settings.ES_INDEX
    print(f"INDEX = {index}")

    m = es.indices.get_mapping(index=index)
    props = list(m.values())[0]["mappings"]["properties"]
    print(f"FIELD COUNT = {len(props)}")
    for name, defn in sorted(props.items()):
        kind = defn.get("type")
        extra = ""
        if kind == "dense_vector":
            extra = f" dims={defn.get('dims')} similarity={defn.get('similarity')}"
        if defn.get("fields"):
            extra += " sub=" + ",".join(defn["fields"].keys())
        # ASCII-safe
        safe = name.encode("ascii", "backslashreplace").decode()
        print(f"  - {safe}: {kind}{extra}")

    print("\n--- counts ---")
    print("docs:", es.count(index=index)["count"])

    print("\n--- sample doc (ascii-safe) ---")
    s = es.search(index=index, body={"size": 1})
    hits = s.get("hits", {}).get("hits", [])
    if hits:
        src = hits[0]["_source"]
        for k in ("bidId", "bidNo", "bidName", "bidForm", "bidMode", "bidPrice",
                  "bidPriceUnit", "publicDate", "bidOpenDate", "bidCloseDate",
                  "investField", "isInternet", "isDomestic"):
            v = src.get(k)
            print(f"  {k} = {v!r}".encode("ascii", "backslashreplace").decode())
        locs = src.get("locations") or []
        print(f"  locations count = {len(locs)}")
        if locs:
            print("  locations[0] = " + json.dumps(locs[0], ensure_ascii=True))

    # Kiem tra field co bao nhiem gia tri duy nhat
    print("\n--- sample values for keyword fields ---")
    for f in ("bidForm", "bidMode", "investField", "isInternet", "bidPriceUnit"):
        if f in props:
            try:
                aggs = es.search(index=index, body={
                    "size": 0,
                    "aggs": {"v": {"terms": {"field": f, "size": 15}}},
                })
                buckets = aggs.get("aggregations", {}).get("v", {}).get("buckets", [])
                out = [(b.get("key"), b.get("doc_count")) for b in buckets]
                print(f"  {f}: " + json.dumps(out, ensure_ascii=True))
            except Exception as e:
                print(f"  {f}: ERR {e}")

    # Kiem tra locations.provName co duoc populate khong
    print("\n--- locations.provName sample (nested agg) ---")
    try:
        aggs = es.search(index=index, body={
            "size": 0,
            "aggs": {
                "loc": {
                    "nested": {"path": "locations"},
                    "aggs": {"p": {"terms": {"field": "locations.provName", "size": 10}}},
                }
            },
        })
        buckets = aggs.get("aggregations", {}).get("loc", {}).get("p", {}).get("buckets", [])
        print(json.dumps([(b.get("key"), b.get("doc_count")) for b in buckets], ensure_ascii=True))
    except Exception as e:
        print("ERR", e)


if __name__ == "__main__":
    main()
