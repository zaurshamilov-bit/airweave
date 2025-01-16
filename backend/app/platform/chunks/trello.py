"""Trello chunk schemas.

Based on the Trello REST API reference, we define chunk schemas for common
Trello objects like Organizations, Boards, Lists, Cards, and Members.
These follow a style similar to our Asana and HubSpot chunk schemas.
"""

from datetime import datetime
from typing import List, Optional

from app.platform.chunks._base import BaseChunk


class TrelloOrganizationChunk(BaseChunk):
    """Schema for Trello organization (Workspace) chunks."""

    display_name: Optional[str] = None
    name: Optional[str] = None
    desc: Optional[str] = None
    website: Optional[str] = None


class TrelloBoardChunk(BaseChunk):
    """Schema for Trello board chunks."""

    name: Optional[str] = None
    desc: Optional[str] = None
    closed: bool = False  # Trello uses 'closed' to indicate archive status
    pinned: bool = False
    starred: bool = False
    url: Optional[str] = None
    short_url: Optional[str] = None
    date_last_activity: Optional[datetime] = None


class TrelloListChunk(BaseChunk):
    """Schema for Trello list chunks."""

    name: Optional[str] = None
    board_id: Optional[str] = None
    closed: bool = False
    subscribed: bool = False


class TrelloCardChunk(BaseChunk):
    """Schema for Trello card chunks."""

    name: Optional[str] = None
    desc: Optional[str] = None
    closed: bool = False
    list_id: Optional[str] = None
    board_id: Optional[str] = None
    due: Optional[datetime] = None
    due_complete: bool = False
    last_activity_at: Optional[datetime] = None
    url: Optional[str] = None


class TrelloMemberChunk(BaseChunk):
    """Schema for Trello member chunks."""

    avatar_url: Optional[str] = None
    initials: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    confirmed: bool = False
    organizations: List[str] = []
    boards: List[str] = []


class TrelloActionChunk(BaseChunk):
    """Schema for Trello action chunks."""

    action_type: Optional[str] = None
    date: Optional[datetime] = None
    member_creator_id: Optional[str] = None
    data: Optional[dict] = None
