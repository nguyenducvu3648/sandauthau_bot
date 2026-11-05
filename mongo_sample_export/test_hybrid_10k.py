"""Test hybrid search (BM25 + Vector + RRF) on 10k index."""
import urllib3
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"
INDEX_NAME = "dauthaus_test_10k"

es = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False)
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# Refresh index
es.indices.refresh(index=INDEX_NAME)
count = es.count(index=INDEX_NAME)["count"]
print(f"Total documents: {count}")

if count == 0:
    print("ERROR: Index empty!")
    exit(1)

# Test 1: BM25 only
query_text = "xây dựng cầu đường giao thông"
print(f"\n=== Test 1: BM25 '{query_text}' ===")
result = es.search(index=INDEX_NAME, query={"match": {"search_text": query_text}}, size=5)
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_score']:.2f} | {hit['_source']['bidName'][:60]}")

# Test 2: Vector only
print(f"\n=== Test 2: Vector '{query_text}' ===")
query_vector = model.encode(query_text).tolist()
result = es.search(
    index=INDEX_NAME,
    knn={"field": "embedding", "query_vector": query_vector, "k": 5, "num_candidates": 100}
)
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    print(f"  {hit['_score']:.3f} | {hit['_source']['bidName'][:60]}")

# Test 3: Hybrid (BM25 + Vector + RRF)
print(f"\n=== Test 3: Hybrid (RRF) '{query_text}' ===")
result = es.search(
    index=INDEX_NAME,
    query={"match": {"search_text": query_text}},
    knn={"field": "embedding", "query_vector": query_vector, "k": 10, "num_candidates": 100},
    rank={"rrf": {}},
    size=5
)
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    score = hit.get('_score', hit.get('_rank', 'N/A'))
    print(f"  {score} | {hit['_source']['bidName'][:60]}")

# Test 4: Hybrid + Metadata filter
print(f"\n=== Test 4: Hybrid + Filter (investField=XL, price>=1B) ===")
result = es.search(
    index=INDEX_NAME,
    query={
        "bool": {
            "must": [{"match": {"search_text": query_text}}],
            "filter": [
                {"term": {"investField": "XL"}},
                {"range": {"bidPrice": {"gte": 1000000000}}}
            ]
        }
    },
    knn={"field": "embedding", "query_vector": query_vector, "k": 10, "num_candidates": 100},
    rank={"rrf": {}},
    size=5
)
print(f"Hits: {result['hits']['total']['value']}")
for hit in result["hits"]["hits"]:
    score = hit.get('_score', hit.get('_rank', 'N/A'))
    print(f"  {score} | {hit['_source']['bidPrice']:,.0f} VND | {hit['_source']['bidName'][:50]}")

print("\n✓ Hybrid search tests complete")
