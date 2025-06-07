"""User schema module."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, validator

from .organization import Organization


class UserOrganizationBase(BaseModel):
    """Base schema for UserOrganization relationship."""

    role: str = "member"  # owner, admin, member
    is_primary: bool = False
    auth0_org_id: Optional[str] = None

    class Config:
        """Pydantic config for UserOrganizationBase."""

        from_attributes = True


class UserOrganization(UserOrganizationBase):
    """Schema for UserOrganization relationship with full organization details."""

    organization_id: UUID
    organization: Organization

    class Config:
        """Pydantic config for UserOrganization."""

        from_attributes = True


class UserBase(BaseModel):
    """Base schema for User."""

    email: EmailStr
    full_name: Optional[str] = "Superuser"
    organization_id: Optional[UUID] = None  # Keep for backward compatibility

    @validator("organization_id", pre=True, always=True)
    def organization_must_exist_for_operations(cls, v, values):
        """Validate that the organization_id field is present for operations."""
        return v

    class Config:
        """Pydantic config for UserBase."""

        from_orm = True
        from_attributes = True


class UserCreate(UserBase):
    """Schema for creating a User object."""

    pass


class UserUpdate(UserBase):
    """Schema for updating a User object."""

    permissions: Optional[list[str]] = None

    @validator("organization_id")
    def organization_required_for_update(cls, v):
        """Validate that the organization_id is not None for updates."""
        if v is None:
            raise ValueError("organization_id cannot be None when updating a user")
        return v


class UserInDBBase(UserBase):
    """Base schema for User stored in DB."""

    id: UUID
    permissions: Optional[list[str]] = None
    primary_organization_id: Optional[UUID] = None
    current_organization_id: Optional[UUID] = None
    organizations: list[UserOrganization] = []

    @validator("organizations", pre=True, always=True)
    def load_organizations(cls, v):
        """Ensure organizations are always loaded."""
        return v or []

    @property
    def primary_organization(self) -> Optional[UserOrganization]:
        """Get the primary organization for this user."""
        for org in self.organizations:
            if org.is_primary:
                return org
        return None

    @property
    def organization_roles(self) -> dict[UUID, str]:
        """Get a mapping of organization IDs to roles."""
        return {org.organization_id: org.role for org in self.organizations}

    class Config:
        """Pydantic config for UserInDBBase."""

        from_attributes = True


class User(UserInDBBase):
    """Schema for User."""

    class Config:
        """Pydantic config for User."""

        from_attributes = True
        populate_by_name = True


class UserInDB(UserInDBBase):
    """Schema for User stored in DB."""

    hashed_password: Optional[str] = None


class UserWithOrganizations(UserInDBBase):
    """Schema for User with Organizations - now redundant as all users include orgs."""

    pass
