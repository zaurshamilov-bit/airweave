"""Slack chunk schemas.

Based on the Slack Web API reference, we define chunk schemas for common Slack
objects like Channels, Users, and Messages. These follow a style similar to our
Asana and HubSpot chunk schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class SlackChannelChunk(BaseChunk):
    """Schema for Slack channel chunks."""

    channel_id: str
    name: Optional[str] = None
    is_channel: bool = False
    is_group: bool = False
    is_im: bool = False
    is_mpim: bool = False
    is_archived: bool = False
    created: Optional[datetime] = None
    creator: Optional[str] = None
    members: List[str] = Field(default_factory=list)
    topic: Optional[Dict] = None
    purpose: Optional[Dict] = None


class SlackUserChunk(BaseChunk):
    """Schema for Slack user chunks."""

    user_id: str
    team_id: Optional[str] = None
    name: Optional[str] = None  # The 'name' field, often the username
    real_name: Optional[str] = None
    display_name: Optional[str] = None
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False
    is_primary_owner: bool = False
    is_restricted: bool = False
    is_ultra_restricted: bool = False
    updated: Optional[
        datetime
    ] = None  # Slack returns profile updates in epoch time; convert to datetime


class SlackMessageChunk(BaseChunk):
    """Schema for Slack message chunks."""

    channel_id: str
    user_id: Optional[str] = None
    text: Optional[str] = None
    ts: Optional[str] = None  # Slack timestamps are strings, e.g. "1664998373.018700"
    thread_ts: Optional[str] = None
    team: Optional[str] = None
    attachments: List[Dict] = Field(default_factory=list)
    blocks: List[Dict] = Field(default_factory=list)
    files: List[Dict] = Field(default_factory=list)
    reactions: List[Dict] = Field(default_factory=list)
    is_bot: bool = False
    subtype: Optional[str] = None
    edited: Optional[Dict] = None
