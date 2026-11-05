"""
Pipeline test với 1000 records mẫu:
- Transform: tạo search_text
- Embed: paraphrase-multilingual-MiniLM-L12-v2
- Index: Elasticsearch
"""
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_FILE = Path("data/raw/dauthaus_sample_1000.jsonl")
ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"  # Thay bằng password thực tế
INDEX_NAME = "dauthaus_test_1k"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def transform_record(doc: dict[str, Any]) -> dict[str, Any]:
    """Transform MongoDB doc sang Elasticsearch format."""
    # search_text: bidName | procuringEntityName [| planName] [| projectName]
    parts = [doc["bidName"], doc["procuringEntityName"]]

    if doc.get("planName"):
        parts.append(doc["planName"])
    if doc.get("projectName"):
        parts.append(doc["projectName"])

    search_text = " | ".join(parts)

    # Giữ fields cần thiết (không đưa _id vào _source, dùng làm ES document ID)
    transformed = {
        "mongo_id": doc["_id"],  # Lưu MongoDB _id dưới tên khác
        "bidNo": doc["bidNo"],
        "bidId": doc["bidId"],
        "mpiid": doc["mpiid"],
        "bidName": doc["bidName"],
        "procuringEntityName": doc["procuringEntityName"],
        "search_text": search_text,
        "bidPrice": doc["bidPrice"],
        "bidPriceUnit": doc["bidPriceUnit"],
        "bidOpenDate": doc["bidOpenDate"],
        "bidCloseDate": doc["bidCloseDate"],
        "publicDate": doc["publicDate"],
        "bidForm": doc["bidForm"],
        "bidMode": doc["bidMode"],
        "investField": doc["investField"],
        "isDomestic": doc["isDomestic"],
        "isInternet": doc["isInternet"],
        "locations": doc.get("locations", []),
        "bidOpenLocation": doc.get("bidOpenLocation"),
    }

    # Optional fields
    for field in ["planNo", "planName", "projectCode", "projectName"]:
        if field in doc:
            transformed[field] = doc[field]

    return transformed


def create_es_index(es: Elasticsearch):
    """Tạo Elasticsearch index với mapping."""
    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "vietnamese": {
                        "type": "standard",
                        "stopwords": "_vietnamese_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "bidNo": {"type": "keyword"},
                "bidId": {"type": "keyword"},
                "mpiid": {"type": "keyword"},
                "bidName": {
                    "type": "text",
                    "analyzer": "vietnamese",
                    "fields": {"keyword": {"type": "keyword"}}
                },
                "procuringEntityName": {
                    "type": "text",
                    "analyzer": "vietnamese"
                },
                "search_text": {
                    "type": "text",
                    "analyzer": "vietnamese"
                },
                "bidPrice": {"type": "float"},
                "bidPriceUnit": {"type": "keyword"},
                "bidOpenDate": {"type": "date"},
                "bidCloseDate": {"type": "date"},
                "publicDate": {"type": "date"},
                "bidForm": {"type": "keyword"},
                "bidMode": {"type": "keyword"},
                "investField": {"type": "keyword"},
                "isDomestic": {"type": "boolean"},
                "isInternet": {"type": "boolean"},
                "locations": {
                    "type": "nested",
                    "properties": {
                        "provCode": {"type": "keyword"},
                        "provName": {"type": "keyword"},
                        "districtCode": {"type": "keyword"},
                        "districtName": {"type": "keyword"},
                        "wardCode": {"type": "keyword"},
                        "wardName": {"type": "keyword"}
                    }
                },
                "bidOpenLocation": {"type": "keyword"},
                "planNo": {"type": "keyword"},
                "planName": {"type": "text", "analyzer": "vietnamese"},
                "projectCode": {"type": "keyword"},
                "projectName": {"type": "text", "analyzer": "vietnamese"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": 384,
                    "index": True,
                    "similarity": "cosine"
                }
            }
        }
    }

    if es.indices.exists(index=INDEX_NAME):
        logger.info(f"Index {INDEX_NAME} đã tồn tại, xóa và tạo lại")
        es.indices.delete(index=INDEX_NAME)

    es.indices.create(index=INDEX_NAME, body=mapping)
    logger.info(f"Tạo index {INDEX_NAME} thành công")


def main():
    # Load dữ liệu
    logger.info(f"Đọc {INPUT_FILE}")
    records = []
    with INPUT_FILE.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    logger.info(f"Loaded {len(records)} records")

    # Transform
    logger.info("Transform records")
    transformed = [transform_record(r) for r in tqdm(records, desc="Transform")]

    # Load embedding model
    logger.info(f"Load model {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Embed
    logger.info("Embedding search_text")
    texts = [r["search_text"] for r in transformed]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    for record, emb in zip(transformed, embeddings):
        record["embedding"] = emb.tolist()

    logger.info(f"Embedding shape: {embeddings.shape}")

    # Connect Elasticsearch
    logger.info(f"Connect Elasticsearch: {ES_URL}")
    es = Elasticsearch(
        [ES_URL],
        basic_auth=(ES_USER, ES_PASSWORD),
        verify_certs=False  # Bỏ qua SSL self-signed cert
    )

    if not es.ping():
        raise ConnectionError(f"Elasticsearch không khả dụng tại {ES_URL}")

    # Create index
    create_es_index(es)

    # Bulk index
    logger.info("Bulk indexing")
    actions = [
        {
            "_index": INDEX_NAME,
            "_id": record["mongo_id"],  # Dùng MongoDB _id làm ES document ID
            "_source": record
        }
        for record in transformed
    ]

    success, failed = helpers.bulk(es, actions, raise_on_error=False)
    logger.info(f"Indexed: {success} success, {len(failed)} failed")

    if failed:
        logger.error(f"Failed records: {failed[:5]}")

    # Verify
    count = es.count(index=INDEX_NAME)["count"]
    logger.info(f"Total documents in index: {count}")

    logger.info("✓ Pipeline hoàn thành")


if __name__ == "__main__":
    main()
