#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test intent_analyzer_v2 với edge cases."""
import sys
import os
sys.path.insert(0, 'backend')

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.services.intent_analyzer_v2 import IntentAnalyzerV2

def test_edge_cases():
    """Test các trường hợp lỗi của v1."""
    cases = [
        # (query, expected_method, expected_filters, description)
        ("xây dựng cầu Hà Nội", "hybrid", {"location": "Hà Nội"}, "Có filter + keyword → hybrid với filter"),
        ("gói thầu ISO 9001", "hybrid", {}, "ISO không phải mã gói thầu → hybrid"),
        ("COVID-19", "hybrid", {}, "COVID không phải mã gói thầu → hybrid"),
        ("DT-2024-123", "bm25_code", {}, "Mã thật → bm25_code"),
        ("Hà Nội năm 2024", "metadata_only", {"location": "Hà Nội", "year": 2024}, "Chỉ filter → metadata_only"),
        ("xây dựng cầu", "hybrid", {}, "Chỉ keyword → hybrid"),
        ("gói thầu xây dựng cầu Hà Nội giá dưới 5 tỷ", "hybrid", {"location": "Hà Nội", "max_price": 5000000000}, "Filter + keyword → hybrid"),
    ]

    print("=" * 80)
    print("TEST EDGE CASES")
    print("=" * 80)

    passed = 0
    failed = 0

    for query, expected_method, expected_filters, desc in cases:
        result = IntentAnalyzerV2.analyze(query)

        method_ok = result.method == expected_method
        filters_ok = result.filters == expected_filters

        status = "PASS" if (method_ok and filters_ok) else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"\n{status} {desc}")
        print(f"  Query: {query}")
        print(f"  Method: {result.method} (expect: {expected_method})")
        print(f"  Filters: {result.filters} (expect: {expected_filters})")
        print(f"  Residual: '{result.residual}'")
        if result.needs_llm:
            print(f"  ⚠ Needs LLM")

    print(f"\n{'=' * 80}")
    print(f"RESULT: {passed} PASS, {failed} FAIL")
    print(f"{'=' * 80}")

def test_residual_extraction():
    """Test extraction residual."""
    print("\n" + "=" * 80)
    print("TEST RESIDUAL EXTRACTION")
    print("=" * 80)

    cases = [
        ("xây dựng cầu ở Hà Nội năm 2024", "xây dựng cầu ở"),
        ("gói thầu giá trên 10 tỷ TP.HCM", "gói thầu"),
        ("mua sắm thiết bị y tế", "mua sắm thiết bị y tế"),
    ]

    for query, expected_residual in cases:
        result = IntentAnalyzerV2.analyze(query)
        status = "PASS" if result.residual == expected_residual else "FAIL"
        print(f"\n{status} Query: {query}")
        print(f"  Residual: '{result.residual}'")
        print(f"  Expected: '{expected_residual}'")

def test_llm_signals():
    """Test tín hiệu cần LLM."""
    print("\n" + "=" * 80)
    print("TEST LLM SIGNALS")
    print("=" * 80)

    cases = [
        ("gói thầu không phải Hà Nội", True, "Phủ định"),
        ("so sánh DT-2024-1 và DT-2024-2", True, "So sánh"),
        ("gói thầu sắp hết hạn ở Đà Nẵng", True, "Thời gian tương đối"),
        ("xây dựng cầu Hà Nội", False, "Query bình thường"),
    ]

    for query, expected_llm, desc in cases:
        result = IntentAnalyzerV2.analyze(query)
        status = "PASS" if result.needs_llm == expected_llm else "FAIL"
        print(f"\n{status} {desc}")
        print(f"  Query: {query}")
        print(f"  Needs LLM: {result.needs_llm} (expect: {expected_llm})")

if __name__ == "__main__":
    test_edge_cases()
    test_residual_extraction()
    test_llm_signals()
