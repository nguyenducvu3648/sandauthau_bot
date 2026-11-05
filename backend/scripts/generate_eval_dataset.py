"""Generate evaluation dataset với LLM."""
import asyncio
import json
from pathlib import Path

async def generate_queries():
    """Sinh 50 câu query test."""
    from app.services.deepseek_client import DeepSeekClient

    prompt = """Sinh 50 câu hỏi tìm kiếm gói thầu Việt Nam thật, đa dạng:
- 15 câu keyword đơn giản: "xây dựng cầu", "mua sắm thiết bị y tế"
- 15 câu có filter: "Hà Nội năm 2024", "dưới 5 tỷ", "Đà Nẵng trên 20 tỷ"
- 10 câu phức tạp: "so sánh xây dựng và sửa chữa cầu", "Hà Nội không phải xây dựng"
- 10 câu aggregation: "bao nhiêu gói thầu", "top 10 cao nhất"

Trả về JSON array: [{"query": "...", "intent": "search|aggregation", "expected_method": "hybrid|bm25_code|metadata_only"}]
"""

    response = await DeepSeekClient.chat(
        messages=[{"role": "user", "content": prompt}],
        response_format="json",
        temperature=0.8,
        max_tokens=2000
    )

    return json.loads(response)

async def label_with_es(queries):
    """Gán nhãn gói thầu đúng bằng ES."""
    from app.services.search_service import SearchService
    from app.services.intent_analyzer_v2 import IntentAnalyzerV2

    search = SearchService()
    labeled = []

    for item in queries:
        query = item["query"]

        # Phân tích query
        analysis = await IntentAnalyzerV2.analyze(query)

        # Search top 50
        if analysis.method == "hybrid":
            results = await search.hybrid_search_rrf(query, top_k=50, filters=analysis.filters)
        else:
            results = await search.bm25_search(query, top_k=50, filters=analysis.filters)

        # Lấy top 5 làm label
        labeled.append({
            "query": query,
            "intent": analysis.intent,
            "filters": analysis.filters,
            "method": analysis.method,
            "ground_truth": [r.get("bidCode", r.get("bidName")) for r in results[:5]]
        })

    return labeled

async def main():
    print("Sinh 50 câu query...")
    queries = await generate_queries()

    print("Gán nhãn với ES...")
    labeled = await label_with_es(queries)

    # Save
    output = Path(__file__).parent.parent / "tests" / "eval_dataset.json"
    output.parent.mkdir(exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(labeled, f, ensure_ascii=False, indent=2)

    print(f"✓ Đã tạo {len(labeled)} queries → {output}")

if __name__ == "__main__":
    asyncio.run(main())
