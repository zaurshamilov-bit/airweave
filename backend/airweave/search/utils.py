"""Utilities for search functionality."""

from typing import Any, Dict, Optional

from qdrant_client.http.models import Filter as QdrantFilter


def dict_to_qdrant_filter(filter_dict: Optional[Dict[str, Any]]) -> Optional[QdrantFilter]:
    """Convert a dictionary representation to a Qdrant Filter object.

    Args:
        filter_dict: Dictionary representation of a filter

    Returns:
        QdrantFilter object or None if input is None
    """
    if not filter_dict:
        return None

    try:
        return QdrantFilter.model_validate(filter_dict)
    except Exception as e:
        raise ValueError(f"Invalid filter format: {str(e)}") from e


def validate_filter_keys(filter: QdrantFilter, allowed_keys: set[str]) -> bool:
    """Validate that filter only uses allowed field keys.

    Args:
        filter: QdrantFilter to validate
        allowed_keys: Set of allowed field keys

    Returns:
        True if valid, raises ValueError if invalid
    """
    # TODO: Implement recursive validation of field keys in filter conditions
    # For now, return True to allow all filters
    return True
