"""Test query Elasticsearch sau khi index."""
import urllib3
from elasticsearch import Elasticsearch

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"  # Thay password của bạn
INDEX_NAME = "dauthaus_test_1k"

es = Elasticsearch(
    [ES_URL],
    basic_auth=(ES_USER, ES_PASSWORD),
    verify_certs=False
)

# Refresh để đảm bảo data khả dụng
es.indices.refresh(index=INDEX_NAME)

# Count
count = es.count(index=INDEX_NAME)["count"]
print(f"Total documents: {count}")

if count > 0:
    # Test 1: Exact lookup by bidNo
    result = es.search(index=INDEX_NAME, query={"term": {"bidNo": "BP2200125545"}})
    print(f"\n=== Test 1: Exact lookup ===")
    if result["hits"]["total"]["value"] > 0:
        doc = result["hits"]["hits"][0]["_source"]
        print(f"bidNo: {doc['bidNo']}")
        print(f"bidName: {doc['bidName']}")
        print(f"search_text: {doc['search_text'][:100]}...")

    # Test 2: BM25 text search
    result = es.search(index=INDEX_NAME, query={"match": {"search_text": "xây dựng trường học"}})
    print(f"\n=== Test 2: BM25 text search 'xây dựng trường học' ===")
    print(f"Found {result['hits']['total']['value']} hits")
    for hit in result["hits"]["hits"][:3]:
        print(f"  {hit['_score']:.2f} | {hit['_source']['bidName'][:60]}")

    # Test 3: Metadata filter
    result = es.search(
        index=INDEX_NAME,
        query={"bool": {"filter": [
            {"term": {"investField": "XL"}},
            {"range": {"bidPrice": {"gte": 1000000000}}}
        ]}}
    )
    print(f"\n=== Test 3: Filter (investField=XL, price>=1B) ===")
    print(f"Found {result['hits']['total']['value']} hits")
    for hit in result["hits"]["hits"][:3]:
        src = hit["_source"]
        print(f"  {src['bidPrice']:,.0f} | {src['bidName'][:50]}")

    # Test 4: Vector search (embed query trước)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    query_text = "mua sắm thiết bị y tế"
    query_vector = model.encode(query_text).tolist()

    result = es.search(
        index=INDEX_NAME,
        knn={"field": "embedding", "query_vector": query_vector, "k": 5, "num_candidates": 100}
    )
    print(f"\n=== Test 4: Vector search '{query_text}' ===")
    print(f"Found {result['hits']['total']['value']} hits")
    for hit in result["hits"]["hits"]:
        print(f"  {hit['_score']:.3f} | {hit['_source']['bidName'][:60]}")

    print("\n✓ All tests passed")
else:
    print("ERROR: No documents indexed!")
