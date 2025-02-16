"""Schemas for entity definitions and relations."""

from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel

from app.models.entity import EntityType


class EntityBase(BaseModel):
    """Base schema for entity."""

    name: str
    description: Optional[str] = None
    type: EntityType
    schema: Union[List[str], Dict]  # List of extensions for files, JSON schema for JSON
    parent_id: Optional[UUID] = None


class EntityCreate(EntityBase):
    """Schema for creating an entity."""

    pass


class EntityUpdate(EntityBase):
    """Schema for updating an entity."""

    pass


class Entity(EntityBase):
    """Schema for an entity definition."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True


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
