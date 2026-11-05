"""Test resume capability - simulate interruption."""
import json
from pathlib import Path

CHECKPOINT_DIR = Path("checkpoints_10k")
LOG_FILE = Path("pipeline_10k.log")

# Check existing checkpoints
checkpoints = sorted(CHECKPOINT_DIR.glob("batch_*.jsonl"))
print(f"Existing checkpoints: {len(checkpoints)}")

if checkpoints:
    for cp in checkpoints[:3]:
        with cp.open(encoding="utf-8") as f:
            lines = f.readlines()
            first = json.loads(lines[0])
            last = json.loads(lines[-1])
            print(f"  {cp.name}: {len(lines)} records, {first['bidNo']} → {last['bidNo']}")

    print(f"\nTo test resume:")
    print(f"1. Delete last checkpoint: rm {checkpoints[-1]}")
    print(f"2. Re-run: python pipeline_10k.py")
    print(f"3. Should resume from batch {len(checkpoints) - 1}")
else:
    print("No checkpoints yet. Run pipeline first.")

# Show log tail
if LOG_FILE.exists():
    print(f"\nLast 10 lines of {LOG_FILE}:")
    with LOG_FILE.open(encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[-10:]:
            print(f"  {line.rstrip()}")
