"""Billing event model for audit trail."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class BillingEvent(Base):
    """Audit log for billing-related events."""

    __tablename__ = "billing_event"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # subscription_created, payment_succeeded, etc.

    stripe_event_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    event_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", lazy="noload")

    __table_args__ = (
        Index("idx_billing_events_org", "organization_id"),
        Index("idx_billing_events_type", "event_type"),
    )
