#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Đo precision/recall cho intent analyzer v2."""
import sys
import os
import json
import asyncio
from collections import defaultdict

sys.path.insert(0, 'backend')

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from backend.app.services.intent_analyzer_v2 import IntentAnalyzerV2


async def evaluate():
    """Đo precision/recall trên test set."""

    # Load test set
    with open('test_queries_100.jsonl', 'r', encoding='utf-8') as f:
        test_cases = json.load(f)

    results = {
        'intent': {'correct': 0, 'total': 0},
        'method': {'correct': 0, 'total': 0},
        'filters': {'correct': 0, 'total': 0, 'partial': 0},
    }

    errors_by_type = defaultdict(list)

    print(f"Đang test {len(test_cases)} queries...")
    print("=" * 80)

    for i, case in enumerate(test_cases, 1):
        query = case['query']
        expected_intent = case['intent']
        expected_method = case['method']
        expected_filters = case['filters']

        # Analyze
        analysis = await IntentAnalyzerV2.analyze(query)

        # Check intent
        results['intent']['total'] += 1
        if analysis.intent == expected_intent:
            results['intent']['correct'] += 1
        else:
            errors_by_type['intent'].append({
                'query': query,
                'expected': expected_intent,
                'actual': analysis.intent
            })

        # Check method
        results['method']['total'] += 1
        if analysis.method == expected_method:
            results['method']['correct'] += 1
        else:
            errors_by_type['method'].append({
                'query': query,
                'expected': expected_method,
                'actual': analysis.method
            })

        # Check filters (exact match vs partial)
        results['filters']['total'] += 1
        expected_keys = set(expected_filters.keys())
        actual_keys = set(analysis.filters.keys())

        if expected_keys == actual_keys:
            # Kiểm tra values
            all_match = True
            for key in expected_keys:
                if analysis.filters.get(key) != expected_filters[key]:
                    all_match = False
                    break

            if all_match:
                results['filters']['correct'] += 1
            else:
                results['filters']['partial'] += 1
                errors_by_type['filters_partial'].append({
                    'query': query,
                    'expected': expected_filters,
                    'actual': analysis.filters
                })
        else:
            errors_by_type['filters_missing'].append({
                'query': query,
                'expected': expected_keys,
                'actual': actual_keys
            })

        # Progress
        if i % 10 == 0:
            print(f"  Processed {i}/{len(test_cases)} queries...")

    print("=" * 80)
    print("\nKẾT QUẢ:\n")

    # Intent accuracy
    intent_acc = results['intent']['correct'] / results['intent']['total'] * 100
    print(f"Intent Detection:")
    print(f"  Accuracy: {intent_acc:.1f}% ({results['intent']['correct']}/{results['intent']['total']})")

    # Method accuracy
    method_acc = results['method']['correct'] / results['method']['total'] * 100
    print(f"\nMethod Selection:")
    print(f"  Accuracy: {method_acc:.1f}% ({results['method']['correct']}/{results['method']['total']})")

    # Filter extraction
    filter_exact = results['filters']['correct'] / results['filters']['total'] * 100
    filter_partial = results['filters']['partial'] / results['filters']['total'] * 100
    print(f"\nFilter Extraction:")
    print(f"  Exact match: {filter_exact:.1f}% ({results['filters']['correct']}/{results['filters']['total']})")
    print(f"  Partial match: {filter_partial:.1f}% ({results['filters']['partial']}/{results['filters']['total']})")
    print(f"  Wrong: {100 - filter_exact - filter_partial:.1f}%")

    # Error breakdown
    print(f"\n\nLỖI THEO LOẠI:\n")

    if errors_by_type['intent']:
        print(f"Intent errors ({len(errors_by_type['intent'])}):")
        for err in errors_by_type['intent'][:5]:
            print(f"  - '{err['query']}': {err['expected']} → {err['actual']}")
        if len(errors_by_type['intent']) > 5:
            print(f"  ... và {len(errors_by_type['intent']) - 5} lỗi khác")

    if errors_by_type['method']:
        print(f"\nMethod errors ({len(errors_by_type['method'])}):")
        for err in errors_by_type['method'][:5]:
            print(f"  - '{err['query']}': {err['expected']} → {err['actual']}")
        if len(errors_by_type['method']) > 5:
            print(f"  ... và {len(errors_by_type['method']) - 5} lỗi khác")

    if errors_by_type['filters_missing']:
        print(f"\nFilter missing keys ({len(errors_by_type['filters_missing'])}):")
        for err in errors_by_type['filters_missing'][:5]:
            missing = err['expected'] - err['actual']
            extra = err['actual'] - err['expected']
            print(f"  - '{err['query']}':")
            if missing:
                print(f"      Thiếu: {missing}")
            if extra:
                print(f"      Thừa: {extra}")
        if len(errors_by_type['filters_missing']) > 5:
            print(f"  ... và {len(errors_by_type['filters_missing']) - 5} lỗi khác")

    if errors_by_type['filters_partial']:
        print(f"\nFilter wrong values ({len(errors_by_type['filters_partial'])}):")
        for err in errors_by_type['filters_partial'][:3]:
            print(f"  - '{err['query']}':")
            print(f"      Expected: {err['expected']}")
            print(f"      Actual:   {err['actual']}")
        if len(errors_by_type['filters_partial']) > 3:
            print(f"  ... và {len(errors_by_type['filters_partial']) - 3} lỗi khác")

    # Overall
    total_checks = results['intent']['total'] + results['method']['total'] + results['filters']['total']
    total_correct = results['intent']['correct'] + results['method']['correct'] + results['filters']['correct']
    overall_acc = total_correct / total_checks * 100

    print(f"\n{'=' * 80}")
    print(f"TỔNG KẾT: {overall_acc:.1f}% accuracy ({total_correct}/{total_checks} checks)")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    asyncio.run(evaluate())
