"""EmbeddingModel schema."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.platform.auth.schemas import AuthType


class EmbeddingModelBase(BaseModel):
    """Base schema for EmbeddingModel."""

    name: str
    description: Optional[str] = None
    provider: str
    model_name: str
    model_version: str
    auth_types: List[AuthType]

    class Config:
        """Pydantic config for EmbeddingModelBase."""

        from_attributes = True


class EmbeddingModelCreate(EmbeddingModelBase):
    """Schema for creating an EmbeddingModel object."""

    pass


class EmbeddingModelUpdate(BaseModel):
    """Schema for updating an EmbeddingModel object."""

    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    auth_types: Optional[List[AuthType]] = None


class EmbeddingModelInDBBase(EmbeddingModelBase):
    """Base schema for EmbeddingModel stored in DB."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        """Pydantic config for EmbeddingModelInDBBase."""

        from_attributes = True


class EmbeddingModel(EmbeddingModelInDBBase):
    """Schema for EmbeddingModel."""

    pass
