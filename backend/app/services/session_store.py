"""Session state cho V4: filters, topic, danh sách kết quả đã xếp hạng, phân trang."""
from typing import Any, Dict, List, Optional


class SessionStore:
    """
    Lưu trạng thái hội thoại theo session_id.

    Mục tiêu:
    - Câu nối tiếp ("thêm 5 gói nữa") phân trang trên danh sách đã xếp hạng, không re-query.
    - Biết được lần trước user hỏi gì, lọc gì để tái sử dụng.
    - Giới hạn số lần hỏi lại (clarification) để không hỏi liên tiếp.
    """

    MAX_CLARIFICATIONS = 2
    MAX_RESULT_IDS = 50

    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get(cls, session_id: Optional[str]) -> Dict[str, Any]:
        if not session_id:
            return cls._empty()
        if session_id not in cls._sessions:
            cls._sessions[session_id] = cls._empty()
        return cls._sessions[session_id]

    @classmethod
    def reset(cls, session_id: Optional[str]) -> None:
        if session_id and session_id in cls._sessions:
            cls._sessions[session_id] = cls._empty()

    @classmethod
    def clear(cls, session_id: str) -> None:
        cls._sessions.pop(session_id, None)

    @classmethod
    def _empty(cls) -> Dict[str, Any]:
        return {
            "filters": {},           # filter đã áp dụng lần trước
            "topic": "",             # chủ đề (từ khóa) lần trước
            "output_mode": "list",
            "last_result_ids": [],   # ID theo thứ tự đã xếp hạng (đã rerank)
            "last_results": [],      # doc tương ứng (rút gọn) để phân trang
            "last_offset": 0,
            "last_total": 0,
            "clarification_count": 0,
            "last_query": "",
        }

    @classmethod
    def save_plan(cls, session_id: Optional[str], plan, filters: Dict[str, Any]) -> None:
        """Ghi lại kế hoạch vừa thực hiện (không đụng danh sách kết quả)."""
        st = cls.get(session_id)
        st["filters"] = dict(filters or {})
        st["topic"] = getattr(plan, "topic", "") or st.get("topic", "")
        st["output_mode"] = getattr(plan, "output_mode", "list")
        st["last_query"] = getattr(plan, "query", "") or st.get("last_query", "")

    @classmethod
    def save_results(
        cls,
        session_id: Optional[str],
        results: List[Dict[str, Any]],
        total: int,
        offset: int = 0,
    ) -> None:
        """Lưu danh sách kết quả đã xếp hạng + vị trí phân trang."""
        st = cls.get(session_id)
        st["last_results"] = results
        st["last_result_ids"] = [cls._doc_id(r) for r in results][: cls.MAX_RESULT_IDS]
        st["last_total"] = total
        st["last_offset"] = offset
        # Có kết quả thì user đã "thỏa" -> reset bộ đếm hỏi lại
        st["clarification_count"] = 0

    @classmethod
    def next_page(cls, session_id: Optional[str], size: int) -> List[Dict[str, Any]]:
        """Lấy trang tiếp theo từ danh sách đã xếp hạng (không gọi lại search)."""
        st = cls.get(session_id)
        results = st.get("last_results") or []
        start = st.get("last_offset", 0)
        page = results[start: start + size]
        st["last_offset"] = start + len(page)
        return page

    @classmethod
    def mark_clarification(cls, session_id: Optional[str]) -> int:
        """Đánh dấu đã hỏi lại user, trả về số lần đã hỏi."""
        st = cls.get(session_id)
        st["clarification_count"] = st.get("clarification_count", 0) + 1
        return st["clarification_count"]

    @classmethod
    def has_results(cls, session_id: Optional[str]) -> bool:
        return bool(cls.get(session_id).get("last_results"))

    @staticmethod
    def _doc_id(doc: Dict[str, Any]) -> str:
        return str(doc.get("bidCode") or doc.get("bidNo") or doc.get("mongo_id") or id(doc))
