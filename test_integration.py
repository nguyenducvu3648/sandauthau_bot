#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test integration với backend."""
import sys
import os
import requests
import json

sys.path.insert(0, 'backend')

# Fix Windows encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

BASE_URL = "http://localhost:8001/search"

def test_auto_search():
    """Test /auto endpoint với v2."""
    print("=" * 80)
    print("TEST /auto ENDPOINT")
    print("=" * 80)

    test_cases = [
        ("xây dựng cầu Hà Nội", "hybrid", {"location": "Hà Nội"}),
        ("DT-2024-123", "bm25_code", {}),
        ("Hà Nội năm 2024", "metadata_only", {"location": "Hà Nội", "year": 2024}),
        ("xin chào", "casual", {}),
    ]

    for query, expected_method, expected_filters in test_cases:
        try:
            response = requests.post(f"{BASE_URL}/auto", json={
                "query": query,
                "top_k": 10
            }, timeout=10)

            if response.status_code == 200:
                data = response.json()
                methods_used = data.get("methods_used", [])
                filters_applied = data.get("filters_applied", {})
                intent = data.get("intent", "")

                # Kiểm tra method
                method_ok = expected_method in methods_used or (expected_method == "casual" and intent == "casual")

                # Kiểm tra filters (chỉ so sánh keys)
                filters_ok = set(expected_filters.keys()) == set(filters_applied.keys())

                status = "PASS" if (method_ok and filters_ok) else "FAIL"

                print(f"\n{status} Query: {query}")
                print(f"  Intent: {intent}")
                print(f"  Method: {methods_used} (expect: {expected_method})")
                print(f"  Filters: {list(filters_applied.keys())} (expect: {list(expected_filters.keys())})")
                print(f"  Results: {data.get('total', 0)}")
            else:
                print(f"\nFAIL Query: {query}")
                print(f"  Status: {response.status_code}")
                print(f"  Error: {response.text[:200]}")

        except requests.exceptions.ConnectionError:
            print(f"\nERROR: Backend không chạy. Start backend với:")
            print(f"  cd backend && uvicorn app.main:app --reload --port 8000")
            return
        except Exception as e:
            print(f"\nERROR Query: {query}")
            print(f"  Exception: {str(e)}")

if __name__ == "__main__":
    test_auto_search()
