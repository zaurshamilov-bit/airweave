"""Chunk schemas."""

import hashlib
from typing import Any, List, Optional
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
    metadata: Optional[dict[str, Any]] = None
    white_label_user_identifier: Optional[str] = None
    white_label_id: Optional[str] = None
    white_label_name: Optional[str] = None


    class Config:
        """Pydantic config."""

        from_attributes = True

    def hash(self) -> str:
        """Hash the chunk."""
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()
