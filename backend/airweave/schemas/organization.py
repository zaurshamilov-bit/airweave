"""Organization schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    """Organization base schema."""

    name: str = Field(..., min_length=4, max_length=100, description="Organization name")
    description: Optional[str] = Field(None, max_length=500, description="Organization description")


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""

    pass


class OrganizationUpdate(BaseModel):
    """Organization update schema."""

    name: str
    description: Optional[str] = None


class OrganizationInDBBase(OrganizationBase):
    """Organization base schema in the database."""

    model_config = {"from_attributes": True}

    id: UUID
    created_at: datetime
    modified_at: datetime


class Organization(OrganizationInDBBase):
    """Organization schema."""

    name: str
    description: Optional[str] = None


class OrganizationWithRole(BaseModel):
    """Organization schema with user's role information."""

    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    modified_at: datetime
    role: str  # owner, admin, member
    is_primary: bool
    auth0_org_id: Optional[str] = None
