"""Trello chunk schemas.

Based on the Trello REST API reference, we define chunk schemas for common
Trello objects like Organizations, Boards, Lists, Cards, and Members.
These follow a style similar to our Asana and HubSpot chunk schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.platform.chunks._base import BaseChunk


class TrelloOrganizationChunk(BaseChunk):
    """Schema for Trello organization (Workspace) chunks."""

    id: str
    display_name: Optional[str] = None
    name: Optional[str] = None
    desc: Optional[str] = None
    website: Optional[str] = None


class TrelloBoardChunk(BaseChunk):
    """Schema for Trello board chunks."""

    id: str
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

    id: str
    name: Optional[str] = None
    board_id: Optional[str] = None
    closed: bool = False
    subscribed: bool = False


class TrelloCardChunk(BaseChunk):
    """Schema for Trello card chunks."""

    id: str
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

    id: str
    avatar_url: Optional[str] = None
    initials: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    confirmed: bool = False
    organizations: List[str] = []
    boards: List[str] = []


class TrelloActionChunk(BaseChunk):
    """Schema for Trello action chunks."""

    id: str
    action_type: Optional[str] = None
    date: Optional[datetime] = None
    member_creator_id: Optional[str] = None
    data: Optional[dict] = None


class Relation(BaseModel):
    """A relation between two entities."""

    id: str
    source_chunk_type: type[BaseChunk]
    source_entity_id_attribute: str
    target_chunk_type: type[BaseChunk]
    target_entity_id_attribute: str
    relation_type: str


RELATIONS = [
    Relation(
        source_chunk_type=TrelloCardChunk,
        source_entity_id_attribute="list_id",
        target_chunk_type=TrelloListChunk,
        target_entity_id_attribute="id",
        relation_type="is_in_list",
    ),
    Relation(
        source_chunk_type=TrelloCardChunk,
        source_entity_id_attribute="board_id",
        target_chunk_type=TrelloBoardChunk,
        target_entity_id_attribute="id",
        relation_type="is_in_board",
    ),
    Relation(
        source_chunk_type=TrelloCardChunk,
        source_entity_id_attribute="member_creator_id",
        target_chunk_type=TrelloMemberChunk,
        target_entity_id_attribute="id",
        relation_type="is_created_by",
    ),
    Relation(
        source_chunk_type=TrelloListChunk,
        target_chunk_type=TrelloBoardChunk,
        source_entity_id_attribute="board_id",
        target_entity_id_attribute="id",
        relation_type="is_in_board",
    ),
    Relation(
        source_chunk_type=TrelloBoardChunk,
        source_entity_id_attribute="organization_id",
        target_chunk_type=TrelloOrganizationChunk,
        target_entity_id_attribute="id",
        relation_type="is_in_organization",
    ),
    Relation(
        source_chunk_type=TrelloMemberChunk,
        target_chunk_type=TrelloOrganizationChunk,
        source_entity_id_attribute="organization_id",
        target_entity_id_attribute="id",
        relation_type="is_in_organization",
    ),
    Relation(
        source_chunk_type=TrelloMemberChunk,
        source_entity_id_attribute="boards",
        target_chunk_type=TrelloBoardChunk,
        target_entity_id_attribute="id",
        relation_type="is_member_of_board",
    ),
    Relation(
        source_chunk_type=TrelloActionChunk,
        source_entity_id_attribute="member_creator_id",
        target_chunk_type=TrelloMemberChunk,
        target_entity_id_attribute="id",
        relation_type="is_created_by",
    ),
]
