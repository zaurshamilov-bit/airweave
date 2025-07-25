"""Organization models."""

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.organization_billing import OrganizationBilling
    from airweave.models.user_organization import UserOrganization


class Organization(Base):
    """Organization model."""

    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String, unique=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth0_org_id: Mapped[str] = mapped_column(String, nullable=True)  # Auth0 organization ID

    # Organization metadata for storing onboarding and other flexible data
    org_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default={})

    # Many-to-many relationship with users
    user_organizations: Mapped[List["UserOrganization"]] = relationship(
        "UserOrganization",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # One-to-one relationship with billing (optional for OSS compatibility)
    billing: Mapped[Optional["OrganizationBilling"]] = relationship(
        "OrganizationBilling",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="noload",
        uselist=False,  # One-to-one
    )
