"""Export 10k records from MongoDB to JSONL."""
import json
from pathlib import Path
from pymongo import MongoClient
from datetime import datetime

OUTPUT = Path("data/raw/dauthaus_sample_10k.jsonl")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

client = MongoClient("mongodb://localhost:27017/")
coll = client["random_db"]["dauthaus"]

with OUTPUT.open("w", encoding="utf-8") as f:
    for doc in coll.find().limit(10000):
        doc["_id"] = str(doc["_id"])
        f.write(json.dumps(doc, ensure_ascii=False, default=serialize) + "\n")

print(f"Exported 10k records to {OUTPUT}")
