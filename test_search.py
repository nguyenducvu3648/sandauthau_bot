#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test search system với 15 test cases."""
import json
import time
import requests
import sys
from typing import Dict, Any, List

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://localhost:8000"
SESSION_ID = "test_session_phase"

def test_intent_analysis(query: str, expected: Dict[str, Any]) -> Dict[str, Any]:
    """Test intent analyzer."""
    response = requests.post(
        f"{API_URL}/search/auto",
        json={"query": query, "top_k": 5, "session_id": SESSION_ID},
        timeout=30
    )

    if response.status_code != 200:
        return {
            "status": "FAIL",
            "error": f"HTTP {response.status_code}: {response.text[:200]}"
        }

    data = response.json()

    # Check intent
    intent_match = True
    if "expected_intent" in expected:
        intent_match = data.get("intent") == expected["expected_intent"]

    # Check filters
    filters_match = True
    expected_filters = expected.get("expected_filters", {})
    actual_filters = data.get("filters_applied", {})

    missing = []
    wrong = []
    for key, val in expected_filters.items():
        if key not in actual_filters:
            missing.append(key)
        elif actual_filters[key] != val:
            wrong.append(f"{key}: expected {val}, got {actual_filters[key]}")

    filters_match = len(missing) == 0 and len(wrong) == 0

    # Check methods
    methods_match = True
    expected_methods = expected.get("expected_methods", [])
    actual_methods = data.get("methods_used", [])

    if set(expected_methods) != set(actual_methods):
        methods_match = False

    # Build result
    passed = intent_match and filters_match and methods_match

    result = {
        "status": "PASS" if passed else "FAIL",
        "intent": data.get("intent"),
        "filters": actual_filters,
        "methods": actual_methods,
        "total_results": data.get("total", 0),
        "latency_ms": data.get("took_ms", 0)
    }

    if not passed:
        issues = []
        if not intent_match:
            issues.append(f"Intent mismatch")
        if missing:
            issues.append(f"Missing filters: {missing}")
        if wrong:
            issues.append(f"Wrong filters: {wrong}")
        if not methods_match:
            issues.append(f"Methods: expected {expected_methods}, got {actual_methods}")
        result["issues"] = issues

    return result


def run_tests():
    """Chạy tất cả test cases."""
    with open("test_queries.json", "r", encoding="utf-8") as f:
        tests = json.load(f)

    print("=" * 80)
    print("SEARCH SYSTEM TEST REPORT")
    print("=" * 80)
    print()

    results = []
    passed = 0
    failed = 0

    for test in tests:
        print(f"Test #{test['id']}: {test['description']}")
        print(f"Query: \"{test['query']}\"")

        try:
            result = test_intent_analysis(test["query"], test)
            results.append({**test, **result})

            if result["status"] == "PASS":
                passed += 1
                print(f"✓ PASS | Intent: {result['intent']} | Methods: {result['methods']} | Results: {result['total_results']} | {result['latency_ms']:.0f}ms")
            else:
                failed += 1
                print(f"✗ FAIL | {', '.join(result.get('issues', []))}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {str(e)}")
            results.append({**test, "status": "ERROR", "error": str(e)})

        print()
        time.sleep(0.5)  # Rate limiting

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total: {len(tests)} | Passed: {passed} | Failed: {failed}")
    print(f"Success Rate: {passed/len(tests)*100:.1f}%")
    print()

    # Breakdown by category
    categories = {
        "Simple keyword": [1, 2, 7],
        "Filter combinations": [3, 4, 5, 8, 9, 11, 14, 15],
        "Complex queries": [6],
        "Exact match (BM25)": [10],
        "Casual queries": [12, 13]
    }

    for cat, test_ids in categories.items():
        cat_results = [r for r in results if r["id"] in test_ids]
        cat_passed = sum(1 for r in cat_results if r.get("status") == "PASS")
        print(f"{cat}: {cat_passed}/{len(cat_results)} passed")

    # Save detailed results
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print()
    print("Detailed results saved to: test_results.json")


if __name__ == "__main__":
    run_tests()
