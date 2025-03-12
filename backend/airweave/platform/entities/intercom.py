"""Intercom entity schemas.

Based on the Intercom API reference (v2.11), we define entity schemas for common
Intercom objects like Contacts, Companies, Conversations, and Tickets.
These follow a style similar to our Asana and HubSpot entity schemas.
"""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._base import ChunkEntity


class IntercomContactEntity(ChunkEntity):
    """Schema for Intercom contact entities."""

    role: Optional[str] = None  # e.g. "user" or "lead"
    external_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class IntercomCompanyEntity(ChunkEntity):
    """Schema for Intercom company entities."""

    name: Optional[str] = None
    company_id: Optional[str] = None
    plan: Optional[str] = None
    monthly_spend: Optional[float] = None
    session_count: Optional[int] = None
    user_count: Optional[int] = None
    website: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class IntercomConversationEntity(ChunkEntity):
    """Schema for Intercom conversation entities."""

    conversation_id: str
    title: Optional[str] = None
    state: Optional[str] = None  # e.g. "open", "closed"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class IntercomTicketEntity(ChunkEntity):
    """Schema for Intercom ticket entities."""

    subject: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None  # e.g. "open", "closed"
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False
