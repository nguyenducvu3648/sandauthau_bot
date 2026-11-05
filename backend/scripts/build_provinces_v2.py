"""Sinh config/provinces_v2.json tu index that: moi don vi -> tat ca provCode tim thay.

Mapping thuc te cua index co 2 he ma (cu 2 so va moi 3 so) cho cung mot tinh,
nen mot ten tinh phai tro toi NHIEU code va filter phai dung `terms` chu khong dung `term`.

Chay: python scripts/build_provinces_v2.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.es_client import ESClient

ROOT = Path(__file__).resolve().parent.parent

# Ten tinh chuan -> danh sach code (cu + moi). Thu tu uu tien: code moi truoc.
# 63 don vi cu -> 34 don vi moi (ke hoach sap xep 2025).
PROVINCE_CODES = {
    "Hà Nội":                 ["101", "01", "213", "15"],
    "TP. Hồ Chí Minh":       ["701", "79"],
    "Hải Phòng":             ["103", "31"],
    "Đà Nẵng":               ["501", "48"],
    "Cần Thơ":               ["815", "92"],
    "Tuyên Quang":           ["211", "08"],
    "Lào Cai":               ["205"],
    "Yên Bái":               ["15"],
    "Điện Biên":            ["301"],
    "Phú Thọ":               ["217", "25"],
    "Vĩnh Phúc":             ["219"],
    "Hòa Bình":              ["305"],
    "Hưng Yên":              ["109", "33"],
    "Thái Bình":             ["115"],
    "Nam Định":              ["113"],
    "Thanh Hóa":             ["401", "38"],
    "Nghệ An":              ["403", "40"],
    "Hà Tĩnh":              ["405", "42"],
    "Quảng Bình":            ["407", "46"],
    "Quảng Trị":             ["409"],
    "Thừa Thiên Huế":        ["411"],
    "Quảng Nam":             ["503"],
    "Quảng Ngãi":            ["505"],
    "Bình Định":             ["507", "52"],
    "Phú Yên":               ["509"],
    "Khánh Hòa":             ["511", "56"],
    "Ninh Thuận":            ["705"],
    "Bình Thuận":            ["715"],
    "Đồng Nai":              ["713", "75"],
    "Bình Phước":            ["707"],
    "Tây Ninh":              ["709", "80"],
    "Long An":               ["801"],
    "Đồng Tháp":            ["803", "82"],
    "An Giang":              ["805", "91"],
    "Kiên Giang":            ["813"],
    "Cà Mau":                ["823", "96"],
    "Bạc Liêu":              ["821"],
    "Bến Tre":               ["811"],
    "Vĩnh Long":             ["809", "86"],
    "Tiền Giang":            ["807"],
    "Sóc Trăng":             ["819"],
    "Bắc Ninh":              ["223", "24"],
    "Bắc Giang":             ["221"],
    "Thái Nguyên":           ["215", "19"],
    "Lạng Sơn":              ["209", "20"],
    "Cao Bằng":              ["203", "04"],
    "Bắc Kạn":               ["207"],
    "Hà Giang":              ["201"],
    "Tuyên Quang cũ":        ["08"],
}

# Alias text -> ten tinh chuan (bo sung alias tu provinces.json cu)
EXTRA_ALIASES = {
    "Hà Nội": ["HN", "hanoi", "ha noi", "thủ đô", "thu do", "tp hà nội", "tp ha noi",
               "thành phố hà nội", "thanh pho ha noi"],
    "TP. Hồ Chí Minh": ["HCM", "TPHCM", "TP HCM", "hồ chí minh", "ho chi minh",
                        "sài gòn", "sai gon", "saigon", "tp. hồ chí minh",
                        "thành phố hồ chí minh"],
    "Đà Nẵng": ["ĐN", "da nang", "danang", "tp. đà nẵng", "thành phố đà nẵng"],
    "Hải Phòng": ["HP", "hai phong", "haiphong", "tp. hải phòng", "thành phố hải phòng"],
    "Cần Thơ": ["CT", "can tho", "cantho", "tp. cần thơ", "thành phố cần thơ"],
    "Bà Rịa - Vũng Tàu": ["BRVT", "vũng tàu", "vung tau", "ba ria", "BRVTVT"],
    "Nghệ An": ["nghe an", "tp vinh", "vinh"],
    "Quảng Ninh": ["quang ninh", "hạ long", "ha long", "halong"],
    "Khánh Hòa": ["khanh hoa", "nha trang"],
    "Lâm Đồng": ["lam dong", "đà lạt", "da lat"],
    "Thừa Thiên Huế": ["huế", "hue", "thua thien hue", "tp huế"],
    "Bình Dương": ["binh duong", "BD", "thủ dầu mộc"],
    "Đắk Lắk": ["dak lak", "daklak", "đắk lắk"],
    "Đắk Nông": ["dak nong", "daknong"],
    "Bình Định": ["binh dinh"],
    "Bình Phước": ["binh phuoc"],
    "Bình Thuận": ["binh thuan"],
    "Đồng Nai": ["dong nai"],
    "Đồng Tháp": ["dong thap"],
    "Quảng Nam": ["quang nam"],
    "Quảng Ngãi": ["quang ngai"],
    "Quảng Bình": ["quang binh"],
    "Quảng Trị": ["quang tri"],
    "Phú Thọ": ["phu tho"],
    "Phú Yên": ["phu yen"],
    "Thái Bình": ["thai binh"],
    "Thái Nguyên": ["thai nguyen"],
    "Tuyên Quang": ["tuyen quang"],
    "Vĩnh Phúc": ["vinh phuc"],
    "Vĩnh Long": ["vinh long"],
    "Tiền Giang": ["tien giang"],
    "Trà Vinh": ["tra vinh"],
    "Sóc Trăng": ["soc trang"],
    "Tây Ninh": ["tay ninh"],
    "Thanh Hóa": ["thanh hoa"],
    "Hà Tĩnh": ["ha tinh"],
    "Hà Nam": ["ha nam"],
    "Hưng Yên": ["hung yen"],
    "Hòa Bình": ["hoa binh"],
    "Hoà Bình": ["hoa binh"],
    "Nam Định": ["nam dinh"],
    "Ninh Bình": ["ninh binh"],
    "Ninh Thuận": ["ninh thuan"],
    "Hà Giang": ["ha giang"],
    "Cao Bằng": ["cao bang"],
    "Bắc Kạn": ["bac kan"],
    "Bắc Giang": ["bac giang"],
    "Bắc Ninh": ["bac ninh"],
    "Bến Tre": ["ben tre"],
    "Bạc Liêu": ["bac lieu"],
    "Cà Mau": ["ca mau"],
    "Kiên Giang": ["kien giang"],
    "Long An": ["long an"],
    "An Giang": ["an giang"],
    "Bắc Giang": ["bac giang"],
    "Gia Lai": ["gia lai"],
    "Kon Tum": ["kon tum", "kontum"],
    "Lai Châu": ["lai chau"],
    "Lào Cai": ["lao cai"],
    "Sơn La": ["son la"],
    "Yên Bái": ["yen bai"],
    "Điện Biên": ["dien bien"],
    "Hòa Bình": ["hoa binh"],
}


def strip_prefix(name: str) -> str:
    """'Tỉnh Thanh Hoá' -> 'Thanh Hoá'; 'Thành phố Hà Nội' -> 'Hà Nội'."""
    for p in ("Tỉnh ", "Thành phố ", "TP. ", "TP "):
        if name.startswith(p):
            return name[len(p):]
    return name


def main():
    es = ESClient.get_client()
    index = settings.ES_INDEX

    # Lay code -> ten that tu index
    r = es.search(index=index, body={
        "size": 0,
        "aggs": {"loc": {"nested": {"path": "locations"},
                         "aggs": {"p": {"terms": {"field": "locations.provCode", "size": 300}}}}},
    })
    buckets = r.get("aggregations", {}).get("loc", {}).get("p", {}).get("buckets", [])

    # code -> (ten trong index, so docs)
    # Lay ten bang 1 request duy nhat (1000 docs, doc lai locations.provName)
    # thay vi 99 request term-query (cham).
    es_map = {b["key"]: {"raw_name": "", "doc_count": b["doc_count"]} for b in buckets}

    r = es.search(index=index, body={
        "size": 1000,
        "_source": ["locations.provName", "locations.provCode"],
        "query": {"nested": {"path": "locations",
                             "query": {"exists": {"field": "locations.provCode"}}}},
    })
    for h in r.get("hits", {}).get("hits", []):
        for loc in (h["_source"].get("locations") or []):
            code = loc.get("provCode")
            nm = loc.get("provName")
            if code and nm and not es_map.get(code, {}).get("raw_name"):
                es_map[code]["raw_name"] = nm

    # Gom code theo ten chuan
    by_name = {}
    for code, meta in es_map.items():
        clean = strip_prefix(meta["raw_name"] or "")
        by_name.setdefault(clean, []).append(code)

    # Ten chuan (chu hoa dau de khop): dung PROVINCE_CODES lam chuan, bo sung ten xuat hien trong index
    canonical = {}
    all_codes_seen = set(es_map.keys())

    def add(name, codes):
        canonical[name] = {"codes": codes}

    # 1) Ten co trong PROVINCE_CODES
    for name, codes in PROVINCE_CODES.items():
        valid = [c for c in codes if c in all_codes_seen]
        if valid:
            add(name, valid)

    # 2) Ten chi xuat hien trong index (chua biet) -> them vao, giu nguyen ten
    known_clean = {strip_prefix(n) for n in PROVINCE_CODES}
    for clean, codes in sorted(by_name.items(), key=lambda x: -len(x[1])):
        if clean in known_clean:
            continue
        if clean in ("Toàn quốc", "Ngoài lãnh thổ Việt Nam", ""):
            continue
        add(clean, codes)

    # 3) Alias: tu provinces.json cu + EXTRA_ALIASES
    old = json.loads((ROOT / "config" / "provinces.json").read_text(encoding="utf-8"))
    # ten cu -> ten chuan (doi chieu bang ten bo dau)
    def norm(s):
        return strip_prefix(s).lower().strip()

    clean_to_canon = {}
    for name in canonical:
        clean_to_canon[norm(name)] = name
    for name in PROVINCE_CODES:
        clean_to_canon[norm(name)] = name

    for old_name, data in old.items():
        target = clean_to_canon.get(norm(old_name))
        if target:
            for a in data.get("aliases", []):
                canonical[target].setdefault("aliases", [])
                if a not in canonical[target]["aliases"]:
                    canonical[target]["aliases"].append(a)
            canonical[target]["aliases"].append(old_name)

    for name, aliases in EXTRA_ALIASES.items():
        target = clean_to_canon.get(norm(name))
        if not target:
            continue
        canonical[target].setdefault("aliases", [])
        for a in aliases:
            if a not in canonical[target]["aliases"]:
                canonical[target]["aliases"].append(a)

    # 4) Alias chuan hoa (lower, khong dau -> lower)
    def deaccent(s):
        import unicodedata
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn").lower().strip()

    for name, data in canonical.items():
        data.setdefault("aliases", [])
        data["aliases"] = sorted(set(data["aliases"]), key=lambda x: (len(x), x))
        data["search_keys"] = sorted({deaccent(name), *{deaccent(a) for a in data["aliases"]}})
        # doc_count gan cho code dau tien (de biet tinh nhung)
        data["doc_count"] = max(es_map[c]["doc_count"] for c in data["codes"])

    out = ROOT / "config" / "provinces_v2.json"
    out.write_text(json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out}")
    print(f"canonical units: {len(canonical)}")
    total_codes = sum(len(d["codes"]) for d in canonical.values())
    print(f"codes mapped: {total_codes} / {len(es_map)} in index")
    missing = sorted(all_codes_seen - {c for d in canonical.values() for c in d["codes"]})
    print(f"unmapped index codes: {missing}")
    for name, data in sorted(canonical.items(), key=lambda x: -x[1]["doc_count"]):
        print(f"  {name}: codes={data['codes']} docs<={data['doc_count']}")


if __name__ == "__main__":
    main()
