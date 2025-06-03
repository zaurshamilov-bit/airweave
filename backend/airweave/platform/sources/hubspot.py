"""HubSpot source implementation."""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import ChunkEntity
from airweave.platform.entities.hubspot import (
    HubspotCompanyEntity,
    HubspotContactEntity,
    HubspotDealEntity,
    HubspotTicketEntity,
    parse_hubspot_datetime,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="HubSpot",
    short_name="hubspot",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="HubspotAuthConfig",
    config_class="HubspotConfig",
    labels=["CRM", "Marketing"],
)
class HubspotSource(BaseSource):
    """HubSpot source implementation.

    This connector retrieves data from HubSpot CRM objects such as Contacts,
    Companies, Deals, and Tickets, then yields them as entities using
    their respective entity schemas.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "HubspotSource":
        """Create a new HubSpot source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to HubSpot API.

        For example, to retrieve contacts:
          GET https://api.hubapi.com/crm/v3/objects/contacts
        """
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return response.json()

    def _safe_float_conversion(self, value: Any) -> Optional[float]:
        """Safely convert a value to float, handling empty strings and None."""
        if not value or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def _generate_contact_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Contact entities from HubSpot.

        This uses the REST CRM API endpoint for contacts:
          GET /crm/v3/objects/contacts
        """
        url = "https://api.hubapi.com/crm/v3/objects/contacts"
        while url:
            data = await self._get_with_auth(client, url)
            for contact in data.get("results", []):
                properties = contact.get("properties", {})

                yield HubspotContactEntity(
                    entity_id=contact["id"],
                    # Core fields for easy access
                    first_name=properties.get("firstname"),
                    last_name=properties.get("lastname"),
                    email=properties.get("email"),
                    # All properties from HubSpot
                    properties=properties,
                    created_at=parse_hubspot_datetime(contact.get("createdAt")),
                    updated_at=parse_hubspot_datetime(contact.get("updatedAt")),
                    archived=contact.get("archived", False),
                )

            # Handle pagination
            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_company_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Company entities from HubSpot.

        This uses the REST CRM API endpoint for companies:
          GET /crm/v3/objects/companies
        """
        url = "https://api.hubapi.com/crm/v3/objects/companies"
        while url:
            data = await self._get_with_auth(client, url)
            for company in data.get("results", []):
                properties = company.get("properties", {})

                yield HubspotCompanyEntity(
                    entity_id=company["id"],
                    # Core fields for easy access
                    name=properties.get("name"),
                    domain=properties.get("domain"),
                    # All properties from HubSpot
                    properties=properties,
                    created_at=parse_hubspot_datetime(company.get("createdAt")),
                    updated_at=parse_hubspot_datetime(company.get("updatedAt")),
                    archived=company.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_deal_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Deal entities from HubSpot.

        This uses the REST CRM API endpoint for deals:
          GET /crm/v3/objects/deals
        """
        url = "https://api.hubapi.com/crm/v3/objects/deals"
        while url:
            data = await self._get_with_auth(client, url)
            for deal in data.get("results", []):
                properties = deal.get("properties", {})

                yield HubspotDealEntity(
                    entity_id=deal["id"],
                    # Core fields for easy access
                    deal_name=properties.get("dealname"),
                    amount=self._safe_float_conversion(properties.get("amount")),
                    # All properties from HubSpot
                    properties=properties,
                    created_at=parse_hubspot_datetime(deal.get("createdAt")),
                    updated_at=parse_hubspot_datetime(deal.get("updatedAt")),
                    archived=deal.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def _generate_ticket_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Ticket entities from HubSpot.

        This uses the REST CRM API endpoint for tickets:
          GET /crm/v3/objects/tickets
        """
        url = "https://api.hubapi.com/crm/v3/objects/tickets"
        while url:
            data = await self._get_with_auth(client, url)
            for ticket in data.get("results", []):
                properties = ticket.get("properties", {})

                yield HubspotTicketEntity(
                    entity_id=ticket["id"],
                    # Core fields for easy access
                    subject=properties.get("subject"),
                    content=properties.get("content"),
                    # All properties from HubSpot
                    properties=properties,
                    created_at=parse_hubspot_datetime(ticket.get("createdAt")),
                    updated_at=parse_hubspot_datetime(ticket.get("updatedAt")),
                    archived=ticket.get("archived", False),
                )

            paging = data.get("paging", {})
            next_link = paging.get("next", {}).get("link")
            url = next_link if next_link else None

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from HubSpot.

        Yields:
            HubSpot entities: Contacts, Companies, Deals, and Tickets.
        """
        async with httpx.AsyncClient() as client:
            # Yield contact entities
            async for contact_entity in self._generate_contact_entities(client):
                yield contact_entity

            # Yield company entities
            async for company_entity in self._generate_company_entities(client):
                yield company_entity

            # Yield deal entities
            async for deal_entity in self._generate_deal_entities(client):
                yield deal_entity

            # Yield ticket entities
            async for ticket_entity in self._generate_ticket_entities(client):
                yield ticket_entity
