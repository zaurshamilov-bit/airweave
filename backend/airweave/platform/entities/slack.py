"""Slack entity schemas.

Based on the Slack Web API reference, we define entity schemas for common Slack
objects like Channels, Users, and Messages. These follow a style similar to our
Asana and HubSpot entity schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class SlackChannelEntity(ChunkEntity):
    """Schema for Slack channel entities."""

    channel_id: str = Field(description="Unique identifier for the channel")
    name: Optional[str] = Field(None, description="Human-readable name of the channel")
    is_channel: bool = Field(False, description="Whether this is a public channel")
    is_group: bool = Field(False, description="Whether this is a private channel/group")
    is_im: bool = Field(False, description="Whether this is a direct message (IM)")
    is_mpim: bool = Field(False, description="Whether this is a multi-person direct message")
    is_archived: bool = Field(False, description="Whether the channel has been archived")
    created: Optional[datetime] = Field(None, description="Timestamp when the channel was created")
    creator: Optional[str] = Field(None, description="User ID of the channel creator")
    members: List[str] = Field(
        default_factory=list, description="List of user IDs who are members of this channel"
    )
    topic: Optional[Dict] = Field(
        None, description="Information about the channel topic including value and creator"
    )
    purpose: Optional[Dict] = Field(
        None, description="Information about the channel purpose including value and creator"
    )


class SlackUserEntity(ChunkEntity):
    """Schema for Slack user entities."""

    user_id: str = Field(description="Unique identifier for the user")
    team_id: Optional[str] = Field(
        None, description="Identifier for the team/workspace the user belongs to"
    )
    name: Optional[str] = Field(None, description="The username/handle of the user")
    real_name: Optional[str] = Field(None, description="The user's real/full name")
    display_name: Optional[str] = Field(None, description="The display name set by the user")
    is_bot: bool = Field(False, description="Whether the user is a bot")
    is_admin: bool = Field(False, description="Whether the user has admin privileges")
    is_owner: bool = Field(False, description="Whether the user is an owner of the workspace")
    is_primary_owner: bool = Field(
        False, description="Whether the user is the primary owner of the workspace"
    )
    is_restricted: bool = Field(False, description="Whether the user is a restricted user (guest)")
    is_ultra_restricted: bool = Field(
        False, description="Whether the user is an ultra-restricted user (single-channel guest)"
    )
    updated: Optional[datetime] = Field(
        None, description="Timestamp when the user profile was last updated"
    )


class SlackMessageEntity(ChunkEntity):
    """Schema for Slack message entities."""

    channel_id: str = Field(description="ID of the channel the message was posted in")
    user_id: Optional[str] = Field(None, description="ID of the user who sent the message")
    text: Optional[str] = Field(None, description="The message text content")
    ts: Optional[str] = Field(
        None,
        description="Unique timestamp identifier for the message (format: '1664998373.018700')",
    )
    thread_ts: Optional[str] = Field(
        None, description="Timestamp of the parent message in a thread"
    )
    team: Optional[str] = Field(None, description="Team/workspace ID the message belongs to")
    attachments: List[Dict] = Field(default_factory=list, description="Legacy message attachments")
    blocks: List[Dict] = Field(default_factory=list, description="Block Kit blocks in the message")
    files: List[Dict] = Field(default_factory=list, description="Files attached to the message")
    reactions: List[Dict] = Field(
        default_factory=list, description="Emoji reactions added to the message"
    )
    is_bot: bool = Field(False, description="Whether the message was sent by a bot")
    subtype: Optional[str] = Field(
        None, description="Message subtype for special messages (like joins, leaves)"
    )
    edited: Optional[Dict] = Field(
        None, description="Information about message edits including timestamp and user"
    )
