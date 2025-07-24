"""Usage model for tracking organization subscription usage."""

from typing import TYPE_CHECKING

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class Usage(OrganizationBase):
    """Usage model for tracking organization subscription limits."""

    __tablename__ = "usage"

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
