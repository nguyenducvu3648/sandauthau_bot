"""Probe ES: check publishedDate format and location+year filter."""
import sys, io, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from elasticsearch import Elasticsearch
from app.config import settings

es = Elasticsearch([settings.ELASTICSEARCH_URL],
                   basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
                   verify_certs=False, ssl_show_warn=False)

# 1. Sample publishedDate values
q = {"query": {"match_all": {}}, "size": 5}
r = es.search(index=settings.ELASTICSEARCH_INDEX, body=q)
print("--- sample publishedDate ---")
for h in r["hits"]["hits"]:
    src = h["_source"]
    print(" ", repr(src.get("publishedDate")), "| bidCloseDate:", repr(src.get("bidCloseDate")))

# 2. Mapping for publishedDate
m = es.indices.get_mapping(index=settings.ELASTICSEARCH_INDEX)
props = m[settings.ELASTICSEARCH_INDEX]["mappings"]["properties"]
print("\n--- mapping publishedDate ---", props.get("publishedDate"))
print("--- mapping locations ---", props.get("locations"))

# 3. location only
codes = ["101", "01", "213", "15"]
q = {"query": {"bool": {"filter": [{"terms": {"locations.provCode": codes}}]}},
     "size": 2, "track_total_hits": True}
r = es.search(index=settings.ELASTICSEARCH_INDEX, body=q)
print(f"\nlocation only -> total {r['hits']['total']['value']}")

# 4. year filter variants
for label, clause in [
    ("range string", {"range": {"publishedDate": {"gte": "2024-01-01", "lte": "2024-12-31"}}}),
    ("range date", {"range": {"publishedDate": {"gte": "2024-01-01T00:00:00", "lte": "2024-12-31T23:59:59"}}}),
]:
    q = {"query": {"bool": {"filter": [{"terms": {"locations.provCode": codes}}, clause]}},
         "size": 2, "track_total_hits": True}
    r = es.search(index=settings.ELASTICSEARCH_INDEX, body=q)
    print(f"location + {label} -> total {r['hits']['total']['value']}")

# 5. year only
q = {"query": {"bool": {"filter": [{"range": {"publishedDate": {"gte": "2024-01-01", "lte": "2024-12-31"}}}]}},
     "size": 2, "track_total_hits": True}
r = es.search(index=settings.ELASTICSEARCH_INDEX, body=q)
print(f"year only -> total {r['hits']['total']['value']}")
