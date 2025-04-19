"""Trello entity schemas.

Based on the Trello REST API reference, we define entity schemas for common
Trello objects like Organizations, Boards, Lists, Cards, and Members.
These follow a style similar to our Asana and HubSpot entity schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity
from airweave.platform.sources._base import Relation


class TrelloOrganizationEntity(ChunkEntity):
    """Schema for Trello organization (Workspace) entities.

    Organizations (or Workspaces) in Trello are containers for boards that are shared
    among team members.
    """

    id: str = Field(description="The unique identifier for the organization in Trello")
    display_name: Optional[str] = Field(
        None, description="The display name of the organization as shown in the Trello UI"
    )
    name: Optional[str] = Field(None, description="The short name/handle of the organization")
    desc: Optional[str] = Field(None, description="Description text for the organization")
    website: Optional[str] = Field(None, description="URL to the organization's website")


class TrelloBoardEntity(ChunkEntity):
    """Schema for Trello board entities.

    Boards in Trello are the containers for lists and cards, representing projects or workflows.
    """

    id: str = Field(description="The unique identifier for the board in Trello")
    name: Optional[str] = Field(None, description="The name of the board")
    desc: Optional[str] = Field(None, description="Description text for the board")
    closed: bool = Field(False, description="Whether the board is closed (archived)")
    pinned: bool = Field(False, description="Whether the board is pinned for the user")
    starred: bool = Field(False, description="Whether the board is starred for the user")
    url: Optional[str] = Field(None, description="The URL to access the board in Trello")
    short_url: Optional[str] = Field(None, description="A shortened URL to access the board")
    date_last_activity: Optional[datetime] = Field(
        None, description="The date and time of the last activity on the board"
    )


class TrelloListEntity(ChunkEntity):
    """Schema for Trello list entities.

    Lists in Trello are vertical columns on a board that contain cards and represent stages
    in a workflow.
    """

    id: str = Field(description="The unique identifier for the list in Trello")
    name: Optional[str] = Field(None, description="The name of the list")
    board_id: Optional[str] = Field(None, description="The ID of the board this list belongs to")
    closed: bool = Field(False, description="Whether the list is closed (archived)")
    subscribed: bool = Field(False, description="Whether the user is subscribed to this list")


class TrelloCardEntity(ChunkEntity):
    """Schema for Trello card entities.

    Cards in Trello represent tasks or items within a list, containing details and
    supporting attachments.
    """

    id: str = Field(description="The unique identifier for the card in Trello")
    name: Optional[str] = Field(None, description="The name/title of the card")
    desc: Optional[str] = Field(None, description="The description text for the card")
    closed: bool = Field(False, description="Whether the card is closed (archived)")
    list_id: Optional[str] = Field(None, description="The ID of the list this card belongs to")
    board_id: Optional[str] = Field(None, description="The ID of the board this card belongs to")
    due: Optional[datetime] = Field(None, description="The due date for the card")
    due_complete: bool = Field(
        False, description="Whether the due date has been marked as complete"
    )
    last_activity_at: Optional[datetime] = Field(
        None, description="The date and time of the last activity on the card"
    )
    url: Optional[str] = Field(None, description="The URL to access the card in Trello")


class TrelloMemberEntity(ChunkEntity):
    """Schema for Trello member entities.

    Members in Trello are users who can interact with boards, lists, and cards based on
    their permissions.
    """

    id: str = Field(description="The unique identifier for the member in Trello")
    avatar_url: Optional[str] = Field(None, description="URL to the member's avatar image")
    initials: Optional[str] = Field(
        None, description="The member's initials as displayed in Trello"
    )
    full_name: Optional[str] = Field(None, description="The member's full name")
    username: Optional[str] = Field(None, description="The member's username in Trello")
    confirmed: bool = Field(False, description="Whether the member's account is confirmed")
    organizations: List[str] = Field(
        default_factory=list, description="List of organization IDs the member belongs to"
    )
    boards: List[str] = Field(
        default_factory=list, description="List of board IDs the member has access to"
    )


class TrelloActionEntity(ChunkEntity):
    """Schema for Trello action entities.

    Actions in Trello represent activities or changes made to boards, lists, or cards.
    """

    id: str = Field(description="The unique identifier for the action in Trello")
    action_type: Optional[str] = Field(
        None, description="The type of action performed (e.g., 'createCard', 'updateList')"
    )
    date: Optional[datetime] = Field(None, description="The date and time when the action occurred")
    member_creator_id: Optional[str] = Field(
        None, description="The ID of the member who created/performed the action"
    )
    data: Optional[dict] = Field(None, description="Additional data associated with the action")


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
