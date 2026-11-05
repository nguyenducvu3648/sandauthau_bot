"""
Pipeline 10k records với checkpoint + resume capability.
"""
import json
import logging
from pathlib import Path
from typing import Any
from datetime import datetime

import numpy as np
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('pipeline_10k.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

INPUT_FILE = Path("data/raw/dauthaus_sample_10k.jsonl")
CHECKPOINT_DIR = Path("checkpoints_10k")
ES_URL = "https://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "httd99550"
INDEX_NAME = "dauthaus_test_10k"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 1000
EMBED_BATCH = 32
ES_BULK = 500

CHECKPOINT_DIR.mkdir(exist_ok=True)


def transform_record(doc: dict[str, Any]) -> dict[str, Any]:
    parts = [doc["bidName"], doc["procuringEntityName"]]
    if doc.get("planName"):
        parts.append(doc["planName"])
    if doc.get("projectName"):
        parts.append(doc["projectName"])

    search_text = " | ".join(parts)

    transformed = {
        "mongo_id": doc["_id"],
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

    for field in ["planNo", "planName", "projectCode", "projectName"]:
        if field in doc:
            transformed[field] = doc[field]

    return transformed


def create_es_index(es: Elasticsearch):
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
                "bidName": {"type": "text", "analyzer": "vietnamese", "fields": {"keyword": {"type": "keyword"}}},
                "procuringEntityName": {"type": "text", "analyzer": "vietnamese"},
                "search_text": {"type": "text", "analyzer": "vietnamese"},
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
                        "districtName": {"type": "keyword"}
                    }
                },
                "bidOpenLocation": {"type": "keyword"},
                "planNo": {"type": "keyword"},
                "planName": {"type": "text", "analyzer": "vietnamese"},
                "projectCode": {"type": "keyword"},
                "projectName": {"type": "text", "analyzer": "vietnamese"},
                "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}
            }
        }
    }

    if es.indices.exists(index=INDEX_NAME):
        logger.info(f"Index {INDEX_NAME} exists, deleting")
        es.indices.delete(index=INDEX_NAME)

    es.indices.create(index=INDEX_NAME, body=mapping)
    logger.info(f"Created index {INDEX_NAME}")


def get_last_checkpoint():
    checkpoints = sorted(CHECKPOINT_DIR.glob("batch_*.jsonl"))
    if not checkpoints:
        return None, 0

    last_file = checkpoints[-1]
    batch_num = int(last_file.stem.split("_")[1])

    with last_file.open(encoding="utf-8") as f:
        lines = f.readlines()
        if lines:
            last_doc = json.loads(lines[-1])
            return last_doc["mongo_id"], batch_num


def main():
    logger.info(f"Reading {INPUT_FILE}")
    records = []
    with INPUT_FILE.open(encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    logger.info(f"Loaded {len(records)} records")

    # Check resume
    last_id, last_batch_num = get_last_checkpoint()
    if last_id:
        logger.info(f"Resume from batch {last_batch_num}, last_id={last_id}")
        records = [r for r in records if r["_id"] > last_id]
        logger.info(f"Remaining: {len(records)} records")
        start_batch = last_batch_num + 1
    else:
        start_batch = 0

    # Load model
    logger.info(f"Loading model {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    # Connect ES
    logger.info(f"Connecting to {ES_URL}")
    es = Elasticsearch([ES_URL], basic_auth=(ES_USER, ES_PASSWORD), verify_certs=False, request_timeout=60)
    if not es.ping():
        raise ConnectionError(f"ES unavailable at {ES_URL}")

    # Create index (skip if resuming)
    if start_batch == 0:
        create_es_index(es)

    # Process in batches
    total_indexed = 0
    for batch_idx in range(0, len(records), BATCH_SIZE):
        batch_num = start_batch + (batch_idx // BATCH_SIZE)
        batch = records[batch_idx:batch_idx + BATCH_SIZE]

        logger.info(f"Batch {batch_num}: processing {len(batch)} records")

        # Transform
        transformed = [transform_record(r) for r in batch]

        # Embed in sub-batches
        all_texts = [r["search_text"] for r in transformed]
        embeddings = model.encode(all_texts, show_progress_bar=True, batch_size=EMBED_BATCH)

        for record, emb in zip(transformed, embeddings):
            record["embedding"] = emb.tolist()

        # Checkpoint
        checkpoint_file = CHECKPOINT_DIR / f"batch_{batch_num:04d}.jsonl"
        with checkpoint_file.open("w", encoding="utf-8") as f:
            for record in transformed:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"Checkpoint saved: {checkpoint_file}")

        # Bulk index
        actions = [
            {"_index": INDEX_NAME, "_id": r["mongo_id"], "_source": r}
            for r in transformed
        ]
        success, failed = helpers.bulk(es, actions, raise_on_error=False, chunk_size=ES_BULK, request_timeout=120)
        total_indexed += success
        logger.info(f"Indexed {success} docs, {len(failed)} failed")

        if failed:
            logger.error(f"Failed samples: {failed[:3]}")

    # Verify
    count = es.count(index=INDEX_NAME)["count"]
    logger.info(f"Total in ES: {count}")
    logger.info(f"Pipeline complete: {total_indexed} indexed")


if __name__ == "__main__":
    main()

