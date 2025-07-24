"""Billing event schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BillingEventBase(BaseModel):
    """Billing event base schema."""

    event_type: str = Field(..., description="Type of billing event")
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    stripe_event_id: Optional[str] = Field(None, description="Stripe event ID if applicable")


class BillingEventCreate(BillingEventBase):
    """Billing event creation schema."""

    organization_id: UUID = Field(..., description="Organization ID")


class BillingEvent(BillingEventBase):
    """Billing event schema."""

    model_config = {"from_attributes": True}

    id: UUID
    organization_id: UUID
    created_at: datetime
