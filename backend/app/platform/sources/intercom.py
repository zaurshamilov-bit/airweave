from typing import AsyncGenerator, Dict, Optional

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk
from app.platform.chunks.intercom import (
    IntercomContactChunk,
    IntercomCompanyChunk,
    IntercomConversationChunk,
    IntercomTicketChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Intercom", "intercom", AuthType.oauth2)
class IntercomSource(BaseSource):
    """
    Intercom source implementation.

    This connector retrieves data from Intercom objects such as Contacts, Companies,
    Conversations, and Tickets, then yields them as chunks using their respective
    Intercom chunk schemas.
    """

    @classmethod
    async def create(cls, access_token: str) -> "IntercomSource":
        """
        Create a new Intercom source instance.
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated GET request to the Intercom API.
        For example, to retrieve contacts:
          GET https://api.intercom.io/contacts
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _generate_contact_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """
        Generate Contact chunks from Intercom.
        Using the Contacts endpoint:
          GET https://api.intercom.io/contacts
        """
        url = "https://api.intercom.io/contacts"
        while url:
            data = await self._get_with_auth(client, url)
            for contact in data.get("data", []):
                yield IntercomContactChunk(
                    source_name="intercom",
                    entity_id=contact.get("id"),
                    role=contact.get("role"),
                    external_id=contact.get("external_id"),
                    email=contact.get("email"),
                    phone=contact.get("phone"),
                    name=contact.get("name"),
                    avatar=contact.get("avatar", {}).get("image_url"),
                    created_at=contact.get("created_at"),
                    updated_at=contact.get("updated_at"),
                    archived=contact.get("archived", False),
                )

            # Handle pagination
            pages = data.get("pages", {})
            next_link = pages.get("next")
            url = next_link if next_link else None

    async def _generate_company_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """
        Generate Company chunks from Intercom.
        Using the Companies endpoint:
          GET https://api.intercom.io/companies
        """
        url = "https://api.intercom.io/companies"
        while url:
            data = await self._get_with_auth(client, url)
            for company in data.get("data", []):
                yield IntercomCompanyChunk(
                    source_name="intercom",
                    entity_id=company.get("id"),
                    name=company.get("name"),
                    company_id=company.get("company_id"),
                    plan=company.get("plan", {}).get("name"),
                    monthly_spend=company.get("monthly_spend"),
                    session_count=company.get("session_count"),
                    user_count=company.get("user_count"),
                    website=company.get("website"),
                    created_at=company.get("created_at"),
                    updated_at=company.get("updated_at"),
                    archived=company.get("archived", False),
                )

            # Handle pagination
            pages = data.get("pages", {})
            next_link = pages.get("next")
            url = next_link if next_link else None

    async def _generate_conversation_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """
        Generate Conversation chunks from Intercom.
        Using the Conversations endpoint:
          GET https://api.intercom.io/conversations
        """
        url = "https://api.intercom.io/conversations"
        while url:
            data = await self._get_with_auth(client, url)
            for convo in data.get("data", []):
                yield IntercomConversationChunk(
                    source_name="intercom",
                    entity_id=convo.get("id"),
                    conversation_id=convo.get("id", ""),
                    title=convo.get("title"),
                    state=convo.get("state"),
                    created_at=convo.get("created_at"),
                    updated_at=convo.get("updated_at"),
                    archived=convo.get("archived", False),
                )

            # Handle pagination
            pages = data.get("pages", {})
            next_link = pages.get("next")
            url = next_link if next_link else None

    async def _generate_ticket_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """
        Generate Ticket chunks from Intercom.
        Using a hypothetical Tickets endpoint:
          GET https://api.intercom.io/tickets
        (In Intercom, tickets may be handled within conversations or separate endpoints.
         Adjust the URL or approach accordingly based on your actual Intercom data model.)
        """
        url = "https://api.intercom.io/tickets"
        while url:
            data = await self._get_with_auth(client, url)
            for ticket in data.get("data", []):
                yield IntercomTicketChunk(
                    source_name="intercom",
                    entity_id=ticket.get("id"),
                    subject=ticket.get("subject"),
                    description=ticket.get("description"),
                    state=ticket.get("state"),
                    contact_id=ticket.get("contact_id"),
                    company_id=ticket.get("company_id"),
                    created_at=ticket.get("created_at"),
                    updated_at=ticket.get("updated_at"),
                    archived=ticket.get("archived", False),
                )

            # Handle pagination
            pages = data.get("pages", {})
            next_link = pages.get("next")
            url = next_link if next_link else None

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """
        Generate all chunks from Intercom:
        Contacts, Companies, Conversations, and Tickets.
        """
        async with httpx.AsyncClient() as client:
            # Yield contact chunks
            async for contact_chunk in self._generate_contact_chunks(client):
                yield contact_chunk

            # Yield company chunks
            async for company_chunk in self._generate_company_chunks(client):
                yield company_chunk

            # Yield conversation chunks
            async for conversation_chunk in self._generate_conversation_chunks(client):
                yield conversation_chunk

            # Yield ticket chunks
            async for ticket_chunk in self._generate_ticket_chunks(client):
                yield ticket_chunk
