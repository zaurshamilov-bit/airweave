"""Source schema."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.platform.auth.schemas import AuthType


class SourceBase(BaseModel):
    """Base schema for Source."""

    name: str
    description: Optional[str] = None
    auth_types: List[AuthType]
    short_name: str
    class_name: str

    class Config:
        """Pydantic config for SourceBase."""

        from_attributes = True


class SourceCreate(SourceBase):
    """Schema for creating a Source object."""

    pass


class SourceUpdate(BaseModel):
    """Schema for updating a Source object."""

    name: Optional[str] = None
    description: Optional[str] = None
    auth_types: Optional[List[AuthType]] = None
    short_name: Optional[str] = None
    class_name: Optional[str] = None


class SourceInDBBase(SourceBase):
    """Base schema for Source stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for SourceInDBBase."""

        from_attributes = True


class Source(SourceInDBBase):
    """Schema for Source."""

    pass
