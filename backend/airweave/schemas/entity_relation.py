"""Schemas for entity relations."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EntityRelationBase(BaseModel):
    """Base schema for entity relation."""

    name: str
    description: Optional[str] = None
    from_entity_id: UUID
    to_entity_id: UUID


class EntityRelationCreate(EntityRelationBase):
    """Schema for creating an entity relation."""

    pass


class EntityRelationUpdate(EntityRelationBase):
    """Schema for updating an entity relation."""

    pass


class EntityRelation(EntityRelationBase):
    """Schema for an entity relation."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True
