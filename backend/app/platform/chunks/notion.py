"""Notion chunk schemas."""

from datetime import datetime
from typing import Dict, Optional

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class NotionWorkspaceChunk(BaseChunk):
    """Schema for Notion workspace chunks."""

    name: str
    workspace_id: str
    domain: Optional[str] = None
    icon: Optional[str] = None


class NotionDatabaseChunk(BaseChunk):
    """Schema for Notion database chunks."""

    name: str
    database_id: str
    title: Optional[str] = None
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    icon: Optional[str] = None
    cover: Optional[Dict] = None  # In Notion, covers can include image info


class NotionPageChunk(BaseChunk):
    """Schema for Notion page chunks."""

    name: str
    page_id: str
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    archived: bool = False
    icon: Optional[str] = None
    cover: Optional[Dict] = None
    properties: Dict = Field(default_factory=dict)


class NotionBlockChunk(BaseChunk):
    """Schema for Notion block chunks."""

    block_id: str
    block_type: str  # e.g. 'paragraph', 'heading_1', etc.
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    has_children: bool = False
    text_content: Optional[str] = None
    # If you want to store raw block data, you can keep a dict here
    raw_block: Optional[Dict] = None


class NotionCommentChunk(BaseChunk):
    """Schema for Notion comment or discussion chunks."""

    comment_id: str
    author: Optional[Dict] = None
    created_time: datetime
    text: Optional[str] = None
    # Any other fields that might be relevant for comments
