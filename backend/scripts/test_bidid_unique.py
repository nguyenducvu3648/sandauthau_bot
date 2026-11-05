"""Test bidId unique key sau khi fix bidCode."""
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

    print("=== Test bidId uniqueness ===")

    # Cardinality bidId
    r = es.search(index=index, body={
        "size": 0,
        "aggs": {"card": {"cardinality": {"field": "bidId"}}}
    })
    bid_id_card = r["aggregations"]["card"]["value"]

    # Total docs
    r_total = es.search(index=index, body={"size": 0, "track_total_hits": True})
    total = r_total["hits"]["total"]["value"]

    print(f"Total docs: {total:,}")
    print(f"Unique bidId: {bid_id_card:,}")
    print(f"Ratio: {bid_id_card / total:.4f} (1.0 = unique)")

    # So sánh với bidNo
    r2 = es.search(index=index, body={
        "size": 0,
        "aggs": {"card": {"cardinality": {"field": "bidNo"}}}
    })
    bid_no_card = r2["aggregations"]["card"]["value"]
    print(f"\nUnique bidNo: {bid_no_card:,} (nhiều gói cùng bidNo → không dùng làm primary key)")

    # Test term query bidId
    r3 = es.search(index=index, body={
        "size": 1,
        "_source": ["bidId", "bidNo", "bidName"],
        "query": {"match_all": {}}
    })
    sample = r3["hits"]["hits"][0]["_source"]
    sample_id = sample.get("bidId")
    print(f"\n=== Test term query bidId ===")
    print(f"Sample bidId: {sample_id}")

    r4 = es.search(index=index, body={
        "size": 1,
        "query": {"term": {"bidId": sample_id}}
    })
    print(f"Term query hits: {r4['hits']['total']['value']} (phải = 1)")


if __name__ == "__main__":
    main()
