"""Expand eval dataset from 20 to 100 questions - P3 prerequisite."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from pathlib import Path

# Load existing 20
base_dir = Path(__file__).parent.parent
eval_20 = json.loads((base_dir / "config" / "eval_20.json").read_text(encoding="utf-8"))

# Add 80 more questions covering 31 V3 errors + real patterns
new_questions = [
    # Price edge cases (V3_ERROR_04)
    {"id": 21, "query": "Thầu từ 2 tỷ đến 10 tỷ", "intent": "search", "expected_filters": {"min_price": 2000000000, "max_price": 10000000000}, "expected_method": "hybrid"},
    {"id": 22, "query": "Thầu từ 500 triệu đến 3 tỷ", "intent": "search", "expected_filters": {"min_price": 500000000, "max_price": 3000000000}, "expected_method": "hybrid"},
    {"id": 23, "query": "Thầu dưới 100 triệu", "intent": "search", "expected_filters": {"max_price": 100000000}, "expected_method": "hybrid"},
    {"id": 24, "query": "Thầu trên 100 tỷ", "intent": "search", "expected_filters": {"min_price": 100000000000}, "expected_method": "hybrid"},
    {"id": 25, "query": "Thầu khoảng 5 tỷ", "intent": "search", "expected_filters": {"approx_price": 5000000000}, "expected_method": "hybrid"},

    # Multiple locations (V3_ERROR_02)
    {"id": 26, "query": "Thầu ở Hải Phòng và Quảng Ninh", "intent": "search", "expected_filters": {"location": ["103", "31", "403", "22"]}, "expected_method": "hybrid"},
    {"id": 27, "query": "Thầu ở Bắc Giang, Bắc Ninh", "intent": "search", "expected_filters": {"location": ["124", "27", "106", "56"]}, "expected_method": "hybrid"},
    {"id": 28, "query": "Các tỉnh miền Trung", "intent": "search", "expected_filters": {}, "expected_method": "hybrid", "llm_signal": "region_ambiguous"},

    # Date filters (V3_ERROR_10, _11)
    {"id": 29, "query": "Thầu đóng sau ngày 15/01/2025", "intent": "search", "expected_filters": {"deadline_after": "2025-01-15"}, "expected_method": "metadata_only"},
    {"id": 30, "query": "Thầu đóng trước ngày 31/12/2024", "intent": "search", "expected_filters": {"deadline_before": "2024-12-31"}, "expected_method": "metadata_only"},
    {"id": 31, "query": "Thầu đăng hôm nay", "intent": "search", "expected_filters": {"published_today": True}, "expected_method": "metadata_only"},
    {"id": 32, "query": "Thầu đăng tuần này", "intent": "search", "expected_filters": {"published_this_week": True}, "expected_method": "metadata_only"},
    {"id": 33, "query": "Thầu hạn chót trong 7 ngày tới", "intent": "search", "expected_filters": {"deadline_within_days": 7}, "expected_method": "metadata_only"},

    # Negation (V3_ERROR_26)
    {"id": 34, "query": "Thầu không phải xây dựng", "intent": "search", "expected_filters": {}, "expected_method": "hybrid", "llm_signal": "negation"},
    {"id": 35, "query": "Thầu ngoài Hà Nội", "intent": "search", "expected_filters": {}, "expected_method": "hybrid", "llm_signal": "negation"},

    # Category keywords
    {"id": 36, "query": "Thầu cung cấp thiết bị y tế", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 37, "query": "Gói thầu mua sắm thuốc", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 38, "query": "Thầu mua sắm phương tiện vận tải", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 39, "query": "Thầu cung cấp văn phòng phẩm", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 40, "query": "Thầu mua sắm máy móc thiết bị", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},

    # Infrastructure keywords
    {"id": 41, "query": "Thầu xây dựng cầu đường", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 42, "query": "Gói thầu hạ tầng giao thông", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 43, "query": "Thầu xây trường học", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 44, "query": "Gói thầu bệnh viện đa khoa", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 45, "query": "Thầu hạ tầng kỹ thuật", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 46, "query": "Thầu hạ tầng xã hội", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 47, "query": "Gói thầu năng lượng tái tạo", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 48, "query": "Thầu nước sạch và vệ sinh môi trường", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},

    # Aggregation variations (V3_ERROR_09)
    {"id": 49, "query": "Tổng giá trị thầu xây dựng", "intent": "aggregation", "expected_filters": {}, "expected_method": "aggregation"},
    {"id": 50, "query": "Giá trung bình thầu xây dựng", "intent": "aggregation", "expected_filters": {}, "expected_method": "aggregation"},
    {"id": 51, "query": "Top 10 tỉnh có nhiều thầu nhất", "intent": "aggregation", "expected_filters": {}, "expected_method": "aggregation"},
    {"id": 52, "query": "So sánh số lượng thầu xây dựng và tư vấn", "intent": "aggregation", "expected_filters": {}, "expected_method": "aggregation", "llm_signal": "compare"},

    # Pagination variations (V3_ERROR_03, _07)
    {"id": 53, "query": "Xem thêm 10 kết quả", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "pagination"},
    {"id": 54, "query": "Trang tiếp theo", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "pagination"},
    {"id": 55, "query": "Lùi về trang trước", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "pagination"},
    {"id": 56, "query": "Thêm 5 gói nữa", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "pagination"},

    # Continuation context (V3_ERROR_12, _16, _31)
    {"id": 57, "query": "Chi tiết gói thầu đầu tiên", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "continuation"},
    {"id": 58, "query": "Gói thầu số 1", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "continuation"},
    {"id": 59, "query": "Tìm giống kết quả số 3", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "continuation"},
    {"id": 60, "query": "Tìm lại kết quả vừa rồi", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "continuation"},

    # Re-sort (V3_ERROR_27)
    {"id": 61, "query": "Sắp xếp theo giá thấp nhất", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "resort"},
    {"id": 62, "query": "Sắp xếp theo giá cao nhất", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "resort"},
    {"id": 63, "query": "Sắp xếp theo mới nhất", "intent": "search", "expected_filters": {}, "expected_method": "none", "llm_signal": "resort"},

    # Existence filters (V3_ERROR_28)
    {"id": 64, "query": "Thầu có số tiền dự toán", "intent": "search", "expected_filters": {"has_budget": True}, "expected_method": "metadata_only"},
    {"id": 65, "query": "Thầu chưa có giá", "intent": "search", "expected_filters": {"has_budget": False}, "expected_method": "metadata_only"},

    # Bid method filters
    {"id": 66, "query": "Thầu đấu thầu rộng rãi", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 67, "query": "Thầu chỉ định thầu", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 68, "query": "Gói thầu quốc tế", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},

    # Investor filter (V3_ERROR_17)
    {"id": 69, "query": "Lọc theo chủ đầu tư Bộ Y Tế", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 70, "query": "Thầu của Bộ Giao thông", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},

    # Complex multi-filter
    {"id": 71, "query": "Thầu xây dựng ở Hà Nội năm 2024 dưới 1 tỷ", "intent": "search", "expected_filters": {"location": ["101", "01", "213", "15"], "year": 2024, "max_price": 1000000000}, "expected_method": "hybrid"},
    {"id": 72, "query": "Tư vấn TP.HCM giá trên 2 tỷ sắp hết hạn", "intent": "search", "expected_filters": {"location": ["701", "79"], "min_price": 2000000000}, "expected_method": "hybrid"},

    # More domain-specific keywords
    {"id": 73, "query": "Thầu cung cấp nhiên liệu", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 74, "query": "Thầu xử lý rác thải", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 75, "query": "Thầu cải tạo nâng cấp", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 76, "query": "Thầu sửa chữa bảo trì", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 77, "query": "Thầu cung cấp điện", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 78, "query": "Thầu hệ thống thoát nước", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 79, "query": "Thầu thiết kế kiến trúc", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 80, "query": "Thầu khảo sát địa chất", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 81, "query": "Thầu giám sát thi công", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 82, "query": "Thầu đánh giá tác động môi trường", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 83, "query": "Thầu lập dự án đầu tư", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 84, "query": "Thầu mua sắm trang thiết bị trường học", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 85, "query": "Thầu cung cấp nước sạch", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 86, "query": "Thầu xây dựng đường nông thôn", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 87, "query": "Thầu hệ thống chiếu sáng công cộng", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 88, "query": "Thầu cung cấp hóa chất", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 89, "query": "Thầu bảo trì hệ thống CNTT", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 90, "query": "Thầu xây dựng kho bãi", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 91, "query": "Thầu cung cấp dịch vụ vệ sinh", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 92, "query": "Thầu mua sắm sách giáo khoa", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 93, "query": "Thầu xây dựng hệ thống thủy lợi", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 94, "query": "Thầu cung cấp nhiên liệu sinh học", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 95, "query": "Thầu cung cấp dịch vụ bảo vệ", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 96, "query": "Thầu xây dựng nhà máy xử lý nước thải", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 97, "query": "Thầu mua sắm phần mềm quản lý", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 98, "query": "Thầu cung cấp đồng phục", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 99, "query": "Thầu xây dựng sân vận động", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
    {"id": 100, "query": "Thầu cung cấp thiết bị phòng cháy chữa cháy", "intent": "search", "expected_filters": {}, "expected_method": "hybrid"},
]

# Merge
eval_100 = eval_20 + new_questions

# Save
output = base_dir / "config" / "eval_100.json"
output.write_text(json.dumps(eval_100, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"✓ Expanded to {len(eval_100)} questions")
print(f"Saved: {output}")
