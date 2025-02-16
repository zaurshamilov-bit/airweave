"""Schemas for transformers."""

from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class TransformerBase(BaseModel):
    """Base schema for transformer."""

    name: str
    description: Optional[str] = None
    input_entity_ids: List[UUID]
    output_entity_ids: List[UUID]
    config_schema: Dict


class TransformerCreate(TransformerBase):
    """Schema for creating a transformer."""

    pass


class TransformerUpdate(TransformerBase):
    """Schema for updating a transformer."""

    pass


class Transformer(TransformerBase):
    """Schema for a transformer."""

    id: UUID
    organization_id: UUID
    created_by_email: str
    modified_by_email: str

    class Config:
        """Pydantic config."""

        from_attributes = True
