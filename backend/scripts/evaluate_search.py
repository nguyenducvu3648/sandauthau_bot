"""Evaluate search quality với Recall@K, nDCG, MRR."""
import asyncio
import json
from pathlib import Path
from typing import List, Dict

async def evaluate():
    """Đo Recall@50, nDCG@10, MRR."""
    from app.services.search_service import SearchService
    from app.services.intent_analyzer_v2 import IntentAnalyzerV2

    # Load dataset
    dataset_path = Path(__file__).parent.parent / "tests" / "eval_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    search = SearchService()
    metrics = {"recall@50": [], "ndcg@10": [], "mrr": [], "zero_results": 0}

    for item in dataset:
        query = item["query"]
        ground_truth = set(item["ground_truth"])

        # Phân tích
        analysis = await IntentAnalyzerV2.analyze(query)

        # Search
        if analysis.method == "hybrid":
            results = await search.hybrid_search_rrf(query, top_k=50, filters=analysis.filters)
        else:
            results = await search.bm25_search(query, top_k=50, filters=analysis.filters)

        if not results:
            metrics["zero_results"] += 1
            metrics["recall@50"].append(0)
            metrics["ndcg@10"].append(0)
            metrics["mrr"].append(0)
            continue

        # Recall@50
        retrieved = set([r.get("bidCode", r.get("bidName")) for r in results[:50]])
        recall = len(ground_truth & retrieved) / len(ground_truth) if ground_truth else 0
        metrics["recall@50"].append(recall)

        # MRR
        for i, r in enumerate(results):
            code = r.get("bidCode", r.get("bidName"))
            if code in ground_truth:
                metrics["mrr"].append(1 / (i + 1))
                break
        else:
            metrics["mrr"].append(0)

        # nDCG@10
        dcg = sum([1 / np.log2(i + 2) for i, r in enumerate(results[:10]) if r.get("bidCode", r.get("bidName")) in ground_truth])
        idcg = sum([1 / np.log2(i + 2) for i in range(min(len(ground_truth), 10))])
        metrics["ndcg@10"].append(dcg / idcg if idcg > 0 else 0)

    # Summary
    print(f"Recall@50: {sum(metrics['recall@50']) / len(metrics['recall@50']):.2%}")
    print(f"nDCG@10: {sum(metrics['ndcg@10']) / len(metrics['ndcg@10']):.2%}")
    print(f"MRR: {sum(metrics['mrr']) / len(metrics['mrr']):.3f}")
    print(f"Zero results: {metrics['zero_results']}/{len(dataset)}")

if __name__ == "__main__":
    import numpy as np
    asyncio.run(evaluate())
