"""Schemas for search."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ResponseType(str, Enum):
    """Response type for search results."""

    RAW = "raw"
    COMPLETION = "completion"


class SearchStatus(str, Enum):
    """Status for search results."""

    SUCCESS = "success"
    NO_RELEVANT_RESULTS = "no_relevant_results"
    NO_RESULTS = "no_results"


class SearchResponse(BaseModel):
    """Schema for search response."""

    results: list[dict]
    response_type: ResponseType
    completion: Optional[str] = None
    status: SearchStatus
