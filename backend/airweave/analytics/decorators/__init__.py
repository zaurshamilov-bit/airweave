"""Decorators for analytics tracking."""

from .api import track_api_endpoint
from .search import track_search_operation

__all__ = [
    "track_api_endpoint",
    "track_search_operation",
]
