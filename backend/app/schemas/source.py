"""Source schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.platform.auth.schemas import AuthType
from app.platform.configs.auth import AuthConfig


class SourceBase(BaseModel):
    """Base schema for Source."""

    name: str
    description: Optional[str] = None
    auth_type: Optional[AuthType] = None
    auth_config_class: Optional[str] = None
    short_name: str
    class_name: str

    class Config:
        """Pydantic config for SourceBase."""

        from_attributes = True


class SourceCreate(SourceBase):
    """Schema for creating a Source object."""

    pass


class SourceUpdate(SourceBase):
    """Schema for updating a Source object."""

    pass


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

class SourceWithAuthConfig(Source):
    """Schema for Source with auth config."""

    auth_config: AuthConfig
