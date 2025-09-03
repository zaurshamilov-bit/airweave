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

            # Normalize keys so users can provide simple field names (e.g., source_name)
            try:
                normalized_filter = self._normalize_filter_dict(self.filter_dict)
            except Exception:
                # Fallback to original if normalization fails
                normalized_filter = self.filter_dict

            # Merge with existing filter from earlier operations (e.g., interpretation)
            existing_filter = context.get("filter")
            merged_filter = self._merge_filters(existing_filter, normalized_filter)

            # Set the merged filter in context for vector search to use
            context["filter"] = merged_filter

            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"[QdrantFilter] Filter (existing): {existing_filter}")
                logger.debug(f"[QdrantFilter] Filter (normalized user): {normalized_filter}")
                logger.debug(f"[QdrantFilter] Filter (merged): {merged_filter}")
            # Emit merge details and applied filter snapshots
            if callable(emitter):
                try:
                    await emitter(
                        "filter_merge",
                        {
                            "existing": existing_filter,
                            "user": normalized_filter,
                            "merged": merged_filter,
                        },
                        op_name=self.name,
                    )
                    await emitter(
                        "filter_applied",
                        {"filter": merged_filter, "source": "user"},
                        op_name=self.name,
                    )
                except Exception:
                    pass
        else:
            logger.debug("[QdrantFilter] No user filter provided")
            # Don't set filter in context if none provided

    # ----------------- Helpers -----------------
    def _map_to_qdrant_path(self, key: str) -> str:
        """Map field names to their actual Qdrant payload paths.

        Mirrors mapping used in QueryInterpretation to ensure consistency.
        """
        nested_fields = {
            "source_name",
            "entity_type",
            "sync_id",
            "sync_job_id",
            "airweave_created_at",
            "airweave_updated_at",
        }
        if isinstance(key, str) and key.startswith("airweave_system_metadata."):
            return key
        if key in nested_fields:
            return f"airweave_system_metadata.{key}"

        # Support table.column → column mapping (e.g., postgresql tables)
        if isinstance(key, str) and "." in key:
            try:
                _, column = key.split(".", 1)
                if column == "id":
                    return "id_"
                return column
            except Exception:
                return key
        return key

    def _normalize_filter_dict(self, f: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a Qdrant filter dict by mapping condition keys to actual paths.

        Keeps ergonomics (simple keys) while ensuring Qdrant gets fully qualified keys.
        """
        import copy

        def map_condition(cond: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(cond, dict):
                return cond
            new_cond = dict(cond)
            if "key" in new_cond and isinstance(new_cond["key"], str):
                new_cond["key"] = self._map_to_qdrant_path(new_cond["key"])
            # Recurse into nested boolean groups if present
            for group_key in ("must", "must_not", "should"):
                if group_key in new_cond and isinstance(new_cond[group_key], list):
                    new_cond[group_key] = [map_condition(c) for c in new_cond[group_key]]
            return new_cond

        nf = copy.deepcopy(f)
        if not isinstance(nf, dict):
            return f

        for group_key in ("must", "must_not", "should"):
            if group_key in nf and isinstance(nf[group_key], list):
                nf[group_key] = [map_condition(c) for c in nf[group_key]]

        # Top-level single condition case (rare but possible)
        if "key" in nf and isinstance(nf["key"], str):
            nf["key"] = self._map_to_qdrant_path(nf["key"])

        return nf

    def _merge_filters(self, a: Dict[str, Any] | None, b: Dict[str, Any] | None) -> Dict[str, Any]:
        """Merge two Qdrant filter dicts using AND semantics.

        - Concatenates must, should, and must_not arrays
        - Omits empty clauses
        - Handles None inputs gracefully
        """

        def list_or_empty(d: Dict[str, Any] | None, k: str) -> list:
            if isinstance(d, dict):
                v = d.get(k)
                return v if isinstance(v, list) else []
            return []

        if not a and not b:
            return {}
        if not a:
            return b or {}
        if not b:
            return a or {}

        merged = {
            "must": list_or_empty(a, "must") + list_or_empty(b, "must"),
            "should": list_or_empty(a, "should") + list_or_empty(b, "should"),
            "must_not": list_or_empty(a, "must_not") + list_or_empty(b, "must_not"),
        }
        # Remove empty arrays
        return {k: v for k, v in merged.items() if v}
