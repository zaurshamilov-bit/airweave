"""Decorators for tracking search operations."""

import time
from functools import wraps
from typing import Any, Callable, TypeVar

from airweave.analytics.service import analytics

F = TypeVar("F", bound=Callable[..., Any])


def track_search_operation():
    """Decorator to track search operations with query analysis."""

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            ctx = None
            query = None
            collection_id = None

            # Extract parameters from function signature
            for arg in kwargs.values():
                if hasattr(arg, "user") and hasattr(arg, "organization"):
                    ctx = arg

            # Extract query and collection info
            query = kwargs.get("query")
            collection_id = kwargs.get("readable_id")
            search_request = kwargs.get("search_request")

            if search_request and hasattr(search_request, "query"):
                query = search_request.query

            try:
                result = await func(*args, **kwargs)

                if ctx and query:
                    duration_ms = (time.time() - start_time) * 1000

                    properties = {
                        "query_length": len(query),
                        "collection_id": collection_id,
                        "duration_ms": duration_ms,
                        "results_count": len(result.results) if hasattr(result, "results") else 0,
                        "response_type": str(result.response_type)
                        if hasattr(result, "response_type")
                        else None,
                        "status": str(result.status) if hasattr(result, "status") else "success",
                        "organization_name": getattr(ctx.organization, "name", "unknown"),
                    }

                    # Add search-specific metrics
                    if hasattr(result, "results") and result.results:
                        # Analyze result quality
                        scores = [r.get("score", 0) for r in result.results if isinstance(r, dict)]
                        if scores:
                            properties.update(
                                {
                                    "avg_score": sum(scores) / len(scores),
                                    "max_score": max(scores),
                                    "min_score": min(scores),
                                }
                            )

                    analytics.track_event(
                        event_name="search_query",
                        distinct_id=str(ctx.user.id)
                        if ctx.user
                        else f"api_key_{ctx.organization.id}",
                        properties=properties,
                        groups={"organization": str(ctx.organization.id)},
                    )

                return result

            except Exception as e:
                if ctx and query:
                    duration_ms = (time.time() - start_time) * 1000

                    properties = {
                        "query_length": len(query) if query else 0,
                        "collection_id": collection_id,
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

                    analytics.track_event(
                        event_name="search_query_error",
                        distinct_id=str(ctx.user.id)
                        if ctx.user
                        else f"api_key_{ctx.organization.id}",
                        properties=properties,
                        groups={"organization": str(ctx.organization.id)},
                    )

                raise

        return wrapper

    return decorator
