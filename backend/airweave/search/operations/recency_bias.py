"""Pre-search dynamic recency bias operator.

Computes a dynamic Qdrant-side decay configuration based on the actual
time range of the (optionally filtered) collection and stores it in
context["decay_config"]. This affects recall and ranking for the whole
collection, not only the returned page, and respects user/LLM filters.

Approach:
- Determine the datetime field to use (prefer system harmonized timestamps)
- Fetch oldest and newest timestamps via two lightweight scrolls with order_by
- Compute scale_seconds as a fraction of the observed time span
- Create DecayConfig with weight = recency_bias and put it in context
- VectorSearch will pick it up and Qdrant will apply formula scoring
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as rest

from airweave.search.operations.base import SearchOperation


class RecencyBias(SearchOperation):
    """Compute dynamic DecayConfig before search and store it in context."""

    def __init__(self, datetime_field: Optional[str] = None, span_fraction: float = 0.2):
        """Initialize.

        Args:
            datetime_field: Preferred datetime field to use if available
            span_fraction: Fraction of observed time span to use as decay scale
        """
        self.datetime_field = datetime_field
        self.span_fraction = max(0.01, min(1.0, span_fraction))

    @property
    def name(self) -> str:
        """Operation name."""
        return "recency"

    @property
    def depends_on(self) -> List[str]:
        """Run after filter extraction and before vector search."""
        return ["qdrant_filter"]

    def _get_filter(self, context: Dict[str, Any]) -> Optional[rest.Filter]:
        """Build Qdrant filter from context if present."""
        if context.get("filter"):
            try:
                return rest.Filter.model_validate(context["filter"])  # type: ignore
            except Exception:
                return None
        return None

    async def _get_min_max(
        self,
        destination,
        collection_id: str,
        field: str,
        qdrant_filter: Optional[rest.Filter],
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Fetch oldest/newest timestamps using ordered scrolls."""
        # Oldest
        oldest_points = await destination.client.scroll(  # type: ignore
            collection_name=str(collection_id),
            limit=1,
            with_payload=[field],
            order_by=rest.OrderBy(key=field, direction="asc"),
            scroll_filter=qdrant_filter,
        )
        # Newest
        newest_points = await destination.client.scroll(  # type: ignore
            collection_name=str(collection_id),
            limit=1,
            with_payload=[field],
            order_by=rest.OrderBy(key=field, direction="desc"),
            scroll_filter=qdrant_filter,
        )

        def extract_dt(point) -> Optional[datetime]:
            if not point or not getattr(point, "payload", None):
                return None
            value: Any = point.payload
            for part in field.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return None
            if isinstance(value, datetime):
                return value
            return None

        oldest = extract_dt(oldest_points[0][0] if oldest_points and oldest_points[0] else None)
        newest = extract_dt(newest_points[0][0] if newest_points and newest_points[0] else None)
        return oldest, newest

    def _build_decay_config(
        self,
        chosen_field: str,
        t_min: datetime,
        t_max: datetime,
        recency_bias: float,
    ) -> Any:
        """Construct DecayConfig from time span and weight."""
        from airweave.search.decay import DecayConfig

        span_seconds = max(1.0, (t_max - t_min).total_seconds())
        scale_seconds = max(43200.0, span_seconds * self.span_fraction)

        decay_config = DecayConfig(
            decay_type="linear",
            datetime_field=chosen_field,
            target_datetime=datetime.now(),
            scale_unit="second",
            scale_value=scale_seconds,
            midpoint=0.5,
            weight=recency_bias,
        )

        # Ensure seconds return path for unit='second'
        def _get_scale_seconds_override(self) -> float:  # type: ignore
            return float(self.scale_value)

        decay_config.get_scale_seconds = _get_scale_seconds_override.__get__(
            decay_config, DecayConfig
        )  # type: ignore
        return decay_config

    async def execute(self, context: Dict[str, Any]) -> None:
        """Compute dynamic decay from collection timestamps and store in context."""
        config = context["config"]
        logger = context["logger"]

        # Determine weight from request via builder
        recency_bias: float = float(getattr(config, "recency_bias", 0.0) or 0.0)
        if recency_bias <= 0.0:
            context["decay_config"] = None
            return

        # Determine datetime field strictly from harmonized system metadata
        # produced via AirweaveField annotations (created/updated_at).
        field = self.datetime_field or "airweave_system_metadata.airweave_updated_at"

        # Prepare Qdrant client
        from uuid import UUID

        from airweave.platform.destinations.qdrant import QdrantDestination

        destination = await QdrantDestination.create(
            collection_id=UUID(config.collection_id), logger=logger
        )

        # Query oldest/newest using the chosen field
        chosen_field: Optional[str] = None
        t_min: Optional[datetime] = None
        t_max: Optional[datetime] = None

        qdrant_filter = self._get_filter(context)

        try:
            oldest, newest = await self._get_min_max(
                destination, config.collection_id, field, qdrant_filter
            )
            if oldest and newest and newest > oldest:
                chosen_field = field
                t_min, t_max = oldest, newest
                logger.info(
                    ("[RecencyBias] Field='%s', filter_applied=%s, oldest=%s, newest=%s"),
                    chosen_field,
                    bool(qdrant_filter),
                    t_min.isoformat(),
                    t_max.isoformat(),
                )
        except Exception:
            chosen_field = None

        if not chosen_field:
            logger.info("[RecencyBias] No usable datetime field found; skipping recency bias")
            context["decay_config"] = None
            return

        # Build DecayConfig and store in context
        decay_config = self._build_decay_config(chosen_field, t_min, t_max, recency_bias)
        context["decay_config"] = decay_config
        logger.info(
            f"[RecencyBias] Using datetime_field='{chosen_field}', span={(t_max - t_min)}, "
            f"scale={decay_config.scale_value:.0f}s, weight={recency_bias}"
        )
