"""Chunk schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    id: str
    name: str
    type: str


class BaseChunk(BaseModel):
    """Base chunk schema."""

    source_name: str
    content: str
    breadcrumbs: List[Breadcrumb] = Field(default_factory=list)
    url: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True
