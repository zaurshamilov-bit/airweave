from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

KEYWORD_VECTOR_NAME = "bm25"


class DecayConfig(BaseModel):
    """Configuration for time-based decay functions in search queries."""

    decay_type: Literal["linear", "exponential", "gaussian"]
    datetime_field: str = Field(
        default="created_time", description="Field name containing datetime values for decay"
    )
    target_datetime: Optional[datetime] = Field(
        default=None, description="Target datetime for decay calculation"
    )
    scale_unit: Literal["year", "month", "week", "day", "hour", "minute", "second"] = Field(
        ..., description="Units of time for scale"
    )
    scale_value: float = Field(..., gt=0, description="Scale in days for decay calculation")
    midpoint: float = Field(default=0.5, ge=0, le=1, description="Score value at scale distance")

    @model_validator(mode="after")
    def set_default_target_datetime(self):
        """Set default target_datetime to current time if not provided."""
        if self.target_datetime is None:
            self.target_datetime = datetime.now()
        return self

    def get_scale_seconds(self) -> float:
        """Get the scale in seconds based on the scale_unit and scale_value."""
        seconds_mapping = {
            "year": 365 * 24 * 3600,
            "month": 30 * 24 * 3600,
            "week": 7 * 24 * 3600,
            "day": 24 * 3600,
            "hour": 3600,
            "minute": 60,
            "second": 1,
        }
        return self.scale_value * seconds_mapping[self.scale_unit]
