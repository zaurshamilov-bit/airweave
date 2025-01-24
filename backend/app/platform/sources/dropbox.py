"""Dropbox source implementation."""

from typing import AsyncGenerator, Dict, List, Optional

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.dropbox import (
    DropboxAccountChunk,
    DropboxFileChunk,
    DropboxFolderChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Dropbox", "dropbox", AuthType.oauth2_with_refresh)
class DropboxSource(BaseSource):
    """Dropbox source implementation."""

    @classmethod
    async def create(cls, access_token: str) -> "DropboxSource":
        """Create a new Dropbox source.

        Args:
            access_token: The OAuth2 access token for Dropbox API access.

        Returns:
            A configured DropboxSource instance.
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        method: str = "GET",
        json_body: Optional[Dict] = None,
    ) -> Dict:
        """Make an authenticated request to the Dropbox API.

        Args:
            client: The HTTPX client instance.
            url: The API endpoint URL.
            method: HTTP method to use (default: "GET").
            json_body: Optional JSON payload for POST requests.

        Returns:
            The JSON response from the API.

        Raises:
            HTTPError: If the request fails.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        if method.upper() == "GET":
            response = await client.get(url, headers=headers)
        else:
            response = await client.post(url, headers=headers, json=json_body or {})
        response.raise_for_status()
        return response.json()

    async def _generate_account_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate Dropbox account-level chunks.

        Args:
            client: The HTTPX client instance.

        Yields:
            Account-level chunks containing user/team information.
        """
        yield DropboxAccountChunk(
            source_name="dropbox",
            entity_id="dummy_account_entity",
            breadcrumbs=[],
            display_name="My Dropbox Account",
            account_id="account-123",
            email="me@example.com",
            profile_photo_url=None,
            is_team=False,
        )

    async def _generate_folder_chunks(
        self,
        client: httpx.AsyncClient,
        account_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate folder chunks for a given Dropbox account.

        Args:
            client: The HTTPX client instance.
            account_breadcrumb: Breadcrumb for the parent account.

        Yields:
            Folder chunks containing metadata about Dropbox folders.
        """
        # Dummy placeholder for MVP:
        yield DropboxFolderChunk(
            source_name="dropbox",
            entity_id="folder-entity-id",
            breadcrumbs=[account_breadcrumb],
            folder_id="folder-123",
            name="Example Folder",
            path_lower="/example_folder",
            path_display="/Example Folder",
            shared_folder_id=None,
            is_team_folder=False,
        )

    async def _generate_file_chunks(
        self,
        client: httpx.AsyncClient,
        folder_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate file chunks within a given folder.

        Args:
            client: The HTTPX client instance.
            folder_breadcrumbs: List of breadcrumbs for the parent folders.

        Yields:
            File chunks containing metadata about Dropbox files.
        """
        yield DropboxFileChunk(
            source_name="dropbox",
            entity_id="file-entity-id",
            breadcrumbs=folder_breadcrumbs,
            file_id="file-123",
            name="Example File.pdf",
            path_lower="/example_folder/example_file.pdf",
            path_display="/Example Folder/Example File.pdf",
            rev="0123456789abcdef",
            client_modified=None,
            server_modified=None,
            size=1024,
            is_downloadable=True,
            sharing_info={},
        )

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Dropbox.

        Yields:
            A sequence of chunks in the following order:
            1. Account-level chunks
            2. Folder chunks for each account
            3. File chunks for each folder
        """
        async with httpx.AsyncClient() as client:
            # 1. Account(s)
            async for account_chunk in self._generate_account_chunks(client):
                yield account_chunk

                account_breadcrumb = Breadcrumb(
                    entity_id=account_chunk.account_id,
                    name=account_chunk.display_name,
                    type="account",
                )

                # 2. Folders
                async for folder_chunk in self._generate_folder_chunks(client, account_breadcrumb):
                    yield folder_chunk

                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_chunk.folder_id,
                        name=folder_chunk.name,
                        type="folder",
                    )
                    folder_breadcrumbs = [account_breadcrumb, folder_breadcrumb]

                    # 3. Files
                    async for file_chunk in self._generate_file_chunks(client, folder_breadcrumbs):
                        yield file_chunk
