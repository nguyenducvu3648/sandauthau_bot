import json
import os
from pathlib import Path
from datetime import date, datetime

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient


# Read .env from the project root (same directory as this script by default).
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "random_db")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "dauthaus")
LIMIT = 1000

OUTPUT_DIR = Path("data") / "raw"
OUTPUT_FILE = OUTPUT_DIR / "dauthaus_sample_1000.jsonl"


def json_default(value):
    """Convert BSON/Python values that JSON cannot represent natively."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    # Preserve a readable representation for other uncommon BSON types.
    return str(value)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )

    try:
        # Confirm MongoDB is reachable.
        client.admin.command("ping")

        collection = client[MONGO_DATABASE][MONGO_COLLECTION]
        total = collection.count_documents({})

        print(f"Connected to MongoDB: {MONGO_URI}")
        print(f"Database: {MONGO_DATABASE}")
        print(f"Collection: {MONGO_COLLECTION}")
        print(f"Total records: {total}")
        print(f"Exporting up to {LIMIT} records...")

        # Stream records from MongoDB; do not load the whole collection into RAM.
        cursor = collection.find({}).sort("_id", 1).limit(LIMIT)

        exported = 0
        with OUTPUT_FILE.open("w", encoding="utf-8") as output:
            for record in cursor:
                output.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        default=json_default,
                    )
                    + "\n"
                )
                exported += 1

        print(f"Export complete: {exported} records")
        print(f"Output file: {OUTPUT_FILE.resolve()}")

    except Exception as exc:
        print(f"Export failed: {type(exc).__name__}: {exc}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    main()
