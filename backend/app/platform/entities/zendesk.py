"""Zendesk entity schemas.

Based on the Zendesk Ticketing API (read-only scope), we define entity schemas for the
following core objects:
  • Organization
  • User
  • Ticket
  • Comment

References:
  • https://developer.zendesk.com/api-reference/ticketing/introduction/
  • https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
  • https://developer.zendesk.com/api-reference/ticketing/tickets/ticket_comments/
  • https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
  • https://developer.zendesk.com/api-reference/ticketing/users/users/
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.platform.entities._base import ChunkEntity


class ZendeskOrganizationEntity(ChunkEntity):
    """Schema for a Zendesk organization.

    References:
      https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
    """

    name: Optional[str] = Field(None, description="Name of the organization.")
    details: Optional[str] = Field(None, description="Details about the organization.")
    domain_names: List[str] = Field(
        default_factory=list,
        description="List of domain names associated with this organization.",
    )
    external_id: Optional[str] = Field(None, description="An external ID for this organization.")
    shared_tickets: bool = Field(
        False, description="Whether tickets from this organization are shareable with all members."
    )
    shared_comments: bool = Field(
        False, description="Whether comments are shared between all members of the organization."
    )
    created_at: Optional[datetime] = Field(None, description="When the organization was created.")
    updated_at: Optional[datetime] = Field(
        None, description="When the organization was last updated."
    )
    archived: bool = Field(False, description="Placeholder for archival state if applicable.")


class ZendeskUserEntity(ChunkEntity):
    """Schema for a Zendesk user (agent or end user).

    References:
      https://developer.zendesk.com/api-reference/ticketing/users/users/
    """

    name: Optional[str] = Field(None, description="The user's full name.")
    email: Optional[str] = Field(None, description="The user's email address.")
    role: Optional[str] = Field(
        None, description="Role assigned, e.g., 'admin', 'agent', 'end-user'."
    )
    time_zone: Optional[str] = Field(None, description="The user's time zone.")
    locale: Optional[str] = Field(
        None, description="Locale for the user (language, date/time format)."
    )
    active: bool = Field(False, description="Whether the user is currently active.")
    verified: bool = Field(False, description="Whether the user's identity is verified.")
    shared: bool = Field(
        False,
        description=(
            "Whether the user is shared from a different Zendesk instance or created locally."
        ),
    )
    suspended: bool = Field(False, description="Whether the user is suspended.")
    last_login_at: Optional[datetime] = Field(
        None, description="When the user last signed in (if available)."
    )
    created_at: Optional[datetime] = Field(None, description="When the user was created.")
    updated_at: Optional[datetime] = Field(None, description="When the user was last updated.")
    archived: bool = Field(False, description="Placeholder for archival state if applicable.")


class ZendeskTicketEntity(ChunkEntity):
    """Schema for a Zendesk ticket.

    References:
      https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
    """

    subject: Optional[str] = Field(None, description="Subject or summary of the ticket.")
    description: Optional[str] = Field(None, description="Description text of the ticket.")
    type: Optional[str] = Field(None, description="Type of ticket, e.g., 'question', 'incident'.")
    priority: Optional[str] = Field(
        None, description="Priority of the ticket, e.g., 'low', 'normal'."
    )
    status: Optional[str] = Field(None, description="Current status, e.g., 'open', 'pending'.")
    tags: List[str] = Field(
        default_factory=list, description="List of tags attached to the ticket."
    )
    requester_id: Optional[str] = Field(
        None,
        description="ID of the user that requested the ticket (i.e., the ticket's author).",
    )
    assignee_id: Optional[str] = Field(
        None, description="ID of the user (agent) assigned to handle this ticket."
    )
    organization_id: Optional[str] = Field(
        None, description="ID of the organization associated with this ticket."
    )
    group_id: Optional[str] = Field(None, description="ID of the group this ticket is assigned to.")
    created_at: Optional[datetime] = Field(None, description="When the ticket was created.")
    updated_at: Optional[datetime] = Field(None, description="When the ticket was last updated.")
    due_at: Optional[datetime] = Field(None, description="When this ticket is due.")
    via: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Details about the source through which this ticket was created (e.g., channel)."
        ),
    )
    custom_fields: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of custom field objects with id/value pairs for this ticket.",
    )
    archived: bool = Field(False, description="Placeholder for archival state if applicable.")


class ZendeskCommentEntity(ChunkEntity):
    """Schema for a Zendesk comment, typically tied to a specific ticket.

    References:
      https://developer.zendesk.com/api-reference/ticketing/tickets/ticket_comments/
    """

    ticket_id: str = Field(..., description="ID of the ticket this comment belongs to.")
    author_id: Optional[str] = Field(None, description="ID of the user who wrote this comment.")
    plain_body: Optional[str] = Field(None, description="Plain text version of the comment.")
    public: bool = Field(False, description="Whether the comment is public or private.")
    created_at: Optional[datetime] = Field(None, description="When the comment was created.")
    attachments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Attachments associated with the comment, if any.",
    )
    archived: bool = Field(False, description="Placeholder for archival state if applicable.")
