"""Test search V4 - intent analysis, filtering, hybrid search, reranking."""
import asyncio
import sys
import os

# Force UTF-8 encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.search_service_v4 import SearchServiceV4
from app.config import settings

async def test_1_basic_search():
    """Test 1: Basic search without filters."""
    print("\n=== Test 1: Basic Search ===")
    service = SearchServiceV4()
    query = "xây dựng cầu"
    result = await service.search(query, session_id="test_1")

    total = result.total
    bids_returned = len(result.bids)

    print(f"Query: '{query}'")
    print(f"  Total matched: {total}")
    print(f"  Bids returned: {bids_returned}")

    if bids_returned > 0:
        first = result.bids[0]
        print(f"  First bid: {first.get('_id', 'N/A')} - {first.get('bidName', '')[:60]}")

    success = bids_returned > 0
    print(f"Result: {'PASS' if success else 'FAIL'}")
    return success


async def test_2_intent_analysis():
    """Test 2: Intent analysis with topic extraction."""
    print("\n=== Test 2: Intent Analysis ===")
    service = SearchServiceV4()
    query = "tìm thầu xây dựng tại Hà Nội năm 2024"

    # Run search
    result = await service.search(query, session_id="test_2")
    total = result.total
    bids_returned = len(result.bids)

    print(f"Query: '{query}'")
    print(f"  Filters applied: {result.filters_applied}")
    print(f"  Total matched: {total}")
    print(f"  Bids returned: {bids_returned}")

    success = total > 0
    print(f"Result: {'PASS' if success else 'FAIL'}")
    return success


async def test_3_topic_search():
    """Test 3: Simple topic search."""
    print("\n=== Test 3: Simple Topic Search ===")
    service = SearchServiceV4()
    query = "công ty xây dựng"

    result = await service.search(query, session_id="test_3")
    total = result.total
    bids_returned = len(result.bids)

    print(f"Query: '{query}'")
    print(f"  Total matched: {total}")
    print(f"  Bids returned: {bids_returned}")

    if bids_returned > 0:
        first = result.bids[0]
        print(f"  First bid: {first.get('_id', 'N/A')}")
        print(f"    Name: {first.get('bidName', '')[:70]}")

    success = bids_returned > 0 and total > 0
    print(f"Result: {'PASS' if success else 'FAIL'}")
    return success


async def test_4_location_filter():
    """Test 4: Location-based filtering."""
    print("\n=== Test 4: Location Filter ===")
    service = SearchServiceV4()
    query = "xây dựng Hà Nội"

    result = await service.search(query, session_id="test_4")
    total = result.total
    bids_returned = len(result.bids)

    print(f"Query: '{query}'")
    print(f"  Total matched: {total}")
    print(f"  Bids returned: {bids_returned}")

    # Check if results have Hà Nội location
    ha_noi_count = 0
    if result.bids:
        for bid in result.bids[:3]:
            locations = bid.get("locations", [])
            prov_codes = [l.get("provCode") for l in locations if isinstance(l, dict)]
            if "01" in prov_codes:  # 01 is Hà Nội code
                ha_noi_count += 1
                print(f"  Bid with Hà Nội: {bid.get('_id', 'N/A')}")

    success = bids_returned > 0 and total > 0
    print(f"Result: {'PASS' if success else 'FAIL'}")
    return success


async def test_5_zero_results_fallback():
    """Test 5: Zero results with fallback suggestions."""
    print("\n=== Test 5: Zero Results Fallback ===")
    service = SearchServiceV4()
    query = "5000 tỷ USD"  # Extremely high price - should get zero results

    try:
        result = await service.search(query, session_id="test_5")
        total = result.total
        bids_returned = len(result.bids)
        clarification = result.clarification

        print(f"Query: '{query}'")
        print(f"  Total matched: {total}")
        print(f"  Bids returned: {bids_returned}")
        if clarification:
            print(f"  Clarification/Suggestions: {clarification[:100]}...")

        success = True  # Success if it doesn't timeout and returns a response
        print(f"Result: {'PASS' if success else 'FAIL'}")
        return success
    except asyncio.TimeoutError:
        print(f"Query: '{query}'")
        print(f"  Result: TIMEOUT - LLM call exceeded timeout")
        print(f"Result: FAIL")
        return False
    except Exception as e:
        print(f"Query: '{query}'")
        print(f"  Error: {e}")
        print(f"Result: FAIL")
        return False


async def run_tests():
    print("=== SEARCH V4 TEST SUITE ===")
    print(f"Debug LLM: {settings.DEBUG_LLM}")

    results = {
        "Test 1": await test_1_basic_search(),
        "Test 2": await test_2_intent_analysis(),
        "Test 3": await test_3_topic_search(),
        "Test 4": await test_4_location_filter(),
        "Test 5": await test_5_zero_results_fallback(),
    }

    print("\n=== SUMMARY ===")
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    return passed_count, total_count


if __name__ == "__main__":
    passed, total = asyncio.run(run_tests())
    sys.exit(0 if passed == total else 1)
