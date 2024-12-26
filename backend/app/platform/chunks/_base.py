"""Chunk schemas."""

from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str
    name: str
    type: str


class BaseChunk(BaseModel):
    """Base chunk schema."""

    chunk_id: UUID = Field(default_factory=uuid4)
    source_name: str
    entity_id: str
    sync_id: UUID
    breadcrumbs: List[Breadcrumb] = Field(default_factory=list)
    url: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True
