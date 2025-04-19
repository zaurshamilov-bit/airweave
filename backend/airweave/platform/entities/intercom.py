"""Intercom entity schemas.

Based on the Intercom API reference (v2.11), we define entity schemas for common
Intercom objects like Contacts, Companies, Conversations, and Tickets.
These follow a style similar to our Asana and HubSpot entity schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class IntercomContactEntity(ChunkEntity):
    """Schema for Intercom contact entities.

    Contacts in Intercom can be either users or leads with associated profile data.
    """

    role: Optional[str] = Field(None, description="The type of contact - either 'user' or 'lead'")
    external_id: Optional[str] = Field(
        None, description="A unique identifier for the contact provided by your application"
    )
    email: Optional[str] = Field(None, description="The contact's email address")
    phone: Optional[str] = Field(None, description="The contact's phone number")
    name: Optional[str] = Field(None, description="The contact's full name")
    avatar: Optional[str] = Field(None, description="URL to the contact's avatar or profile image")
    created_at: Optional[datetime] = Field(
        None,
        description="Creation time of the contact, represented as UTC Unix timestamp",
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last updated time of the contact, represented as UTC Unix timestamp",
    )
    archived: bool = Field(False, description="Indicates whether the contact has been archived")


class IntercomCompanyEntity(ChunkEntity):
    """Schema for Intercom company entities.

    Companies in Intercom represent organizations that your contacts belong to.
    """

    name: Optional[str] = Field(None, description="The company's name")
    company_id: Optional[str] = Field(None, description="A unique identifier for the company")
    plan: Optional[str] = Field(None, description="The plan or subscription level of the company")
    monthly_spend: Optional[float] = Field(
        None, description="The monthly spend or revenue associated with this company"
    )
    session_count: Optional[int] = Field(
        None, description="The number of sessions associated with the company"
    )
    user_count: Optional[int] = Field(
        None, description="The number of users associated with the company"
    )
    website: Optional[str] = Field(None, description="The company's website URL")
    created_at: Optional[datetime] = Field(
        None,
        description="Creation time of the company, represented as UTC Unix timestamp",
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last updated time of the company, represented as UTC Unix timestamp",
    )
    archived: bool = Field(False, description="Indicates whether the company has been archived")


class IntercomConversationEntity(ChunkEntity):
    """Schema for Intercom conversation entities.

    Conversations in Intercom represent message threads between contacts and your team.
    """

    conversation_id: str = Field(
        description="The unique identifier for the conversation in Intercom"
    )
    title: Optional[str] = Field(None, description="The title or subject of the conversation")
    state: Optional[str] = Field(
        None, description="The current state of the conversation (e.g., 'open', 'closed')"
    )
    created_at: Optional[datetime] = Field(
        None, description="The time the conversation was created, represented as UTC Unix timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="The time the conversation was last updated, represented as UTC Unix timestamp",
    )
    archived: bool = Field(
        False, description="Indicates whether the conversation has been archived"
    )


class IntercomTicketEntity(ChunkEntity):
    """Schema for Intercom ticket entities.

    Tickets in Intercom represent structured support requests that can be tracked and managed.
    """

    subject: Optional[str] = Field(None, description="The subject or title of the ticket")
    description: Optional[str] = Field(None, description="The detailed description of the ticket")
    state: Optional[str] = Field(
        None, description="The current state of the ticket (e.g., 'open', 'closed')"
    )
    contact_id: Optional[str] = Field(
        None, description="The ID of the contact associated with this ticket"
    )
    company_id: Optional[str] = Field(
        None, description="The ID of the company associated with this ticket"
    )
    created_at: Optional[datetime] = Field(
        None, description="The time the ticket was created, represented as UTC Unix timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None, description="The time the ticket was last updated, represented as UTC Unix timestamp"
    )
    archived: bool = Field(False, description="Indicates whether the ticket has been archived")
