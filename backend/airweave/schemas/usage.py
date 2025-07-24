"""Usage schemas for tracking organization subscription limits."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UsageBase(BaseModel):
    """Base schema for usage tracking."""

    syncs: int = Field(
        0,
        ge=0,
        description="Number of syncs created by the organization.",
    )
    entities: int = Field(
        0,
        ge=0,
        description="Total number of entities processed across all syncs.",
    )
    queries: int = Field(
        0,
        ge=0,
        description="Number of search queries executed.",
    )
    collections: int = Field(
        0,
        ge=0,
        description="Number of collections created.",
    )
    source_connections: int = Field(
        0,
        ge=0,
        description="Number of source connections configured.",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class UsageCreate(UsageBase):
    """Schema for creating usage records.

    Typically, usage records are created automatically when an organization
    is created, with all counters initialized to 0.
    """

    # All fields inherit from UsageBase with default values of 0


class UsageUpdate(BaseModel):
    """Schema for updating usage counters.

    All fields are optional, allowing partial updates of specific counters.
    """

    syncs: Optional[int] = Field(
        None,
        ge=0,
        description="Updated sync count.",
    )
    entities: Optional[int] = Field(
        None,
        ge=0,
        description="Updated entity count.",
    )
    queries: Optional[int] = Field(
        None,
        ge=0,
        description="Updated query count.",
    )
    collections: Optional[int] = Field(
        None,
        ge=0,
        description="Updated collection count.",
    )
    source_connections: Optional[int] = Field(
        None,
        ge=0,
        description="Updated source connection count.",
    )


class UsageInDBBase(UsageBase):
    """Base schema for usage records stored in the database."""

    id: UUID = Field(
        ...,
        description="Unique identifier for the usage record.",
    )
    organization_id: UUID = Field(
        ...,
        description="Organization this usage record belongs to.",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the usage record was created.",
    )
    modified_at: datetime = Field(
        ...,
        description="Timestamp when the usage record was last updated.",
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Usage(UsageInDBBase):
    """Complete usage representation with computed fields."""

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "organization_id": "org12345-6789-abcd-ef01-234567890abc",
                    "syncs": 5,
                    "entities": 10000,
                    "queries": 250,
                    "collections": 3,
                    "source_connections": 8,
                    "created_at": "2024-01-01T00:00:00Z",
                    "modified_at": "2024-01-15T14:22:15Z",
                }
            ]
        },
    }
