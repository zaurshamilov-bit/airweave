"""Organization billing model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class OrganizationBilling(Base):
    """Organization billing information for Stripe integration."""

    __tablename__ = "organization_billing"

    # Foreign key to organization (one-to-one relationship)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )

    billing_plan: Mapped[str] = mapped_column(
        String(50),
        default="trial",
        nullable=False,  # trial, developer, startup, enterprise
    )
    billing_status: Mapped[str] = mapped_column(
        String(50),
        default="active",  # active, past_due, canceled, paused, trial_expired
        nullable=False,
    )

    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_method_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    last_payment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship to organization
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="billing", lazy="noload"
    )
