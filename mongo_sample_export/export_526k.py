"""Export full 526k records từ MongoDB sang JSONL."""
from pymongo import MongoClient
import json
from pathlib import Path
from datetime import datetime

OUTPUT = Path("data/raw/dauthaus_full_526k.jsonl")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

def serialize(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

client = MongoClient("mongodb://localhost:27017/")
collection = client["random_db"]["dauthaus"]

total = collection.count_documents({})
print(f"Total: {total} records")

with OUTPUT.open("w", encoding="utf-8") as f:
    for i, doc in enumerate(collection.find(), 1):
        doc["_id"] = str(doc["_id"])
        f.write(json.dumps(doc, ensure_ascii=False, default=serialize) + "\n")
        if i % 10000 == 0:
            print(f"Exported {i}/{total}...")

print(f"Done: {OUTPUT} ({OUTPUT.stat().st_size / 1024 / 1024:.1f} MB)")
