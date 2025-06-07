"""User model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import UUID, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase

if TYPE_CHECKING:
    from airweave.models.organization import Organization
    from airweave.models.user_organization import UserOrganization


class User(OrganizationBase):
    """User model."""

    __tablename__ = "user"

    full_name: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    auth0_id: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Multi-organization support - new fields
    primary_organization_id: Mapped[UUID] = mapped_column(
        UUID, ForeignKey("organization.id"), nullable=True
    )
    current_organization_id: Mapped[UUID] = mapped_column(
        UUID, nullable=True
    )  # Runtime org context

    # Define the relationships
    # Keep existing relationship for backward compatibility (maps to organization_id from OrganizationBase)
    organization: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys="User.organization_id",
        back_populates="users",
        lazy="noload",
    )

    # New primary organization relationship
    primary_organization: Mapped["Organization"] = relationship(
        "Organization", foreign_keys=[primary_organization_id], lazy="noload"
    )

    # Many-to-many relationship with organizations
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
