"""Location mapping service - V2 với multi-code mapping."""
import json
import os
import unicodedata
from typing import Optional, List

class LocationService:
    """Map location names to codes (v2: mỗi tỉnh có nhiều codes)."""

    _provinces = None

    @classmethod
    def _load_provinces(cls):
        if cls._provinces is None:
            # provinces_v2.json: {name: {codes: [..], aliases: [..], search_keys: [..]}}
            path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "provinces_v2.json")
            with open(path, "r", encoding="utf-8") as f:
                cls._provinces = json.load(f)
        return cls._provinces

    @classmethod
    def get_province_codes(cls, name: str) -> List[str]:
        """Lấy TẤT CẢ codes của tỉnh từ tên hoặc alias (v2: trả list thay vì 1 code)."""
        provinces = cls._load_provinces()
        name_lower = cls._deaccent(name.lower().strip())

        for prov_name, data in provinces.items():
            # Match tên chính
            if cls._deaccent(prov_name.lower()) == name_lower:
                return data["codes"]
            # Match alias
            if name_lower in [cls._deaccent(a.lower()) for a in data.get("aliases", [])]:
                return data["codes"]
            # Match search_keys
            if name_lower in data.get("search_keys", []):
                return data["codes"]
        return []

    @classmethod
    def get_province_code(cls, name: str) -> Optional[str]:
        """Backward compat: trả code đầu tiên (code mới, nhiều docs nhất)."""
        codes = cls.get_province_codes(name)
        return codes[0] if codes else None

    @classmethod
    def get_province_name(cls, code: str) -> Optional[str]:
        """Lấy tên chuẩn từ 1 code bất kỳ (cũ hoặc mới)."""
        provinces = cls._load_provinces()
        for prov_name, data in provinces.items():
            if code in data["codes"]:
                return prov_name
        return None

    @classmethod
    def normalize_location(cls, name: str) -> Optional[str]:
        """Chuẩn hóa tên địa điểm về tên chính thức."""
        codes = cls.get_province_codes(name)
        if codes:
            return cls.get_province_name(codes[0])
        return None

    @staticmethod
    def _deaccent(s: str) -> str:
        """Bỏ dấu: 'Hà Nội' -> 'ha noi'."""
        return "".join(c for c in unicodedata.normalize("NFD", s)
                       if unicodedata.category(c) != "Mn")


# Backward compat
def get_location_terms(location: str) -> List[str]:
    """Trả về danh sách terms để search (giữ cho code cũ)."""
    normalized = LocationService.normalize_location(location)
    return [normalized] if normalized else [location]
