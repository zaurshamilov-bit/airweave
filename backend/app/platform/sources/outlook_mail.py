"""Outlook Mail source implementation.

Retrieves data (read-only) from a user's Outlook/Microsoft 365 mailbox via Microsoft Graph API:
 - MailFolders (in a hierarchical folder structure)
 - Messages (within each folder)

References (Mail API only):
    https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0

This connector follows the general style of other source connectors (e.g., Asana, Todoist, HubSpot).
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.outlook_mail import OutlookMailFolderChunk, OutlookMessageChunk
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Outlook Mail", "outlook_mail", AuthType.oauth2_with_refresh)
class OutlookMailSource(BaseSource):
    """Outlook Mail source implementation (read-only).

    This connector retrieves Outlook mail folders in a hierarchical fashion
    and yields OutlookMailFolderChunk for each folder. For each folder, it
    also retrieves email messages and yields OutlookMessageChunk items.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(cls, access_token: str) -> "OutlookMailSource":
        """Create an OutlookMailSource instance with the given access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
        """Utility to make an authenticated GET request to Microsoft Graph.

        Raises for non-2xx responses and returns parsed JSON.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _generate_folder_chunks(
        self,
        client: httpx.AsyncClient,
        folder_id: Optional[str] = None,
        parent_breadcrumbs: Optional[List[Breadcrumb]] = None,
    ) -> AsyncGenerator[OutlookMailFolderChunk, None]:
        """Recursively generate OutlookMailFolderChunk objects.

        Traverses the mail folder hierarchy via Microsoft Graph.

        If folder_id is None, it fetches top-level folders with GET /me/mailFolders.
        Otherwise, it fetches children with GET /me/mailFolders/{folder_id}/childFolders.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        # Decide the endpoint: top-level vs. child folders
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/childFolders"
        else:
            # top-level mail folders
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders"

        while url:
            data = await self._get_with_auth(client, url)
            for folder in data.get("value", []):
                # Yield folder chunk
                folder_chunk = OutlookMailFolderChunk(
                    source_name="outlook_mail",
                    entity_id=folder["id"],
                    breadcrumbs=parent_breadcrumbs,
                    display_name=folder["displayName"],
                    parent_folder_id=folder.get("parentFolderId"),
                    child_folder_count=folder.get("childFolderCount", 0),
                    total_item_count=folder.get("totalItemCount", 0),
                    unread_item_count=folder.get("unreadItemCount", 0),
                    well_known_name=folder.get("wellKnownName"),
                )

                yield folder_chunk

                # Build breadcrumb for this folder
                folder_breadcrumb = Breadcrumb(
                    entity_id=folder_chunk.entity_id,
                    name=folder_chunk.display_name,
                    type="folder",
                )

                # Recursively yield child folders
                if folder_chunk.child_folder_count:
                    async for child_folder_chunk in self._generate_folder_chunks(
                        client,
                        folder_chunk.entity_id,
                        parent_breadcrumbs + [folder_breadcrumb],
                    ):
                        yield child_folder_chunk

            # Handle pagination if @odata.nextLink is present
            next_link = data.get("@odata.nextLink")
            url = next_link if next_link else None

    async def _generate_message_chunks(
        self,
        client: httpx.AsyncClient,
        folder_chunk: OutlookMailFolderChunk,
    ) -> AsyncGenerator[OutlookMessageChunk, None]:
        """Generate OutlookMessageChunk objects for a given folder.

        Fetches messages with GET /me/mailFolders/{folderId}/messages.
        """
        folder_breadcrumb = Breadcrumb(
            entity_id=folder_chunk.entity_id,
            name=folder_chunk.display_name,
            type="folder",
        )
        breadcrumbs = folder_chunk.breadcrumbs + [folder_breadcrumb]

        url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_chunk.entity_id}/messages"
        while url:
            data = await self._get_with_auth(client, url)
            for msg in data.get("value", []):
                yield OutlookMessageChunk(
                    source_name="outlook_mail",
                    entity_id=msg["id"],
                    breadcrumbs=breadcrumbs,
                    subject=msg.get("subject"),
                    body_preview=msg.get("bodyPreview"),
                    body_content=(msg.get("body", {}) or {}).get("content"),
                    is_read=msg.get("isRead", False),
                    is_draft=msg.get("isDraft", False),
                    importance=msg.get("importance"),
                    has_attachments=msg.get("hasAttachments", False),
                    internet_message_id=msg.get("internetMessageId"),
                    from_=msg.get("from"),
                    to_recipients=msg.get("toRecipients", []),
                    cc_recipients=msg.get("ccRecipients", []),
                    bcc_recipients=msg.get("bccRecipients", []),
                    sent_at=msg.get("sentDateTime"),
                    received_at=msg.get("receivedDateTime"),
                    created_at=msg.get("createdDateTime"),
                    updated_at=msg.get("lastModifiedDateTime"),
                )

            # Handle pagination if @odata.nextLink is present
            next_link = data.get("@odata.nextLink")
            url = next_link if next_link else None

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all Outlook mail chunks.

        Yields chunks in the following order:
          - Mail folders (recursive)
          - Messages in each folder
        """
        async with httpx.AsyncClient() as client:
            # 1) Generate all mail folders (including subfolders)
            #    and yield them as OutlookMailFolderChunk
            async for folder_chunk in self._generate_folder_chunks(client):
                yield folder_chunk

                # 2) For each folder, generate and yield messages in that folder
                async for message_chunk in self._generate_message_chunks(client, folder_chunk):
                    yield message_chunk
