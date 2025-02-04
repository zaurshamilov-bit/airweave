"""Notion source implementation."""

from typing import AsyncGenerator, Dict, List

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.notion import (
    NotionDatabaseChunk,
    NotionPageChunk,
    NotionWorkspaceChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Notion", "notion", AuthType.oauth2)
class NotionSource(BaseSource):
    """Notion source implementation."""

    @classmethod
    async def create(cls, access_token: str) -> "NotionSource":
        """Create a new Notion source."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make an authenticated GET request to the Notion API.

        Notion requires a Notion-Version header, e.g. '2022-06-28' or newer.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",  # Adjust to your desired version
        }
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _generate_workspace_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate workspace chunks.

        Notion's API doesn't offer a direct
        'list workspaces' endpoint; for a typical integration, you might
        call 'GET /v1/users/me' to identify the workspace and yield a single chunk.
        """
        # Example of getting your bot user, which might let you parse workspace info
        # data = await self._get_with_auth(client, "https://api.notion.com/v1/users/me")
        # This is just a placeholder:
        yield NotionWorkspaceChunk(
            source_name="notion",
            entity_id="dummy_workspace_entity",
            sync_id=self.sync_id,
            breadcrumbs=[],
            name="My Notion Workspace",
            workspace_id="workspace-123",
            domain="my-team.notion.site",
            icon=None,
        )

    async def _generate_database_chunks(
        self, client: httpx.AsyncClient, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate database chunks.

        You'd typically call
        'GET /v1/search' with a filter for 'database' or
        'GET /v1/databases/{database_id}' to fetch each database.([2](https://developers.notion.com/reference/search))
        """
        # data = await self._get_with_auth(client, "https://api.notion.com/v1/search")
        # Filter out 'database' objects if you want to mimic the Asana workspace->database approach.
        # Below is just a placeholder yield:
        yield NotionDatabaseChunk(
            source_name="notion",
            entity_id="db-entity-id",
            sync_id=self.sync_id,
            breadcrumbs=[workspace_breadcrumb],
            name="Example Database",
            database_id="database-345",
            title="Demo Database",
            created_time=None,
            last_edited_time=None,
            icon=None,
            cover=None,
        )

    async def _generate_page_chunks(
        self, client: httpx.AsyncClient, database_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate page chunks within a given database or workspace.

        Typically, you'd call 'POST /v1/databases/{database_id}/query'
        or again use /v1/search with appropriate filters.([2](https://developers.notion.com/reference/post-database-query))
        """
        # data = await self._get_with_auth(client, f"https://api.notion.com/v1/databases/{db_id}/query")
        yield NotionPageChunk(
            source_name="notion",
            entity_id="page-entity-id",
            sync_id=self.sync_id,
            breadcrumbs=database_breadcrumbs,
            name="Sample Page",
            page_id="page-123",
            created_time=None,
            last_edited_time=None,
            archived=False,
            icon=None,
            cover=None,
            properties={},
        )

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all Notion chunks.

        Ties everything together: fetch workspaces, fetch databases,
        then fetch pages from each database, etc.
        """
        async with httpx.AsyncClient() as client:
            # 1. Workspaces
            async for workspace_chunk in self._generate_workspace_chunks(client):
                yield workspace_chunk

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_chunk.workspace_id,
                    name=workspace_chunk.name,
                    type="workspace",
                )

                # 2. Databases
                async for database_chunk in self._generate_database_chunks(
                    client, workspace_breadcrumb
                ):
                    yield database_chunk

                    database_breadcrumb = Breadcrumb(
                        entity_id=database_chunk.database_id,
                        name=database_chunk.name,
                        type="database",
                    )
                    database_breadcrumbs = [workspace_breadcrumb, database_breadcrumb]

                    # 3. Pages
                    async for page_chunk in self._generate_page_chunks(
                        client, database_breadcrumbs
                    ):
                        yield page_chunk
