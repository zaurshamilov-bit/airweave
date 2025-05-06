"""Collection schema."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class CollectionStatus(str, Enum):
    """Collection status enum."""

    ACTIVE = "ACTIVE"
    NEEDS_SOURCE = "NEEDS SOURCE"
    SYNCING = "SYNCING"
    ERROR = "ERROR"


class CollectionBase(BaseModel):
    """Base schema for collections."""

    name: str = Field(..., description="Display name for the collection")
    readable_id: Optional[str] = Field(
        None,
        description="Unique lowercase identifier (e.g., respectable-sparrow, collection-123)",
    )

    @field_validator("readable_id")
    def validate_readable_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate that readable_id is a valid lowercase string with hyphens only."""
        if v is None:
            return None
        if not all(c.islower() or c.isdigit() or c == "-" for c in v):
            raise ValueError(
                "readable_id must contain only lowercase letters, numbers, and hyphens"
            )
        # Check that readable_id doesn't start or end with a hyphen
        if v and (v.startswith("-") or v.endswith("-")):
            raise ValueError("readable_id must not start or end with a hyphen")
        return v

    class Config:
        """Pydantic config."""

        from_attributes = True


class CollectionCreate(CollectionBase):
    """Schema for creating a collection."""

    pass


class CollectionUpdate(BaseModel):
    """Schema for updating a collection."""

    name: Optional[str] = None


class CollectionInDBBase(CollectionBase):
    """Base schema for collection in DB."""

    id: UUID
    readable_id: str
    status: CollectionStatus = CollectionStatus.NEEDS_SOURCE
    total_entities: int = 0
    created_at: datetime
    modified_at: datetime
    organization_id: UUID
    created_by_email: EmailStr
    modified_by_email: EmailStr

    class Config:
        """Pydantic config."""

        from_attributes = True


class Collection(CollectionInDBBase):
    """Schema for complete collection representation."""

    pass


class CollectionSearchQuery(BaseModel):
    """Schema for collection search query parameters."""

    query: str
    source_name: Optional[str] = None
    limit: int = 10
    offset: int = 0


class CollectionSearchResult(BaseModel):
    """Schema for search results within a collection."""

    id: UUID
    content: str
    metadata: dict
    source: str
    score: float
