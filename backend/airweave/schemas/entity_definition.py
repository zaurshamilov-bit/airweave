"""Schemas for entity definitions."""

from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel

from airweave.models.entity_definition import EntityType


class EntityDefinitionBase(BaseModel):
    """Base schema for entity."""

    name: str
    description: Optional[str] = None
    type: EntityType
    entity_schema: Union[List[str], Dict]  # List of extensions for files, JSON schema for JSON
    parent_id: Optional[UUID] = None
    module_name: str
    class_name: str


class EntityDefinitionCreate(EntityDefinitionBase):
    """Schema for creating an entity definition."""

    pass


class EntityDefinitionUpdate(EntityDefinitionBase):
    """Schema for updating an entity."""

    pass


class EntityDefinition(EntityDefinitionBase):
    """Schema for an entity definition."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True
