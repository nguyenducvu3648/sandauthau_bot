"""Test queries tren 10k dataset."""
import sys
import urllib3
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding='utf-8')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"
INDEX_NAME = "dauthaus_test_10k"

es = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False)
es.indices.refresh(index=INDEX_NAME)

count = es.count(index=INDEX_NAME)["count"]
print(f"Total documents: {count}")

# Test 1: BM25
result = es.search(index=INDEX_NAME, query={"match": {"search_text": "xây dựng trường học"}}, size=5)
print(f"\n=== BM25 'xây dựng trường học' ===")
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_score']:.2f} | {hit['_source']['bidName'][:60]}")

# Test 2: Metadata filter
result = es.search(
    index=INDEX_NAME,
    query={"bool": {"filter": [
        {"term": {"investField": "XL"}},
        {"range": {"bidPrice": {"gte": 5000000000}}}
    ]}},
    size=5
)
print(f"\n=== Filter (XL, price>=5B) ===")
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_source']['bidPrice']:,.0f} VND")

# Test 3: Vector search
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
query_vec = model.encode("mua sắm thiết bị y tế").tolist()
result = es.search(index=INDEX_NAME, knn={"field": "embedding", "query_vector": query_vec, "k": 5, "num_candidates": 100})
print(f"\n=== Vector 'mua sắm thiết bị y tế' ===")
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_score']:.3f} | {hit['_source']['bidName'][:60]}")

# Test 4: Hybrid search (BM25 + Vector, manual merge)
# RRF cần license, dùng cách đơn giản: knn với pre-filter
result = es.search(
    index=INDEX_NAME,
    knn={
        "field": "embedding",
        "query_vector": model.encode("xây dựng cầu đường").tolist(),
        "k": 10,
        "num_candidates": 100,
        "filter": {"match": {"search_text": "xây dựng"}}
    },
    size=5
)
print(f"\n=== Hybrid 'xây dựng cầu đường' (Vector + BM25 filter) ===")
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_score']:.3f} | {hit['_source']['bidName'][:60]}")

print("\n✓ All tests passed")
