"""Search response models."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class LocationInfo(BaseModel):
    """Location info with optional fields."""
    provCode: Optional[str] = None
    provName: Optional[str] = None
    districtCode: Optional[str] = None
    districtName: Optional[str] = None
    wardCode: Optional[str] = None
    wardName: Optional[str] = None
    _id: Optional[str] = None

class SearchResult(BaseModel):
    """Single search result."""
    score: float
    mongo_id: str
    bid_no: Optional[str] = None
    bid_name: str
    procuring_entity: str
    bid_price: Optional[float] = None
    bid_price_unit: Optional[str] = None
    bid_open_date: Optional[str] = None
    bid_close_date: Optional[str] = None
    locations: Optional[List[LocationInfo]] = None

class SearchResponse(BaseModel):
    """Search API response."""
    query: str
    total: int
    results: List[SearchResult]
    took_ms: float
    intent: Optional[str] = None
    methods_used: Optional[List[str]] = None
    filters_applied: Optional[Dict[str, Any]] = None

