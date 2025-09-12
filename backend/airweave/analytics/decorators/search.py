"""Decorators for tracking search operations."""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from airweave.analytics.search_analytics import (
    build_search_error_properties,
    build_search_properties,
    track_search_event,
)

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

                    # Extract response type and status from result
                    response_type = None
                    if hasattr(result, "response_type") and hasattr(result.response_type, "value"):
                        response_type = result.response_type.value

                    status = "success"
                    if hasattr(result, "status") and hasattr(result.status, "value"):
                        status = result.status.value

                    # Build properties using shared utility
                    properties = build_search_properties(
                        ctx=ctx,
                        query=query,
                        collection_slug=collection_slug,
                        duration_ms=duration_ms,
                        search_type="regular",
                        results=result.results if hasattr(result, "results") else None,
                        response_type=response_type,
                        status=status,
                    )

                    track_search_event(ctx, properties, "search_query")

                return result

            except Exception as e:
                if ctx and query:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    properties = build_search_error_properties(
                        query, collection_slug, duration_ms, e, search_type="regular"
                    )
                    track_search_event(ctx, properties, "search_query_error")

                raise

        return wrapper

    return decorator


def track_streaming_search_initiation():
    """Decorator to track streaming search initiation.

    This decorator only tracks when a streaming search is initiated.
    The actual search completion is tracked by the SearchExecutor
    when it emits the 'done' event.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx, query, collection_slug = _extract_search_context(args, kwargs)

            # Track stream initiation
            if ctx and query:
                properties = build_search_properties(
                    ctx=ctx,
                    query=query,
                    collection_slug=collection_slug,
                    duration_ms=0,  # No duration for initiation
                    search_type="streaming",
                )
                track_search_event(ctx, properties, "search_stream_start")

            return await func(*args, **kwargs)

        return wrapper

    return decorator
