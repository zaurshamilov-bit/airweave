"""Organization schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OrganizationBase(BaseModel):
    """Organization base schema."""

    name: str
    description: str


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""

    pass


class OrganizationUpdate(BaseModel):
    """Organization update schema."""

    name: str
    description: str


class OrganizationInDBBase(OrganizationBase):
    """Organization base schema in the database."""

    id: UUID
    created_at: datetime
    modified_at: datetime


class Organization(OrganizationInDBBase):
    """Organization schema."""

    name: str
    description: str
