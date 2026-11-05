import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import settings
from elasticsearch import Elasticsearch

es = Elasticsearch([settings.ELASTICSEARCH_URL],
                   basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
                   verify_certs=False, ssl_show_warn=False)

idx = settings.ELASTICSEARCH_INDEX
print("index:", idx)
print("aliases:", es.indices.get_alias(index=idx).keys())

r = es.search(index=idx, body={"query": {"match_all": {}}, "size": 2})
for h in r["hits"]["hits"]:
    print("HITS _id:", h["_id"], "| keys:", list(h["_source"].keys())[:20])
    print("   bidId:", h["_source"].get("bidId"), "| bidNo:", h["_source"].get("bidNo"))

m = es.mget(index=idx, body={"ids": [h["_id"] for h in r["hits"]["hits"]]})
print("mget docs:", [(d.get("_id"), d.get("found")) for d in m["docs"]])
