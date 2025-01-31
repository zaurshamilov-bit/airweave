"""Google Calendar chunk schemas.

Based on the Google Calendar API reference (readonly scope),
we define chunk schemas for:
 - Calendar objects
 - CalendarList objects
 - Event objects
 - FreeBusy responses

They follow a style similar to that of Asana, HubSpot, and Todoist chunk schemas.

Reference:
    https://developers.google.com/calendar/api/v3/reference
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.platform.chunks._base import BaseChunk


class GoogleCalendarCalendarChunk(BaseChunk):
    """Schema for a Google Calendar object (the underlying calendar resource).

    See: https://developers.google.com/calendar/api/v3/reference/calendars
    """

    calendar_id: str = Field(..., description="Unique identifier for the calendar.")
    summary: Optional[str] = Field(None, description="Title of the calendar.")
    description: Optional[str] = Field(None, description="Description of the calendar.")
    location: Optional[str] = Field(None, description="Geographic location of the calendar.")
    time_zone: Optional[str] = Field(None, description="The time zone of the calendar.")


class GoogleCalendarListChunk(BaseChunk):
    """Schema for a CalendarList entry, i.e., how the user sees a calendar.

    See: https://developers.google.com/calendar/api/v3/reference/calendarList
    """

    calendar_id: str = Field(..., description="Unique identifier for the calendar.")
    summary: Optional[str] = Field(None, description="Title of the calendar.")
    summary_override: Optional[str] = Field(
        None, description="User-defined name for the calendar, if set."
    )
    color_id: Optional[str] = Field(None, description="Color ID reference for the calendar.")
    background_color: Optional[str] = Field(None, description="Background color in HEX.")
    foreground_color: Optional[str] = Field(None, description="Foreground color in HEX.")
    hidden: bool = Field(False, description="Whether the calendar is hidden from the UI.")
    selected: bool = Field(False, description="Indicates if the calendar is selected in the UI.")
    access_role: Optional[str] = Field(
        None,
        description=(
            "The effective access role that the authenticated user has on the calendar."
            " E.g., 'owner', 'reader', 'writer'."
        ),
    )
    primary: bool = Field(False, description="Flag to indicate if this is the primary calendar.")
    deleted: bool = Field(False, description="Flag to indicate if this calendar has been deleted.")


class GoogleCalendarEventChunk(BaseChunk):
    """Schema for a Google Calendar Event.

    See: https://developers.google.com/calendar/api/v3/reference/events
    """

    event_id: str = Field(..., description="Unique identifier for the event.")
    status: Optional[str] = Field(None, description="Status of the event (e.g., 'confirmed').")
    html_link: Optional[str] = Field(
        None, description="An absolute link to the event in the Google Calendar UI."
    )
    created_at: Optional[datetime] = Field(None, description="When the event was created.")
    updated_at: Optional[datetime] = Field(None, description="When the event was last modified.")
    summary: Optional[str] = Field(None, description="Title of the event.")
    description: Optional[str] = Field(None, description="Description of the event.")
    location: Optional[str] = Field(None, description="Geographic location of the event.")
    color_id: Optional[str] = Field(None, description="Color ID for this event.")
    start_datetime: Optional[datetime] = Field(
        None,
        description=(
            "Start datetime if the event has a specific datetime. "
            "(DateTime from 'start' if 'dateTime' is present.)"
        ),
    )
    start_date: Optional[str] = Field(
        None,
        description=(
            "Start date if the event is an all-day event. "
            "(Date from 'start' if 'date' is present.)"
        ),
    )
    end_datetime: Optional[datetime] = Field(
        None,
        description=(
            "End datetime if the event has a specific datetime. "
            "(DateTime from 'end' if 'dateTime' is present.)"
        ),
    )
    end_date: Optional[str] = Field(
        None,
        description=(
            "End date if the event is an all-day event. " "(Date from 'end' if 'date' is present.)"
        ),
    )
    recurrence: Optional[List[str]] = Field(
        None, description="List of RRULE, EXRULE, RDATE, EXDATE lines for recurring events."
    )
    recurring_event_id: Optional[str] = Field(
        None, description="For recurring events, identifies the event ID of the recurring series."
    )
    organizer: Optional[Dict[str, Any]] = Field(
        None, description="The organizer of the event. Usually contains 'email' and 'displayName'."
    )
    creator: Optional[Dict[str, Any]] = Field(
        None, description="The creator of the event. Usually contains 'email' and 'displayName'."
    )
    attendees: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "The attendees of the event (each dict typically has 'email', 'responseStatus', etc.)."
        ),
    )
    transparency: Optional[str] = Field(
        None,
        description=(
            "Specifies whether the event blocks time on the calendar ('opaque') or not "
            "('transparent')."
        ),
    )
    visibility: Optional[str] = Field(
        None, description="Visibility of the event (e.g., 'default', 'public')."
    )
    conference_data: Optional[Dict[str, Any]] = Field(
        None, description="Conference data associated with the event, e.g., hangout or meet link."
    )
    event_type: Optional[str] = Field(None, description="Event type. E.g., 'default' or 'focus'.")


class GoogleCalendarFreeBusyChunk(BaseChunk):
    """Schema for a FreeBusy response chunk for a given calendar.

    See: https://developers.google.com/calendar/api/v3/reference/freebusy
    """

    calendar_id: str = Field(..., description="ID of the calendar for which free/busy is returned.")
    busy: List[Dict[str, str]] = Field(
        default_factory=list,
        description=(
            "List of time ranges during which this calendar is busy. "
            "Each range is typically {'start': <RFC3339 date/time>, 'end': <RFC3339 date/time>}."
        ),
    )
