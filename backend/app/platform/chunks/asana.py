"""Asana chunk schemas."""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class AsanaProjectChunk(BaseChunk):
    """Schema for Asana project chunks."""

    color: Optional[str] = None
    due_date: Optional[str] = None
    is_archived: bool = False
    owner: Optional[dict] = None
    team: Optional[dict] = None
    custom_fields: list[dict] = Field(default_factory=list)


class AsanaTaskChunk(BaseChunk):
    """Schema for Asana task chunks."""

    project_gid: str
    section_gid: Optional[str] = None
    assignee: Optional[dict] = None
    due_date: Optional[str] = None
    completed: bool = False
    tags: list[str] = Field(default_factory=list)
    custom_fields: list[dict] = Field(default_factory=list)


class AsanaCommentChunk(BaseChunk):
    """Schema for Asana comment chunks."""

    task_gid: str
    author: dict
    created_at: datetime
    is_pinned: bool = False


class AsanaWorkspaceChunk(BaseChunk):
    """Schema for Asana workspace chunks."""

    name: str
    asana_gid: str
    is_organization: bool = False
    email_domains: list[str] = Field(default_factory=list)
