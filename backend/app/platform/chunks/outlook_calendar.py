"""
Outlook Calendar chunk schemas.

Based on the Microsoft Graph API reference (read-only scope for the Calendar endpoint),
we define chunk schemas for:
  • Calendar
  • Event

They follow a style similar to the existing chunk schemas, inheriting entity_id from
BaseChunk to store the Microsoft Graph unique identifier for each object.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/calendar?view=graph-rest-1.0
  https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class OutlookCalendarCalendarChunk(BaseChunk):
    """
    Schema for an Outlook Calendar object.

    The inherited entity_id field stores the calendar's Microsoft Graph ID.
    """

    name: Optional[str] = Field(None, description="The display name of the calendar.")
    color: Optional[str] = Field(None, description="Indicates the color theme for the calendar.")
    change_key: Optional[str] = Field(
        None,
        description="Identifies the version of the calendar object. Every time the calendar changes, changeKey changes.",
    )
    can_edit: bool = Field(False, description="Indicates if the user can write to the calendar.")
    can_share: bool = Field(
        False, description="Indicates if the user has the ability to share the calendar."
    )
    can_view_private_items: bool = Field(
        False, description="Indicates if the user can view private events on the calendar."
    )
    owner: Optional[Dict[str, Any]] = Field(
        None,
        description="Details about the calendar's owner. Usually includes name and address fields.",
    )


class OutlookCalendarEventChunk(BaseChunk):
    """
    Schema for an Outlook Calendar Event object.

    The inherited entity_id field stores the event's Microsoft Graph ID.
    """

    subject: Optional[str] = Field(None, description="The subject or title of the event.")
    body_preview: Optional[str] = Field(None, description="A short text preview of the event body.")
    body_content: Optional[str] = Field(None, description="Full body content (HTML or text).")

    start_datetime: Optional[datetime] = Field(
        None,
        description="The date/time when the event starts, in UTC. Derived from 'start.dateTime' if present.",
    )
    start_timezone: Optional[str] = Field(
        None, description="Time zone for the start time, from 'start.timeZone'."
    )
    end_datetime: Optional[datetime] = Field(
        None,
        description="The date/time when the event ends, in UTC. Derived from 'end.dateTime' if present.",
    )
    end_timezone: Optional[str] = Field(
        None, description="Time zone for the end time, from 'end.timeZone'."
    )

    is_all_day: bool = Field(False, description="Indicates if the event lasts all day.")
    is_cancelled: bool = Field(False, description="Indicates if the event has been canceled.")
    show_as: Optional[str] = Field(
        None, description="The status to show. E.g., 'busy', 'tentative', 'free'."
    )
    importance: Optional[str] = Field(None, description="Indicates the importance of the event.")
    sensitivity: Optional[str] = Field(
        None,
        description="Indicates the sensitivity of the event (normal, personal, private, confidential).",
    )

    organizer: Optional[Dict[str, Any]] = Field(
        None,
        description="Information about the organizer of the event, typically includes email address and name.",
    )
    attendees: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of attendees. Each dict usually includes email address info and response status.",
    )
    location: Optional[Dict[str, Any]] = Field(
        None, description="Information about the location where the event is held."
    )

    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the event was created, from 'createdDateTime'."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the event was last modified, from 'lastModifiedDateTime'."
    )

    web_link: Optional[str] = Field(
        None, description="A URL that opens the event in Outlook on the web."
    )

    online_meeting_url: Optional[str] = Field(
        None,
        description="A URL to join the meeting online if the event has online meeting info (e.g., Microsoft Teams).",
    )

    series_master_id: Optional[str] = Field(
        None,
        description="If this is part of a recurring series, specifies the ID of the master recurring event.",
    )
    recurrence: Optional[Dict[str, Any]] = Field(
        None, description="When present, indicates the recurrence pattern of a repeating event."
    )
