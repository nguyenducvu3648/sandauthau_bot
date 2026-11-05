"""Check investField as category substitute."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from elasticsearch import Elasticsearch
from collections import Counter

es = Elasticsearch(
    ['https://localhost:9200'],
    basic_auth=('elastic', 'httd99550'),
    verify_certs=False
)

# Sample investField values
result = es.search(
    index='dauthaus_prod_526k_v2',
    body={
        "_source": ["investField"],
        "size": 1000,
        "query": {"exists": {"field": "investField"}}
    }
)

fields = []
for hit in result['hits']['hits']:
    val = hit['_source'].get('investField')
    if val:
        if isinstance(val, list):
            fields.extend(val)
        else:
            fields.append(val)

print(f"Total values: {len(fields)} from {len(result['hits']['hits'])} docs")

counter = Counter(fields)
print(f"\nUnique values: {len(counter)}")
print("\n=== Top 20 ===")
for val, count in counter.most_common(20):
    print(f"{count:6d} | {val}")
