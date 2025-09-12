"""Decorators for tracking API endpoint metrics."""

import asyncio
import time
from functools import wraps
from types import SimpleNamespace
from typing import Any, Callable, Optional, TypeVar

from fastapi import HTTPException

from airweave.analytics.service import analytics

F = TypeVar("F", bound=Callable[..., Any])


def _extract_context(args, kwargs):
    """Extract context from function args and kwargs.

    First looks for ApiContext-like objects, then falls back to User-like objects
    for endpoints that don't have organization context yet (like signup).
    """
    # Find ApiContext-like first (has both user and organization)
    for val in list(args) + list(kwargs.values()):
        if hasattr(val, "user") and hasattr(val, "organization"):
            return val

    # Find user-only object (model)
    for val in list(args) + list(kwargs.values()):
        if hasattr(val, "id") and (hasattr(val, "email") or hasattr(val, "username")):
            return SimpleNamespace(
                user=val,
                organization=SimpleNamespace(id=None, name="unknown"),
                auth_method=getattr(val, "auth_method", "unknown"),
            )

    # Check explicit kw names
    user = kwargs.get("user") or kwargs.get("current_user") or kwargs.get("authenticated_user")
    if user:
        return SimpleNamespace(
            user=user,
            organization=SimpleNamespace(id=None, name="unknown"),
            auth_method=getattr(user, "auth_method", "unknown"),
        )

    return None


def _track_analytics(ctx, func, event_name, start_time, error, status_code, include_timing):
    """Track analytics event with shared logic."""
    if not ctx:
        logger = analytics.logger if hasattr(analytics, "logger") else None
        if logger:
            logger.debug(f"No analytics context for {func.__name__}")
        return

    org = getattr(ctx, "organization", None)
    user = getattr(ctx, "user", None)

    properties = {
        "endpoint": event_name or func.__name__,
        "status_code": status_code,
        "auth_method": getattr(ctx, "auth_method", "unknown"),
        "organization_name": getattr(org, "name", "unknown"),
    }

    if include_timing and start_time:
        properties["duration_ms"] = (time.monotonic() - start_time) * 1000

    if error:
        properties["error"] = error

    # Build distinct_id safely
    if user:
        distinct_id = str(user.id)
    elif org and getattr(org, "id", None):
        distinct_id = f"api_key_{org.id}"
    else:
        distinct_id = "unknown"

    # Only include groups if organization has an ID
    groups = {"organization": str(org.id)} if org and getattr(org, "id", None) else None

    event_suffix = "_error" if error else ""
    analytics.track_event(
        event_name=f"api_call{event_suffix}",
        distinct_id=distinct_id,
        properties=properties,
        groups=groups,
    )


def _handle_exception(e):
    """Handle exceptions and extract error details."""
    if isinstance(e, HTTPException):
        return e.detail, e.status_code
    return str(e), 500


def _extract_status_code_from_response(response):
    """Extract status code from FastAPI response object."""
    if hasattr(response, "status_code"):
        return response.status_code
    return 200  # Default for non-response objects


def _create_wrapper(func, event_name, include_timing, is_async):
    """Create a wrapper function for tracking API calls."""

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.monotonic() if include_timing else None
        ctx = _extract_context(args, kwargs)
        error = None
        status_code = 200

        try:
            result = await func(*args, **kwargs)
            # Extract actual status code from successful response
            status_code = _extract_status_code_from_response(result)
            return result
        except Exception as e:
            error, status_code = _handle_exception(e)
            raise
        finally:
            _track_analytics(ctx, func, event_name, start_time, error, status_code, include_timing)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.monotonic() if include_timing else None
        ctx = _extract_context(args, kwargs)
        error = None
        status_code = 200

        try:
            result = func(*args, **kwargs)
            # Extract actual status code from successful response
            status_code = _extract_status_code_from_response(result)
            return result
        except Exception as e:
            error, status_code = _handle_exception(e)
            raise
        finally:
            _track_analytics(ctx, func, event_name, start_time, error, status_code, include_timing)

    return async_wrapper if is_async else sync_wrapper


def track_api_endpoint(event_name: Optional[str] = None, include_timing: bool = True):
    """Decorator to track API endpoint calls with performance metrics.

    Args:
    ----
        event_name: Endpoint name for analytics properties (defaults to function name)
        include_timing: Whether to include timing metrics
    """

    def decorator(func: F) -> F:
        is_async = asyncio.iscoroutinefunction(func)
        return _create_wrapper(func, event_name, include_timing, is_async)

    return decorator
