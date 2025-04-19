"""HubSpot entity schemas.

Based on the HubSpot CRM API reference, we define entity schemas for common
HubSpot objects like Contacts, Companies, Deals, and Tickets.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity


class HubspotContactEntity(ChunkEntity):
    """Schema for HubSpot contact entities."""

    first_name: Optional[str] = Field(default=None, description="The contact's first name")
    last_name: Optional[str] = Field(default=None, description="The contact's last name")
    email: Optional[str] = Field(default=None, description="The contact's email address")
    phone: Optional[str] = Field(default=None, description="The contact's phone number")
    lifecycle_stage: Optional[str] = Field(
        default=None, description="The contact's lifecycle stage in the marketing/sales process"
    )
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the contact was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the contact was last updated"
    )
    archived: bool = Field(default=False, description="Whether the contact is archived")


class HubspotCompanyEntity(ChunkEntity):
    """Schema for HubSpot company entities."""

    name: Optional[str] = Field(default=None, description="The company's name")
    domain: Optional[str] = Field(default=None, description="The company's domain name")
    industry: Optional[str] = Field(default=None, description="The company's industry category")
    phone: Optional[str] = Field(default=None, description="The company's phone number")
    website: Optional[str] = Field(default=None, description="The company's website URL")
    city: Optional[str] = Field(default=None, description="The city where the company is located")
    state: Optional[str] = Field(
        default=None, description="The state or region where the company is located"
    )
    zip: Optional[str] = Field(
        default=None, description="The postal code where the company is located"
    )
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the company was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the company was last updated"
    )
    archived: bool = Field(default=False, description="Whether the company is archived")


class HubspotDealEntity(ChunkEntity):
    """Schema for HubSpot deal entities."""

    deal_name: Optional[str] = Field(default=None, description="The name of the deal")
    amount: Optional[float] = Field(default=None, description="The monetary value of the deal")
    pipeline: Optional[str] = Field(default=None, description="The pipeline the deal belongs to")
    deal_stage: Optional[str] = Field(
        default=None, description="The stage of the deal in the sales process"
    )
    close_date: Optional[datetime] = Field(
        default=None, description="The date when the deal is expected to close or closed"
    )
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the deal was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the deal was last updated"
    )
    archived: bool = Field(default=False, description="Whether the deal is archived")


class HubspotTicketEntity(ChunkEntity):
    """Schema for HubSpot ticket entities."""

    subject: Optional[str] = Field(default=None, description="The subject of the support ticket")
    content: Optional[str] = Field(
        default=None, description="The content or description of the ticket"
    )
    status: Optional[str] = Field(default=None, description="The current status of the ticket")
    created_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the ticket was created"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the ticket was last updated"
    )
    archived: bool = Field(default=False, description="Whether the ticket is archived")
