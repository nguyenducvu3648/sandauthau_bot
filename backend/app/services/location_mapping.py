"""Location canonical mapping để tối ưu wildcard search."""

# ponytail: dict mapping, không cần database
LOCATION_CANONICAL = {
    # Thành phố trực thuộc TW
    "Hà Nội": ["Thành phố Hà Nội", "TP Hà Nội", "Ha Noi"],
    "TP.HCM": ["Thành phố Hồ Chí Minh", "TP Hồ Chí Minh", "Ho Chi Minh", "Sai Gon", "Sài Gòn"],
    "Đà Nẵng": ["Thành phố Đà Nẵng", "TP Đà Nẵng", "Da Nang"],
    "Hải Phòng": ["Thành phố Hải Phòng", "TP Hải Phòng", "Hai Phong"],
    "Cần Thơ": ["Thành phố Cần Thơ", "TP Cần Thơ", "Can Tho"],

    # Các tỉnh
    "Bắc Ninh": ["Tỉnh Bắc Ninh", "Bac Ninh"],
    "Bình Dương": ["Tỉnh Bình Dương", "Binh Duong"],
    "Đồng Nai": ["Tỉnh Đồng Nai", "Dong Nai"],
    "Nghệ An": ["Tỉnh Nghệ An", "Nghe An"],
    "Thanh Hóa": ["Tỉnh Thanh Hóa", "Thanh Hoa"],
    "Thừa Thiên Huế": ["Tỉnh Thừa Thiên Huế", "Thua Thien Hue", "Huế", "Hue"],
    "Quảng Ninh": ["Tỉnh Quảng Ninh", "Quang Ninh"],
    "Lâm Đồng": ["Tỉnh Lâm Đồng", "Lam Dong"],
    "Khánh Hòa": ["Tỉnh Khánh Hòa", "Khanh Hoa"],
}

def get_location_terms(user_input: str) -> list[str]:
    """
    Trả về tất cả variants của location.

    VD: "Hà Nội" → ["Hà Nội", "Thành phố Hà Nội", "TP Hà Nội", "Ha Noi"]
    """
    # Normalize input
    normalized = user_input.strip()

    # Lookup canonical
    if normalized in LOCATION_CANONICAL:
        return [normalized] + LOCATION_CANONICAL[normalized]

    # Reverse lookup (user nhập variant)
    for canonical, variants in LOCATION_CANONICAL.items():
        if normalized in variants:
            return [canonical] + variants

    # Không tìm thấy → trả input gốc
    return [normalized]
