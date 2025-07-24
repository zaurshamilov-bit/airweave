"""Usage model for tracking organization subscription usage."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class Usage(OrganizationBase):
    """Usage model for tracking organization subscription limits per billing period."""

    __tablename__ = "usage"

    # Billing period fields
    start_period: Mapped[date] = mapped_column(Date, nullable=False)
    end_period: Mapped[date] = mapped_column(Date, nullable=False)

    # Usage counters with server defaults
    syncs: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    entities: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    queries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    collections: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source_connections: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationship to organization
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="usage",
        lazy="noload",
    )

    __table_args__ = (
        # Index for efficient lookup by organization
        Index("ix_usage_organization_id", "organization_id"),
        # Composite index for efficient querying of most recent period
        Index("ix_usage_organization_id_end_period", "organization_id", "end_period"),
    )
