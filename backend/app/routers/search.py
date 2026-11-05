"""Search router."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import time
import json

from ..models import (
    BM25SearchRequest,
    VectorSearchRequest,
    HybridSearchRequest,
    FilterSearchRequest,
    AutoSearchRequest,
    SearchResponse,
    SearchResult
)
from ..services.search import SearchService
from ..services.advanced_search import AdvancedSearchService
from ..services.intent_analyzer_v2 import IntentAnalyzerV2
from ..services.deepseek_client import DeepSeekClient
from ..services.cache_service import CacheService
from ..services.rag_service import RAGService
from ..services.search_service_v4 import SearchServiceV4
from ..services.session_store import SessionStore

router = APIRouter(prefix="/search", tags=["search"])
search_service = SearchService()
advanced_search_service = AdvancedSearchService()
search_service_v4 = SearchServiceV4()

def _parse_hits(hits: Dict[str, Any], took_ms: float, query: str) -> SearchResponse:
    """Parse ES hits to SearchResponse."""
    results = []
    for hit in hits["hits"]["hits"]:
        source = hit["_source"]
        results.append(SearchResult(
            score=hit["_score"],
            mongo_id=source["mongo_id"],
            bid_no=source.get("bidNo"),
            bid_name=source.get("bidName", ""),
            procuring_entity=source.get("procuringEntityName", ""),
            bid_price=source.get("bidPrice"),
            bid_price_unit=source.get("bidPriceUnit"),
            bid_open_date=source.get("bidOpenDate"),
            bid_close_date=source.get("bidCloseDate"),
            locations=source.get("locations")
        ))

    return SearchResponse(
        query=query,
        total=hits["hits"]["total"]["value"],
        results=results,
        took_ms=took_ms
    )

def _docs_to_results(docs: list[Dict[str, Any]]) -> list[SearchResult]:
    """Convert docs từ advanced search thành SearchResult."""
    results = []
    for doc in docs:
        results.append(SearchResult(
            score=doc.get("final_score", doc.get("_score", 0)),
            mongo_id=doc.get("mongo_id", ""),
            bid_no=doc.get("bidNo"),
            bid_name=doc.get("bidName", ""),
            procuring_entity=doc.get("procuringEntityName", ""),
            bid_price=doc.get("bidPrice"),
            bid_price_unit=doc.get("bidPriceUnit"),
            bid_open_date=doc.get("bidOpenDate"),
            bid_close_date=doc.get("bidCloseDate"),
            locations=doc.get("locations")
        ))
    return results

@router.post("/bm25", response_model=SearchResponse)
async def bm25_search(request: BM25SearchRequest):
    """BM25 text search endpoint."""
    start = time.time()
    hits = search_service.bm25_search(request.query, request.top_k)
    took_ms = (time.time() - start) * 1000
    return _parse_hits(hits, took_ms, request.query)

@router.post("/vector", response_model=SearchResponse)
async def vector_search(request: VectorSearchRequest):
    """Vector similarity search endpoint."""
    start = time.time()
    hits = search_service.vector_search(request.query, request.top_k, request.min_score)
    took_ms = (time.time() - start) * 1000
    return _parse_hits(hits, took_ms, request.query)

@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(request: HybridSearchRequest):
    """Hybrid search endpoint."""
    start = time.time()
    hits = search_service.hybrid_search(
        request.query, request.top_k, request.min_score, request.text_weight
    )
    took_ms = (time.time() - start) * 1000
    return _parse_hits(hits, took_ms, request.query)

@router.post("/filter", response_model=SearchResponse)
async def filter_search(request: FilterSearchRequest):
    """Filter + vector search endpoint."""
    start = time.time()
    hits = search_service.filter_search(
        request.query, request.filters, request.top_k, request.min_score
    )
    took_ms = (time.time() - start) * 1000
    return _parse_hits(hits, took_ms, request.query)

@router.post("/auto", response_model=SearchResponse)
async def auto_search(request: AutoSearchRequest):
    """
    Auto-routing intelligent search với cache.

    - Phân tích intent (casual vs search)
    - Extract filters tự động
    - Chọn search methods phù hợp
    - RRF merge + multi-criteria ranking
    - Cache results
    """
    start = time.time()

    # Step 1: Intent analysis với v2
    analysis = await IntentAnalyzerV2.analyze(request.query)
    intent = analysis.intent
    filters = analysis.filters
    method = analysis.method
    residual = analysis.residual

    # Step 2: Route theo intent
    if intent == "casual":
        return SearchResponse(
            query=request.query,
            total=0,
            results=[],
            took_ms=(time.time() - start) * 1000,
            intent=intent,
            methods_used=[],
            filters_applied={}
        )

    if intent == "aggregation":
        return SearchResponse(
            query=request.query,
            total=0,
            results=[],
            took_ms=(time.time() - start) * 1000,
            intent=intent,
            methods_used=["aggregation"],
            filters_applied=filters
        )

    # Step 3: Check cache
    cached_results = CacheService.get_query_cache(request.query, [method], filters)
    if cached_results:
        took_ms = (time.time() - start) * 1000
        return SearchResponse(
            query=request.query,
            total=len(cached_results),
            results=_docs_to_results(cached_results),
            took_ms=took_ms,
            intent=intent,
            methods_used=[method],
            filters_applied=filters
        )

    # Step 4: Execute search theo method
    if method == "bm25_code":
        # BM25 cho mã gói thầu
        docs = advanced_search_service.execute_multi_method(
            query=request.query,
            methods=["bm25"],
            filters=filters,
            top_k=request.top_k
        )
    elif method == "metadata_only":
        # Chỉ filter, sort theo mới nhất
        docs = advanced_search_service.metadata_only_search(filters, top_k=request.top_k)
    else:
        # Hybrid search với residual
        docs = advanced_search_service.execute_multi_method(
            query=residual if residual else request.query,
            methods=["hybrid"],
            filters=filters,
            top_k=request.top_k
        )

    # Step 5: Cache results
    CacheService.set_query_cache(request.query, [method], filters, docs)

    # Step 6: Update user context
    if request.session_id:
        keywords = [w for w in request.query.split() if len(w) > 3]
        CacheService.update_user_context(
            request.session_id,
            request.query,
            filters,
            keywords
        )

    took_ms = (time.time() - start) * 1000

    return SearchResponse(
        query=request.query,
        total=len(docs),
        results=_docs_to_results(docs),
        took_ms=took_ms,
        intent=intent,
        methods_used=[method],
        filters_applied=filters
    )

@router.post("/answer")
async def answer_with_rag(request: AutoSearchRequest):
    """
    RAG answer generation với streaming.

    Returns:
        Server-Sent Events stream với answer + citations
    """
    start = time.time()

    # Step 1: Intent analysis với v2
    analysis = await IntentAnalyzerV2.analyze(request.query)
    intent = analysis.intent
    filters = analysis.filters
    method = analysis.method
    residual = analysis.residual

    # Step 2: Nếu casual → stream casual response
    if intent == "casual":
        async def casual_stream():
            async for chunk in RAGService.generate_casual_response(request.query):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(casual_stream(), media_type="text/event-stream")

    # Step 3: Search docs
    cached_results = CacheService.get_query_cache(request.query, [method], filters)
    if cached_results:
        docs = cached_results
    else:
        # Execute search theo method
        if method == "bm25_code":
            docs = advanced_search_service.execute_multi_method(
                query=request.query,
                methods=["bm25"],
                filters=filters,
                top_k=15
            )
        elif method == "metadata_only":
            docs = advanced_search_service.metadata_only_search(filters, top_k=15)
        else:
            docs = advanced_search_service.execute_multi_method(
                query=residual if residual else request.query,
                methods=["hybrid"],
                filters=filters,
                top_k=15
            )

        # Cache
        CacheService.set_query_cache(request.query, [method], filters, docs)

    # Step 4: Update user context
    if request.session_id:
        keywords = [w for w in request.query.split() if len(w) > 3]
        CacheService.update_user_context(request.session_id, request.query, filters, keywords)

    # Step 5: Stream RAG answer
    async def rag_stream():
        # Send metadata first (include docs)
        took_ms = (time.time() - start) * 1000

        # Serialize docs
        docs_serialized = []
        for doc in docs[:15]:
            docs_serialized.append({
                "bid_name": doc.get("bidName", ""),
                "bid_no": doc.get("bidNo"),
                "procuring_entity": doc.get("procuringEntityName", ""),
                "bid_price": doc.get("bidPrice"),
                "locations": doc.get("locations", []),
                "bid_open_date": doc.get("bidOpenDate"),
                "score": doc.get("final_score", doc.get("rrf_score", doc.get("_score", 0)))
            })

        metadata = {
            "type": "metadata",
            "took_ms": took_ms,
            "total_docs": len(docs),
            "intent": intent,
            "methods": [method],
            "filters": filters,
            "docs": docs_serialized
        }
        yield f"data: {json.dumps(metadata)}\n\n"

        # Stream answer chunks
        async for chunk in RAGService.generate_answer(request.query, docs):
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

        # Send citations
        citations = RAGService.format_citations(docs)
        yield f"data: {json.dumps({'type': 'citations', 'content': citations})}\n\n"

        # Done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(rag_stream(), media_type="text/event-stream")

@router.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    return CacheService.get_cache_stats()

@router.post("/v4", response_model=SearchResponse)
async def search_v4(request: AutoSearchRequest):
    """
    V4 intelligent search - full 8-step pipeline.

    - Step 1: Fast path (bid code, greeting)
    - Step 2: Pagination (continue previous results)
    - Step 3: LLM intent analysis (DeepSeek)
    - Step 4: Session merge & method selection
    - Step 5: Hybrid search + advanced reranking
    - Step 6: Auto-relax filters on zero results
    - Step 7: Aggregations (optional)
    - Step 8: Session update + logging
    """
    start = time.time()

    # Load or initialize session
    session = SessionStore.get(request.session_id) if request.session_id else {}

    # Execute V4 pipeline
    result = await search_service_v4.search(
        query=request.query,
        session_id=request.session_id or "anonymous",
        session=session
    )

    # Convert to SearchResponse
    results = []
    for bid in result.bids:
        results.append(SearchResult(
            score=bid.get("_score", bid.get("rrf_score", 0)),
            mongo_id=bid.get("mongo_id", ""),
            bid_no=bid.get("bidNo"),
            bid_name=bid.get("bidName", ""),
            procuring_entity=bid.get("procuringEntityName", ""),
            bid_price=bid.get("bidPrice"),
            bid_price_unit=bid.get("bidPriceUnit"),
            bid_open_date=bid.get("bidOpenDate"),
            bid_close_date=bid.get("bidCloseDate"),
            locations=bid.get("locations")
        ))

    return SearchResponse(
        query=request.query,
        total=result.total,
        results=results,
        took_ms=result.took_ms
    )

@router.post("/v4/answer")
async def search_v4_with_answer(request: AutoSearchRequest):
    """
    V4 search + RAG answer generation với streaming.

    Returns:
        Server-Sent Events stream:
        - metadata: search metadata + docs
        - chunk: answer chunks
        - citations: formatted citations
        - done: completion signal
    """
    start = time.time()

    # Load session
    session = SessionStore.get(request.session_id) if request.session_id else {}

    # Step 1: Execute V4 search
    result = await search_service_v4.search(
        query=request.query,
        session_id=request.session_id or "anonymous",
        session=session
    )

    # Step 2: Stream RAG answer
    async def rag_stream():
        # Send metadata first
        docs_serialized = []
        for bid in result.bids[:15]:
            docs_serialized.append({
                "bid_name": bid.get("bidName", ""),
                "bid_no": bid.get("bidNo"),
                "procuring_entity": bid.get("procuringEntityName", ""),
                "bid_price": bid.get("bidPrice"),
                "locations": bid.get("locations", []),
                "bidOpenDate": bid.get("bidOpenDate"),
                "bidCloseDate": bid.get("bidCloseDate"),
                "score": bid.get("_score", bid.get("rrf_score", 0))
            })

        metadata = {
            "type": "metadata",
            "took_ms": result.took_ms,
            "total_docs": result.total,
            "method": result.method,
            "docs": docs_serialized
        }
        yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"

        # Stream answer chunks
        try:
            async for chunk in RAGService.generate_answer(request.query, result.bids[:15]):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

        # Send citations
        citations = RAGService.format_citations(result.bids[:15])
        yield f"data: {json.dumps({'type': 'citations', 'content': citations}, ensure_ascii=False)}\n\n"

        # Done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(rag_stream(), media_type="text/event-stream")

@router.post("/cache/clear/{session_id}")
async def clear_user_cache(session_id: str):
    """Clear user context cache."""
    CacheService.clear_user_context(session_id)
    SessionStore.clear(session_id)
    return {"status": "ok", "message": f"Cleared context for session {session_id}"}


