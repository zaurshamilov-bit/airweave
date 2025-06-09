"""Organization models."""

from typing import TYPE_CHECKING, List

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.user_organization import UserOrganization


class Organization(Base):
    """Organization model."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String, unique=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth0_org_id: Mapped[str] = mapped_column(String, nullable=True)  # Auth0 organization ID

    # Many-to-many relationship with users
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )
