"""Analytics module for PostHog integration."""

from .decorators.api import track_api_endpoint
from .decorators.search import track_search_operation
from .events.business_events import business_events
from .service import analytics

__all__ = [
    "analytics",
    "business_events",
    "track_api_endpoint",
    "track_search_operation",
]
