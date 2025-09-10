"""Decorators for tracking search operations."""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from airweave.analytics.service import analytics

F = TypeVar("F", bound=Callable[..., Any])


def _extract_search_context(args, kwargs):
    """Extract context, query, and collection_slug from function args and kwargs."""
    ctx = None
    query = None
    collection_slug = None

    # Extract context from args and kwargs
    for arg in list(args) + list(kwargs.values()):
        if hasattr(arg, "user") and hasattr(arg, "organization"):
            ctx = arg
            break

    # Extract query and collection info
    query = kwargs.get("query")
    collection_slug = kwargs.get("readable_id")
    search_request = kwargs.get("search_request")

    if search_request and hasattr(search_request, "query"):
        query = search_request.query

    return ctx, query, collection_slug


def _build_success_properties(ctx, query, collection_slug, result, duration_ms):
    """Build properties for successful search analytics."""
    properties = {
        "query_length": len(query),
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "results_count": len(result.results) if hasattr(result, "results") else 0,
        "response_type": result.response_type.value
        if hasattr(result, "response_type") and hasattr(result.response_type, "value")
        else None,
        "status": result.status.value
        if hasattr(result, "status") and hasattr(result.status, "value")
        else "success",
        "organization_name": getattr(ctx.organization, "name", "unknown"),
    }

    # Add search-specific metrics
    if hasattr(result, "results") and result.results:
        scores = [r.get("score", 0) for r in result.results if isinstance(r, dict)]
        if scores:
            properties.update(
                {
                    "avg_score": sum(scores) / len(scores),
                    "max_score": max(scores),
                    "min_score": min(scores),
                }
            )

    return properties


def _build_error_properties(query, collection_slug, duration_ms, error):
    """Build properties for search error analytics."""
    return {
        "query_length": len(query) if query else 0,
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "error": type(error).__name__,
    }


def _track_search_analytics(ctx, properties, event_name):
    """Track search analytics event."""
    analytics.track_event(
        event_name=event_name,
        distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
        properties=properties,
        groups={"organization": str(ctx.organization.id)},
    )


def track_search_operation():
    """Decorator to track search operations with query analysis."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.monotonic()
            ctx, query, collection_slug = _extract_search_context(args, kwargs)

            try:
                result = await func(*args, **kwargs)

                if ctx and query:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    properties = _build_success_properties(
                        ctx, query, collection_slug, result, duration_ms
                    )
                    _track_search_analytics(ctx, properties, "search_query")

                return result

            except Exception as e:
                if ctx and query:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    properties = _build_error_properties(query, collection_slug, duration_ms, e)
                    _track_search_analytics(ctx, properties, "search_query_error")

                raise

        return wrapper

    return decorator
