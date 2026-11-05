#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test Phase 2 fixes."""
import sys
import os
import asyncio
sys.path.insert(0, 'backend')

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from app.services.intent_analyzer import IntentAnalyzer

async def test_casual_fix():
    """Test casual regex không match mixed queries."""
    print("=" * 60)
    print("TEST: Casual Regex Fix")
    print("=" * 60)

    cases = [
        ("xin chào", "casual", "Pure greeting"),
        ("cảm ơn", "casual", "Pure thanks"),
        ("Xin chào, tìm giúp tôi gói thầu xây dựng", "search", "Mixed query"),
        ("hi tôi muốn tìm thầu Hà Nội", "search", "Mixed greeting"),
    ]

    for query, expected, desc in cases:
        result = await IntentAnalyzer.analyze(query)
        intent = result["intent"]
        status = "PASS" if intent == expected else "FAIL"
        print(f"{status} {desc}")
        print(f"  Query: {query}")
        print(f"  Expected: {expected}, Got: {intent}")
        print()

async def test_aggregation():
    """Test aggregation detection."""
    print("=" * 60)
    print("TEST: Aggregation Detection")
    print("=" * 60)

    cases = [
        ("tỉnh nào có nhiều gói thầu nhất", "aggregation"),
        ("bao nhiêu gói thầu ở Hà Nội", "aggregation"),
        ("top 10 tỉnh có giá trị thầu cao nhất", "aggregation"),
        ("xây dựng cầu Hà Nội", "search"),
    ]

    for query, expected in cases:
        result = await IntentAnalyzer.analyze(query)
        intent = result["intent"]
        status = "PASS" if intent == expected else "FAIL"
        print(f"{status} Query: {query}")
        print(f"  Expected: {expected}, Got: {intent}")
        print()

async def main():
    await test_casual_fix()
    await test_aggregation()

if __name__ == "__main__":
    asyncio.run(main())
