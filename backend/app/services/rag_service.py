"""RAG service - Generate answers from retrieved docs."""
from typing import List, Dict, Any, AsyncIterator
from .deepseek_client import DeepSeekClient


class RAGService:
    """Generate answers with citations from retrieved tender docs."""

    @staticmethod
    async def generate_answer(query: str, docs: List[Dict[str, Any]]) -> AsyncIterator[str]:
        """
        Stream answer chunks với citations.

        Args:
            query: User query
            docs: Top-k retrieved tender documents

        Yields:
            Answer text chunks
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[RAG] generate_answer called: query={query[:60]}, docs_count={len(docs)}")

        if not docs:
            yield "Không tìm thấy gói thầu nào phù hợp."
            return

        # Build context từ docs
        context = RAGService._build_context(docs)

        # Prompt
        prompt = f"""Bạn là trợ lý tìm kiếm gói thầu. Dựa trên các gói thầu dưới đây, hãy trả lời câu hỏi của người dùng.

<context>
{context}
</context>

<question>
{query}
</question>

Yêu cầu:
- Trả lời ngắn gọn, trực tiếp
- Trích dẫn thông tin từ context bằng [1], [2], ...
- Nếu không có thông tin, nói rõ
- Không bịa thông tin không có trong context

Trả lời:"""

        # Generate answer với streaming
        messages = [{"role": "user", "content": prompt}]
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[RAG] Starting LLM stream for query: {query[:60]}")
        try:
            chunk_count = 0
            async for chunk in DeepSeekClient.chat_stream(messages, max_tokens=1000):
                chunk_count += 1
                if chunk_count <= 2:
                    logger.info(f"[RAG] Chunk {chunk_count}: {len(chunk)} chars")
                yield chunk
            logger.info(f"[RAG] Stream done, total {chunk_count} chunks")
        except Exception as e:
            logger.error(f"[RAG] Stream error: {type(e).__name__}: {e}", exc_info=True)
            yield f"\n\n⚠️ Lỗi LLM: {str(e)}"

    @staticmethod
    def _format_locations(locations: Any) -> str:
        """Format locations thành string. locations có thể là list[str] hoặc list[dict]."""
        if not locations:
            return ""
        if isinstance(locations, str):
            return locations

        parts = []
        for loc in locations:
            if isinstance(loc, dict):
                # Ưu tiên tỉnh/huyện, bỏ qua field rỗng
                name = (
                    loc.get("districtName")
                    or loc.get("wardName")
                    or loc.get("provName")
                    or loc.get("provCode")
                    or ""
                )
                if name:
                    parts.append(str(name))
            else:
                parts.append(str(loc))

        # Bỏ trùng lặp, giữ thứ tự
        seen = set()
        unique = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        return ", ".join(unique)

    @staticmethod
    def _build_context(docs: List[Dict[str, Any]]) -> str:
        """Format docs thành context cho LLM."""
        lines = []
        for i, doc in enumerate(docs[:10], 1):  # Top 10 docs
            bid_name = doc.get("bidName", "")
            bid_no = doc.get("bidNo", "")
            entity = doc.get("procuringEntityName", "")
            price = doc.get("bidPrice")
            locations = RAGService._format_locations(doc.get("locations"))
            open_date = doc.get("bidOpenDate", "")
            close_date = doc.get("bidCloseDate", "")

            lines.append(f"[{i}] {bid_name}")
            if bid_no:
                lines.append(f"    Mã: {bid_no}")
            if entity:
                lines.append(f"    Bên mời thầu: {entity}")
            if price:
                lines.append(f"    Giá: {price:,.0f} VNĐ")
            if locations:
                lines.append(f"    Địa điểm: {locations}")
            if open_date:
                lines.append(f"    Mở thầu: {open_date}")
            if close_date:
                lines.append(f"    Đóng thầu: {close_date}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_citations(docs: List[Dict[str, Any]]) -> str:
        """Format citations list."""
        lines = ["\n**Nguồn tham khảo:**"]
        for i, doc in enumerate(docs[:10], 1):
            bid_name = (doc.get("bidName") or "")[:80]
            bid_no = doc.get("bidNo") or ""
            if bid_no:
                lines.append(f"[{i}] {bid_name} (Mã: {bid_no})")
            else:
                lines.append(f"[{i}] {bid_name}")
        return "\n".join(lines)

