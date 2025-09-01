"""Qdrant filter operation.

This operation applies user-provided Qdrant filters to the search.
It takes filters from the SearchRequest and ensures they are properly
formatted for the vector search operation.
"""

from typing import Any, Dict, Optional

from airweave.search.operations.base import SearchOperation


class QdrantFilterOperation(SearchOperation):
    """Applies user-provided Qdrant filters to search.

    This operation takes the filter from the SearchRequest (if any)
    and prepares it for use by the vector search operation. It handles
    filter validation and transformation as needed.
    """

    def __init__(self, filter_dict: Optional[Dict[str, Any]] = None):
        """Initialize with optional filter dict.

        Args:
            filter_dict: Qdrant filter dictionary
        """
        self.filter_dict = filter_dict

    @property
    def name(self) -> str:
        """Operation name."""
        return "qdrant_filter"

    async def execute(self, context: Dict[str, Any]) -> None:
        """Apply Qdrant filter from config.

        Reads from context:
            - logger: For logging

        Writes to context:
            - filter: Processed Qdrant filter for vector search
        """
        logger = context["logger"]
        emitter = context.get("emit")

        if self.filter_dict:
            logger.info("[QdrantFilter] Applying user-provided Qdrant filter")

            # Set the filter in context for vector search to use
            context["filter"] = self.filter_dict

            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"[QdrantFilter] Filter: {self.filter_dict}")
            # Emit applied filter minimal snapshot
            if callable(emitter):
                try:
                    await emitter(
                        "filter_applied",
                        {"filter": self.filter_dict, "source": "user"},
                        op_name=self.name,
                    )
                except Exception:
                    pass
        else:
            logger.debug("[QdrantFilter] No user filter provided")
            # Don't set filter in context if none provided
