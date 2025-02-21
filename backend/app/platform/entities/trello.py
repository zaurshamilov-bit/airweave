"""Trello entity schemas.

Based on the Trello REST API reference, we define entity schemas for common
Trello objects like Organizations, Boards, Lists, Cards, and Members.
These follow a style similar to our Asana and HubSpot entity schemas.
"""

from datetime import datetime
from typing import List, Optional

from app.platform.entities._base import ChunkEntity
from app.platform.sources._base import Relation


class TrelloOrganizationEntity(ChunkEntity):
    """Schema for Trello organization (Workspace) entities."""

    id: str
    display_name: Optional[str] = None
    name: Optional[str] = None
    desc: Optional[str] = None
    website: Optional[str] = None


class TrelloBoardEntity(ChunkEntity):
    """Schema for Trello board entities."""

    id: str
    name: Optional[str] = None
    desc: Optional[str] = None
    closed: bool = False  # Trello uses 'closed' to indicate archive status
    pinned: bool = False
    starred: bool = False
    url: Optional[str] = None
    short_url: Optional[str] = None
    date_last_activity: Optional[datetime] = None


class TrelloListEntity(ChunkEntity):
    """Schema for Trello list entities."""

    id: str
    name: Optional[str] = None
    board_id: Optional[str] = None
    closed: bool = False
    subscribed: bool = False


class TrelloCardEntity(ChunkEntity):
    """Schema for Trello card entities."""

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


class TrelloMemberEntity(ChunkEntity):
    """Schema for Trello member entities."""

    id: str
    avatar_url: Optional[str] = None
    initials: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    confirmed: bool = False
    organizations: List[str] = []
    boards: List[str] = []


class TrelloActionEntity(ChunkEntity):
    """Schema for Trello action entities."""

    id: str
    action_type: Optional[str] = None
    date: Optional[datetime] = None
    member_creator_id: Optional[str] = None
    data: Optional[dict] = None


RELATIONS = [
    Relation(
        source_entity_type=TrelloCardEntity,
        source_entity_id_attribute="list_id",
        target_entity_type=TrelloListEntity,
        target_entity_id_attribute="id",
        relation_type="is_in_list",
    ),
    Relation(
        source_entity_type=TrelloCardEntity,
        source_entity_id_attribute="board_id",
        target_entity_type=TrelloBoardEntity,
        target_entity_id_attribute="id",
        relation_type="is_in_board",
    ),
    Relation(
        source_entity_type=TrelloCardEntity,
        source_entity_id_attribute="member_creator_id",
        target_entity_type=TrelloMemberEntity,
        target_entity_id_attribute="id",
        relation_type="is_created_by",
    ),
    Relation(
        source_entity_type=TrelloListEntity,
        target_entity_type=TrelloBoardEntity,
        source_entity_id_attribute="board_id",
        target_entity_id_attribute="id",
        relation_type="is_in_board",
    ),
    Relation(
        source_entity_type=TrelloBoardEntity,
        source_entity_id_attribute="organization_id",
        target_entity_type=TrelloOrganizationEntity,
        target_entity_id_attribute="id",
        relation_type="is_in_organization",
    ),
    Relation(
        source_entity_type=TrelloMemberEntity,
        target_entity_type=TrelloOrganizationEntity,
        source_entity_id_attribute="organization_id",
        target_entity_id_attribute="id",
        relation_type="is_in_organization",
    ),
    Relation(
        source_entity_type=TrelloMemberEntity,
        source_entity_id_attribute="boards",
        target_entity_type=TrelloBoardEntity,
        target_entity_id_attribute="id",
        relation_type="is_member_of_board",
    ),
    Relation(
        source_entity_type=TrelloActionEntity,
        source_entity_id_attribute="member_creator_id",
        target_entity_type=TrelloMemberEntity,
        target_entity_id_attribute="id",
        relation_type="is_created_by",
    ),
]
