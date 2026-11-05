# Export 1,000 MongoDB records

## What it does
- Connects to `mongodb://localhost:27017/`
- Reads `random_db.dauthaus`
- Exports up to 1,000 records as JSON Lines (JSONL)
- Does not modify MongoDB
- Streams records rather than loading the entire collection into memory

## Run on Windows

Open a terminal in this folder, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python export_mongo_sample.py
```

If your connection settings differ, copy `.env.example` to `.env` and edit it.

Output:
`data/raw/dauthaus_sample_1000.jsonl`

Each line in the JSONL file is one MongoDB document. BSON `ObjectId` and date values are converted to strings for JSON export. This export is a raw sample; it does not normalize fields or create embeddings yet.
