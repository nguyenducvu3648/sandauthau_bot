"""Test location filter sau khi fix multi-code mapping."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Fix encoding Windows console
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.location_service import LocationService
from app.services.es_client import ESClient
from app.config import settings


def main():
    print("=== Test LocationService multi-code ===")

    # Test get_province_codes
    hanoi_codes = LocationService.get_province_codes("Hà Nội")
    print(f"Hà Nội codes: {hanoi_codes}")

    hcm_codes = LocationService.get_province_codes("TP. Hồ Chí Minh")
    print(f"TP.HCM codes: {hcm_codes}")

    # Test alias
    hanoi_alias = LocationService.get_province_codes("HN")
    print(f"HN alias: {hanoi_alias}")

    # Test backward compat
    hanoi_single = LocationService.get_province_code("Hà Nội")
    print(f"get_province_code (single): {hanoi_single}")

    # Test reverse lookup
    name_101 = LocationService.get_province_name("101")
    name_01 = LocationService.get_province_name("01")
    print(f"Code 101 -> {name_101}, Code 01 -> {name_01}")

    print("\n=== Test ES filter với multi-code ===")
    es = ESClient.get_client()
    index = settings.ES_INDEX

    # Filter Hà Nội với tất cả codes
    r = es.search(index=index, body={
        "size": 0,
        "track_total_hits": True,
        "query": {
            "nested": {
                "path": "locations",
                "query": {"terms": {"locations.provCode": hanoi_codes}}
            }
        }
    })
    total = r["hits"]["total"]["value"]
    print(f"Hà Nội (codes={hanoi_codes}): {total:,} docs")

    # So sánh với code cũ đơn lẻ
    r_old = es.search(index=index, body={
        "size": 0,
        "track_total_hits": True,
        "query": {
            "nested": {
                "path": "locations",
                "query": {"term": {"locations.provCode": "01"}}
            }
        }
    })
    total_old = r_old["hits"]["total"]["value"]
    print(f"Chỉ code 01: {total_old:,} docs")
    print(f"Tăng {total / total_old:.1f}x")


if __name__ == "__main__":
    main()
