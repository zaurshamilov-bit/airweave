"""Notion entity schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.platform.entities._base import BaseEntity


class NotionDatabaseEntity(BaseEntity):
    """Schema for Notion database entities."""

    name: str = Field(description="The name of the database")
    database_id: str = Field(description="The ID of the database")
    description: Optional[str] = Field(default=None, description="The description of the database")
    created_time: Optional[datetime] = Field(
        default=None, description="The creation time of the database"
    )
    last_edited_time: Optional[datetime] = Field(
        default=None, description="The last edited time of the database"
    )


class NotionPageEntity(BaseEntity):
    """Schema for Notion page entities."""

    page_id: str = Field(description="The ID of the page")
    parent_id: str = Field(description="The ID of the parent page")
    parent_type: str = Field(description="The type of the parent page")
    title: str = Field(description="The title of the page")
    created_time: Optional[datetime] = Field(
        default=None, description="The creation time of the page"
    )
    last_edited_time: Optional[datetime] = Field(
        default=None, description="The last edited time of the page"
    )
    archived: bool = Field(default=False, description="Whether the page is archived")
    content: Optional[str] = Field(default=None, description="The content of the page")


class NotionBlockEntity(BaseEntity):
    """Schema for Notion block entities."""

    block_id: str = Field(description="The ID of the block")
    parent_id: str = Field(description="The ID of the parent block")
    block_type: str = Field(description="The type of the block")
    text_content: Optional[str] = Field(default=None, description="The text content of the block")
    has_children: bool = Field(default=False, description="Whether the block has children")
    children_ids: List[str] = Field(
        default_factory=list, description="The IDs of the children blocks"
    )
    created_time: Optional[datetime] = Field(
        default=None, description="The creation time of the block"
    )
    last_edited_time: Optional[datetime] = Field(
        default=None, description="The last edited time of the block"
    )
