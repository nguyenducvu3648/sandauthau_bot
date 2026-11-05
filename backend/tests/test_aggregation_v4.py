"""Test V4 aggregation feature."""
import sys, io, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, ".")

import asyncio
from app.services.search_service_v4 import SearchServiceV4


async def test_aggregate():
    """Test aggregate output mode."""
    service = SearchServiceV4()

    # Query với yêu cầu tổng hợp
    query = "Thống kê thầu xây dựng theo địa điểm"
    result = await service.search(query, session_id="test_agg")

    print("=== AGGREGATION TEST ===")
    print(f"Query: '{query}'")
    print(f"Total matched: {result.total}")
    print(f"Response: {result.clarification}")

    if result.aggregation:
        print("\nAggregation results:")
        print(f"  By location: {result.aggregation.get('by_location', {})}")
        print(f"  By year: {result.aggregation.get('by_year', )}")

        price_stats = result.aggregation.get('price_range', {})
        if price_stats:
            print(f"  Price stats:")
            print(f"    Min: {price_stats.get('min') or 0:,.0f} VND")
            print(f"    Max: {price_stats.get('max') or 0:,.0f} VND")
            print(f"    Avg: {price_stats.get('avg') or 0:,.0f} VND")

    # Test passed if aggregation exists
    passed = result.aggregation is not None and len(result.aggregation.get("by_location", {})) > 0
    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    return passed


if __name__ == "__main__":
    passed = asyncio.run(test_aggregate())
    sys.exit(0 if passed else 1)
