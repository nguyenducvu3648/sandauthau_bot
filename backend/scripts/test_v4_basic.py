"""
Test cơ bản V4 search service.
Kiểm tra 8 bước flow với câu hỏi đơn giản.
"""
import sys
import asyncio
import json
from pathlib import Path
import io

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.search_service_v4 import SearchServiceV4


async def test_fast_path():
    """Test bước 1: Fast path với mã gói thầu."""
    print("\n=== TEST 1: Fast Path (Mã gói thầu) ===")

    service = SearchServiceV4()
    result = await service.search(
        query="Tìm gói thầu AB1234567890",
        session_id="test_001"
    )

    print(f"Total: {result.total}")
    print(f"Took: {result.took_ms:.0f}ms")
    print(f"Filters: {result.filters_applied}")


async def test_greeting():
    """Test bước 1: Greeting detection."""
    print("\n=== TEST 2: Greeting Detection ===")

    service = SearchServiceV4()
    result = await service.search(
        query="Xin chào",
        session_id="test_002"
    )

    print(f"Total: {result.total}")
    print(f"Clarification: {result.clarification}")


async def test_simple_search():
    """Test bước 3-4: LLM intent + hybrid search."""
    print("\n=== TEST 3: Simple Topic Search ===")

    service = SearchServiceV4()
    result = await service.search(
        query="Tìm thầu xây dựng",
        session_id="test_003"
    )

    print(f"Total: {result.total}")
    print(f"Took: {result.took_ms:.0f}ms")
    print(f"Filters: {result.filters_applied}")
    if hasattr(result, '_debug_intent'):
        print(f"Debug Intent: {json.dumps(result._debug_intent, ensure_ascii=False, indent=2)}")
    print(f"Bids returned: {len(result.bids)}")
    if result.bids:
        print(f"First bid: {result.bids[0].get('bidName', 'N/A')[:80]}")


async def test_location_filter():
    """Test filter với địa điểm."""
    print("\n=== TEST 4: Location Filter ===")

    service = SearchServiceV4()
    result = await service.search(
        query="Tìm thầu xây dựng ở Hà Nội",
        session_id="test_004"
    )

    print(f"Total: {result.total}")
    print(f"Took: {result.took_ms:.0f}ms")
    print(f"Filters: {json.dumps(result.filters_applied, ensure_ascii=False, indent=2)}")
    if hasattr(result, '_debug_intent'):
        print(f"Debug Intent: {json.dumps(result._debug_intent, ensure_ascii=False, indent=2)}")
    print(f"Bids returned: {len(result.bids)}")


async def test_zero_results():
    """Test fallback khi 0 kết quả."""
    print("\n=== TEST 5: Zero Results Fallback ===")

    service = SearchServiceV4()
    result = await service.search(
        query="Tìm thầu xây dựng tàu vũ trụ giá 1 triệu đồng",
        session_id="test_005"
    )

    print(f"Total: {result.total}")
    print(f"Clarification: {result.clarification}")
    if hasattr(result, '_debug_intent'):
        print(f"Debug Intent: {json.dumps(result._debug_intent, ensure_ascii=False, indent=2)}")
    print(f"Relaxed filters: {result.relaxed_filters}")


async def main():
    """Run all tests."""
    tests = [
        test_greeting,
        test_simple_search,
        test_location_filter,
        test_zero_results
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as e:
            print(f"ERROR in {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n=== ALL TESTS COMPLETED ===")


if __name__ == "__main__":
    asyncio.run(main())
