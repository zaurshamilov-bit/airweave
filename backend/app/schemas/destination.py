"""Destination schema."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.platform.auth.schemas import AuthType


class DestinationBase(BaseModel):
    """Base schema for Destination."""

    name: str
    description: Optional[str] = None
    short_name: str
    class_name: str
    auth_types: List[AuthType]

    class Config:
        """Pydantic config for DestinationBase."""

        from_attributes = True


class DestinationCreate(DestinationBase):
    """Schema for creating a Destination object."""

    pass


class DestinationUpdate(BaseModel):
    """Schema for updating a Destination object."""

    name: Optional[str] = None
    description: Optional[str] = None
    short_name: Optional[str] = None
    class_name: Optional[str] = None
    auth_types: Optional[List[AuthType]] = None


class DestinationInDBBase(DestinationBase):
    """Base schema for Destination stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for DestinationInDBBase."""

        from_attributes = True


class Destination(DestinationInDBBase):
    """Schema for Destination."""

    pass
