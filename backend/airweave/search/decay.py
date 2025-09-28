"""Search-internal decay configuration.

This module defines DecayConfig, used internally by the search pipeline to
configure Qdrant formula queries for recency bias. It is not exposed
through the public API; users control recency via `recency_bias` only.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class DecayConfig(BaseModel):
    """Configuration for time-based decay used by Qdrant queries.

    This is an internal search concern and is consumed by the Qdrant destination
    when constructing formula queries. It is derived by the RecencyBias operator
    from the public `recency_bias` knob and dataset timestamps.
    """

    decay_type: Literal["linear", "exponential", "gaussian"]
    datetime_field: str = Field(..., description="Payload field with datetime values")
    target_datetime: Optional[datetime] = Field(
        default=None, description="Reference datetime for decay calculation"
    )
    # Scale can be expressed via unit+value; the RecencyBias operator may also
    # set unit to "second" and provide a raw seconds value.
    scale_unit: Literal["year", "month", "week", "day", "hour", "minute", "second"]
    scale_value: float = Field(..., gt=0, description="Scale value in the given unit")
    midpoint: float = Field(default=0.5, ge=0, le=1, description="Score at scale distance")
    # Weight for blending: final = (1-weight)*similarity + weight*decay
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relative weight of recency in final score (0..1)",
    )

    @model_validator(mode="after")
    def _default_target_datetime(self):
        """Populate target_datetime if not provided."""
        if self.target_datetime is None:
            self.target_datetime = datetime.now()
        return self

    def get_scale_seconds(self) -> float:
        """Convert the configured scale to seconds."""
        mapping = {
            "year": 365 * 24 * 3600,
            "month": 30 * 24 * 3600,
            "week": 7 * 24 * 3600,
            "day": 24 * 3600,
            "hour": 3600,
            "minute": 60,
            "second": 1,
        }
        return self.scale_value * mapping[self.scale_unit]
