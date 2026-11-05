"""
Build provinces_34.json từ Nghị quyết 202/2025/QH15.
Mapping 34 tỉnh mới → tất cả codes của các tỉnh cũ đã sáp nhập.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from pathlib import Path
from elasticsearch import Elasticsearch

# Load old 67-province mapping
base_dir = Path(__file__).parent.parent
old_data = json.loads((base_dir / "config" / "provinces_v2.json").read_text(encoding="utf-8"))

# 34 tỉnh theo Nghị quyết 202/2025/QH15
MERGE_MAP = {
    "Tuyên Quang": ["Hà Giang", "Tuyên Quang"],
    "Lào Cai": ["Lào Cai", "Yên Bái"],
    "Thái Nguyên": ["Bắc Kạn", "Thái Nguyên"],
    "Phú Thọ": ["Phú Thọ", "Vĩnh Phúc", "Hòa Bình"],
    "Bắc Ninh": ["Bắc Ninh", "Bắc Giang"],
    "Hưng Yên": ["Hưng Yên", "Thái Bình"],
    "Hải Phòng": ["Hải Phòng", "Hải Dương"],
    "Ninh Bình": ["Ninh Bình", "Nam Định", "Hà Nam"],
    "Quảng Trị": ["Quảng Trị", "Quảng Bình"],
    "Đà Nẵng": ["Đà Nẵng", "Quảng Nam"],
    "Quảng Ngãi": ["Quảng Ngãi", "Kon Tum"],
    "Gia Lai": ["Gia Lai", "Bình Định"],
    "Khánh Hòa": ["Khánh Hòa", "Ninh Thuận"],
    "Lâm Đồng": ["Lâm Đồng", "Đắk Nông", "Bình Thuận"],
    "Đắk Lắk": ["Đắk Lắk", "Phú Yên"],
    "TP. Hồ Chí Minh": ["TP. Hồ Chí Minh", "Bình Dương", "Bà Rịa - Vũng Tàu"],
    "Đồng Nai": ["Đồng Nai", "Bình Phước"],
    "Tây Ninh": ["Tây Ninh", "Long An"],
    "Cần Thơ": ["Cần Thơ", "Hậu Giang", "Sóc Trăng"],
    "Vĩnh Long": ["Vĩnh Long", "Bến Tre", "Trà Vinh"],
    "Đồng Tháp": ["Đồng Tháp", "Tiền Giang"],
    "Cà Mau": ["Cà Mau", "Bạc Liêu"],
    "An Giang": ["An Giang", "Kiên Giang"],
    "Hà Nội": ["Hà Nội"],
    "Cao Bằng": ["Cao Bằng"],
    "Điện Biên": ["Điện Biên"],
    "Lai Châu": ["Lai Châu"],
    "Sơn La": ["Sơn La"],
    "Lạng Sơn": ["Lạng Sơn"],
    "Quảng Ninh": ["Quảng Ninh"],
    "Thanh Hóa": ["Thanh Hóa"],
    "Nghệ An": ["Nghệ An"],
    "Hà Tĩnh": ["Hà Tĩnh"],
    "Huế": ["Thừa Thiên Huế"],
}

def normalize(name):
    """Match logic from location_service."""
    return name.lower().replace(".", "").replace("  ", " ").strip()

# Build 34-province mapping
provinces_34 = {}

for new_name, old_names in MERGE_MAP.items():
    codes = []
    aliases = set()
    search_keys = set()
    doc_count = 0

    for old_name in old_names:
        # Find in old data (match by normalized name)
        old_norm = normalize(old_name)
        matched = None

        for k, v in old_data.items():
            if normalize(k) == old_norm:
                matched = v
                break
            # Check aliases
            if "aliases" in v:
                for alias in v["aliases"]:
                    if normalize(alias) == old_norm:
                        matched = v
                        break

        if matched:
            codes.extend(matched["codes"])
            if "aliases" in matched:
                aliases.update(matched["aliases"])
            if "search_keys" in matched:
                search_keys.update(matched["search_keys"])
            doc_count += matched.get("doc_count", 0)
        else:
            print(f"⚠ '{old_name}' not found in old data - will need manual code mapping")

    # Add old names as aliases
    aliases.update(old_names)
    search_keys.update([normalize(n) for n in old_names])

    provinces_34[new_name] = {
        "codes": list(set(codes)) if codes else [],  # dedupe, empty if no codes found
        "aliases": sorted(aliases),
        "search_keys": sorted(search_keys),
        "merged_from": old_names if len(old_names) > 1 else [],
        "doc_count": doc_count,
        "missing_old_data": [n for n in old_names if not any(
            normalize(n) == normalize(k) or
            (normalize(n) in [normalize(a) for a in v.get("aliases", [])])
            for k, v in old_data.items()
        )]
    }

# Save
output = base_dir / "config" / "provinces_34.json"
output.write_text(json.dumps(provinces_34, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"✓ Built {len(provinces_34)} provinces")
print(f"Total codes: {sum(len(p['codes']) for p in provinces_34.values())}")
print(f"Total docs: {sum(p['doc_count'] for p in provinces_34.values()):,}")
print(f"Saved: {output}")

# Show sample
print("\n=== Sample ===")
for name in ["Hà Nội", "TP. Hồ Chí Minh", "Phú Thọ"]:
    p = provinces_34[name]
    print(f"{name}: {len(p['codes'])} codes, {p['doc_count']:,} docs")
    if p.get("merged_from"):
        print(f"  ← {', '.join(p['merged_from'])}")
