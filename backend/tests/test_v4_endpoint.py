"""Test V4 API endpoint."""
import sys, io, os
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_v4_endpoint_basic():
    """Test basic V4 search endpoint."""
    import time

    t0 = time.time()
    response = client.post("/search/v4", json={
        "query": "thầu xây dựng Hà Nội",
        "top_k": 10,
        "session_id": "test_v4_basic"
    })
    t1 = time.time()

    assert response.status_code == 200
    data = response.json()

    assert "query" in data
    assert "total" in data
    assert "results" in data
    assert "took_ms" in data

    print(f"✓ Query: '{data['query']}'")
    print(f"✓ Total: {data['total']}")
    print(f"✓ Results returned: {len(data['results'])}")
    print(f"✓ Took (client): {(t1-t0)*1000:.0f}ms")
    print(f"✓ Took (server): {data['took_ms']:.0f}ms")

    # Verify ≤10 bids returned
    assert len(data['results']) <= 10, f"Expected ≤10 bids, got {len(data['results'])}"


def test_v4_pagination():
    """Test pagination with session."""
    session_id = "test_v4_pagination"

    # First request
    r1 = client.post("/search/v4", json={
        "query": "thầu xây dựng",
        "top_k": 5,
        "session_id": session_id
    })
    assert r1.status_code == 200
    d1 = r1.json()

    # Pagination request
    r2 = client.post("/search/v4", json={
        "query": "tiếp theo",
        "top_k": 5,
        "session_id": session_id
    })
    assert r2.status_code == 200
    d2 = r2.json()

    print(f"✓ First page: {len(d1['results'])} results")
    print(f"✓ Next page: {len(d2['results'])} results")

    # Clear session
    client.post(f"/search/cache/clear/{session_id}")


def test_v4_bid_code_fastpath():
    """Test bid code fast path."""
    response = client.post("/search/v4", json={
        "query": "221240000049",
        "top_k": 10,
        "session_id": "test_v4_fastpath"
    })

    assert response.status_code == 200
    data = response.json()

    # Should return 1 exact match
    assert data["total"] >= 1
    if data["results"]:
        print(f"✓ Bid code match: {data['results'][0]['bid_no']}")


if __name__ == "__main__":
    print("=== TEST V4 ENDPOINT ===\n")

    print("1. Basic search...")
    test_v4_endpoint_basic()

    print("\n2. Pagination...")
    test_v4_pagination()

    print("\n3. Bid code fast path...")
    test_v4_bid_code_fastpath()

    print("\n✓ All tests passed")
