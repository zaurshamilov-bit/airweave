"""HubSpot chunk schemas.

Based on the HubSpot CRM API reference, we define chunk schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from datetime import datetime
from typing import Optional

from app.platform.chunks._base import BaseChunk


class HubspotContactChunk(BaseChunk):
    """Schema for HubSpot contact chunks."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class HubspotCompanyChunk(BaseChunk):
    """Schema for HubSpot company chunks."""

    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class HubspotDealChunk(BaseChunk):
    """Schema for HubSpot deal chunks."""

    deal_name: Optional[str] = None
    amount: Optional[float] = None
    pipeline: Optional[str] = None
    deal_stage: Optional[str] = None
    close_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False


class HubspotTicketChunk(BaseChunk):
    """Schema for HubSpot ticket chunks."""

    subject: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    archived: bool = False
