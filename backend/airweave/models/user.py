"""User model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import UUID, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.user_organization import UserOrganization


class User(Base):
    """User model."""

    __tablename__ = "user"

    full_name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Multi-organization support - new fields
    primary_organization_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("organization.id"), nullable=False
    )

    # Many-to-many relationship with organizations
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
