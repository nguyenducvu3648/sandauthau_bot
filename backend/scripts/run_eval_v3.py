"""Run eval V3 - đo intent accuracy, filter accuracy."""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.intent_analyzer_v3 import IntentAnalyzerV3


async def main():
    dataset = json.loads((Path(__file__).parent.parent / "config" / "eval_20.json").read_text(encoding="utf-8"))

    results = {"total": len(dataset), "intent_correct": 0, "method_correct": 0, "filter_exact": 0}

    for item in dataset:
        analysis = await IntentAnalyzerV3.analyze(item["query"], session_context=None)

        # Intent accuracy
        if analysis.intent == item["intent"]:
            results["intent_correct"] += 1

        # Method accuracy
        if analysis.method == item["expected_method"]:
            results["method_correct"] += 1

        # Filter exact match
        exp_filters = item.get("expected_filters", {})
        if analysis.filters == exp_filters:
            results["filter_exact"] += 1
        elif "location" in exp_filters and "location" in analysis.filters:
            # Check location codes match
            if set(analysis.filters["location"]) == set(exp_filters["location"]):
                results["filter_exact"] += 1

        # Code detection
        exp_code = item.get("expected_code")
        if exp_code and analysis.code == exp_code:
            results.setdefault("code_correct", 0)
            results["code_correct"] += 1

    # Calc percentages
    results["intent_acc"] = round(results["intent_correct"] / results["total"] * 100, 1)
    results["method_acc"] = round(results["method_correct"] / results["total"] * 100, 1)
    results["filter_acc"] = round(results["filter_exact"] / results["total"] * 100, 1)

    print(json.dumps(results, indent=2, ensure_ascii=False))

    # Save
    output = Path(__file__).parent.parent / "results" / "v3_eval_20.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
