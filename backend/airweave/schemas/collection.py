"""Collection schema."""

import random
import re
import string
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from airweave.core.shared_models import CollectionStatus


def generate_readable_id(name: str) -> str:
    """Generate a readable ID from a name.

    Converts the name to lowercase, replaces spaces with hyphens,
    removes special characters, and adds a random suffix.
    """
    # Convert to lowercase and replace spaces with hyphens
    readable_id = name.lower().strip()

    # Replace any character that's not a letter, number, or space with nothing
    readable_id = re.sub(r"[^a-z0-9\s]", "", readable_id)
    # Replace spaces with hyphens
    readable_id = re.sub(r"\s+", "-", readable_id)
    # Ensure no consecutive hyphens
    readable_id = re.sub(r"-+", "-", readable_id)
    # Trim hyphens from start and end
    readable_id = readable_id.strip("-")

    # Add random alphanumeric suffix
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    readable_id = f"{readable_id}-{suffix}"

    return readable_id


class CollectionBase(BaseModel):
    """Base schema for collections."""

    name: str = Field(
        ...,
        description="Display name for the collection",
        min_length=4,
        max_length=64,
    )
    readable_id: Optional[str] = Field(
        None,
        description="Unique lowercase identifier (e.g., respectable-sparrow, collection-123)",
    )

    @model_validator(mode="after")
    def generate_readable_id_if_none(self) -> "CollectionBase":
        """Generate a readable_id if none is provided."""
        if self.readable_id is None and self.name:
            self.readable_id = generate_readable_id(self.name)
        return self

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

    name: Optional[str] = Field(
        None,
        description="Display name for the collection",
        min_length=4,
        max_length=64,
    )


class CollectionInDBBase(CollectionBase):
    """Base schema for collection in DB."""

    id: UUID
    readable_id: str
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

    # Ephemeral status derived from source connections
    status: CollectionStatus = CollectionStatus.NEEDS_SOURCE


class CollectionSearchQuery(BaseModel):
    """Schema for collection search query parameters."""

    query: str
    source_name: Optional[str] = None
    limit: int = 10
    offset: int = 0
