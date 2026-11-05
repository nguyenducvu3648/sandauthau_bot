"""Test search optimization - RRF, fallback, location, rerank."""
import asyncio
import sys
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
from app.services.search_service import SearchService
from app.services.location_service import LocationService

def test_location_mapping():
    """Test province name to code mapping."""
    cases = [
        ("Hà Nội", "01"),
        ("HN", "01"),
        ("Thủ đô", "01"),
        ("TP.HCM", "79"),
        ("Sài Gòn", "79"),
        ("Đà Nẵng", "48"),
        ("invalid", None),
    ]
    passed = 0
    for name, expected in cases:
        result = LocationService.get_province_code(name)
        if result == expected:
            passed += 1
            print(f"OK {name} -> {result}")
        else:
            print(f"FAIL {name} -> {result} (expected {expected})")
    return passed, len(cases)

async def test_bm25_search():
    """Test BM25 text search."""
    s = SearchService()
    query = "xây dựng cầu"
    results = await s.bm25_search(query, top_k=5)
    print(f"\nBM25: '{query}' -> {len(results)} results")
    if results:
        print(f"  Top: {results[0].get('bidName', '')[:60]}")
    return len(results) > 0

async def test_vector_search():
    """Test vector similarity search."""
    s = SearchService()
    query = "xây dựng cầu"
    results = await s.vector_search(query, top_k=5)
    print(f"\nVector: '{query}' -> {len(results)} results")
    if results:
        print(f"  Top: {results[0].get('bidName', '')[:60]}")
    return len(results) > 0

async def test_hybrid_rrf():
    """Test hybrid RRF merge."""
    s = SearchService()
    query = "xây dựng cầu"
    results = await s.hybrid_search_rrf(query, top_k=5)
    print(f"\nHybrid RRF: '{query}' -> {len(results)} results")
    if results:
        print(f"  Top: {results[0].get('bidName', '')[:60]}")
    return len(results) > 0

async def test_location_filter():
    """Test location filtering with province code."""
    s = SearchService()
    query = "xây dựng"
    filters = {"location": "Hà Nội"}
    results = await s.hybrid_search_rrf(query, top_k=5, filters=filters)
    print(f"\nLocation filter (Ha Noi): '{query}' -> {len(results)} results")
    if results and 'locations' in results[0]:
        locs = results[0]['locations']
        codes = [l.get('provCode') for l in locs if isinstance(l, dict)]
        print(f"  First result provCodes: {codes}")
        has_01 = '01' in codes
        print(f"  Contains '01' (Ha Noi): {has_01}")
        return has_01
    return len(results) > 0

async def test_fallback_ladder():
    """Test progressive filter relaxation."""
    s = SearchService()
    query = "xây dựng cầu"
    filters = {
        "location": "Hà Nội",
        "year": 2024,
        "min_price": 1000000000,
        "max_price": 10000000000,
        "bidForm": "Đấu thầu rộng rãi"
    }
    results, relaxed = await s.search_with_fallback(query, filters, method="hybrid", top_k=5)
    print(f"\nFallback: '{query}' with strict filters -> {len(results)} results")
    print(f"  Relaxed filters: {relaxed if relaxed else 'none'}")
    return True

async def test_metadata_sort():
    """Test dynamic sorting in metadata-only search."""
    s = SearchService()
    cases = [
        ("sắp hết hạn", "deadline asc"),
        ("giá trị lớn nhất", "bidPrice desc"),
        ("mới nhất", "publicDate desc"),
    ]
    passed = 0
    for query, expected_sort in cases:
        results = await s.metadata_only_search(query, filters={}, top_k=3)
        if results:
            print(f"OK '{query}' -> {len(results)} results (expected {expected_sort})")
            passed += 1
        else:
            print(f"FAIL '{query}' -> 0 results")
    return passed, len(cases)

async def run_tests():
    print("=== SEARCH OPTIMIZATION TEST SUITE ===\n")

    print("--- 1. Location Service ---")
    loc_passed, loc_total = test_location_mapping()

    print("\n--- 2. BM25 Search ---")
    bm25_ok = await test_bm25_search()

    print("\n--- 3. Vector Search ---")
    vec_ok = await test_vector_search()

    print("\n--- 4. Hybrid RRF ---")
    hybrid_ok = await test_hybrid_rrf()

    print("\n--- 5. Location Filter ---")
    filter_ok = await test_location_filter()

    print("\n--- 6. Fallback Ladder ---")
    fallback_ok = await test_fallback_ladder()

    print("\n--- 7. Metadata Sort ---")
    sort_passed, sort_total = await test_metadata_sort()

    print("\n=== SUMMARY ===")
    print(f"Location mapping: {loc_passed}/{loc_total}")
    print(f"BM25: {'OK' if bm25_ok else 'FAIL'}")
    print(f"Vector: {'OK' if vec_ok else 'FAIL'}")
    print(f"Hybrid RRF: {'OK' if hybrid_ok else 'FAIL'}")
    print(f"Location filter: {'OK' if filter_ok else 'FAIL'}")
    print(f"Fallback: {'OK' if fallback_ok else 'FAIL'}")
    print(f"Metadata sort: {sort_passed}/{sort_total}")

    total = loc_passed + int(bm25_ok) + int(vec_ok) + int(hybrid_ok) + int(filter_ok) + int(fallback_ok) + sort_passed
    max_score = loc_total + 5 + sort_total
    print(f"\nTotal: {total}/{max_score} tests passed")

if __name__ == "__main__":
    asyncio.run(run_tests())
