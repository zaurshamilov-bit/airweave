"""Notion source implementation."""

from typing import AsyncGenerator, Dict, List

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.notion import (
    NotionBlockChunk,
    NotionDatabaseChunk,
    NotionPageChunk,
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
        """Make an authenticated GET request to the Notion API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: Dict) -> Dict:
        """Make an authenticated POST request to the Notion API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }
        response = await client.post(url, headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()

    async def _search_notion_objects(
        self, client: httpx.AsyncClient, query: str = "", filter_type: str = None
    ) -> AsyncGenerator[Dict, None]:
        """Search for Notion objects using the search endpoint.

        Args:
            client: httpx.AsyncClient
            query: Optional search query
            filter_type: Optional filter for object type ("page" or "database")

        Returns:
            AsyncGenerator[Dict, None]: A generator of Notion objects
        """
        url = "https://api.notion.com/v1/search"
        has_more = True
        start_cursor = None

        while has_more:
            json_data = {"query": query}
            if filter_type:
                json_data["filter"] = {"property": "object", "value": filter_type}
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            response = await self._post_with_auth(client, url, json_data)

            for result in response.get("results", []):
                yield result

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

    async def _get_block_children(
        self, client: httpx.AsyncClient, block_id: str
    ) -> AsyncGenerator[Dict, None]:
        """Retrieve all children blocks of a block."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        has_more = True
        start_cursor = None

        while has_more:
            url_with_params = url
            if start_cursor:
                url_with_params = f"{url}?start_cursor={start_cursor}"

            response = await self._get_with_auth(client, url_with_params)

            for block in response.get("results", []):
                yield block

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

    def _create_database_chunk(self, database: Dict) -> NotionDatabaseChunk:
        """Create a database chunk from API response."""
        return NotionDatabaseChunk(
            source_name="notion",
            database_id=database["id"],
            entity_id=database["id"],
            name=database.get("title", [{}])[0].get("plain_text", "Untitled"),
            description=(
                database.get("description", [])[0].get("plain_text", "")
                if database.get("description")
                else ""
            ),
            created_time=database.get("created_time"),
            last_edited_time=database.get("last_edited_time"),
        )

    def _create_page_chunk(self, page: Dict, breadcrumbs: List[Breadcrumb]) -> NotionPageChunk:
        """Create a page chunk from API response."""
        parent = page.get("parent", {})

        # Safely extract title with proper nesting and fallbacks
        title = (
            page.get("properties", {})
            .get("title", {})
            .get("title", [{}])[0:1][  # Get first element or empty list
                0
            ]  # Get first element (safe because of [0:1] above)
            .get("plain_text", "Untitled")
            if isinstance(page.get("properties", {}).get("title"), dict)
            else "Untitled"
        )

        return NotionPageChunk(
            source_name="notion",
            page_id=page["id"],
            entity_id=page["id"],
            breadcrumbs=breadcrumbs,
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            title=title,
            created_time=page.get("created_time"),
            last_edited_time=page.get("last_edited_time"),
            archived=page.get("archived", False),
            content=None,  # Will be populated from blocks
        )

    def _create_block_chunk(
        self, block: Dict, parent_id: str, breadcrumbs: List[Breadcrumb]
    ) -> NotionBlockChunk:
        """Create a block chunk from API response."""
        return NotionBlockChunk(
            source_name="notion",
            block_id=block["id"],
            entity_id=block["id"],
            breadcrumbs=breadcrumbs,
            parent_id=parent_id,
            block_type=block["type"],
            text_content=block.get(block["type"], {}).get("text", {}).get("content"),
            has_children=block.get("has_children", False),
            children_ids=[],  # Will be populated if has_children is True
        )

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Notion.

        Instead of traversing a hierarchy, we use Notion's search endpoint to get:
        1. All databases
        2. All pages (both in databases and standalone)
        3. All blocks within pages
        """
        async with httpx.AsyncClient() as client:
            # 1. Get all databases
            async for database in self._search_notion_objects(client, filter_type="database"):
                database_chunk = self._create_database_chunk(database)
                yield database_chunk

            # 2. Get all pages
            async for page in self._search_notion_objects(client, filter_type="page"):
                # Create breadcrumbs based on parent
                breadcrumbs = []
                parent = page.get("parent", {})
                if parent.get("type") == "database_id":
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent["database_id"],
                            name="Parent Database",  # We could cache database names if needed
                            type="database",
                        )
                    )
                elif parent.get("type") == "page_id":
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent["page_id"],
                            name="Parent Page",  # We could cache page names if needed
                            type="page",
                        )
                    )

                page_chunk = self._create_page_chunk(page, breadcrumbs)
                yield page_chunk

                # 3. Get all blocks for this page
                page_breadcrumb = Breadcrumb(
                    entity_id=page["id"], name=page_chunk.title, type="page"
                )
                block_breadcrumbs = [*breadcrumbs, page_breadcrumb]

                async for block in self._get_block_children(client, page["id"]):
                    block_chunk = self._create_block_chunk(block, page["id"], block_breadcrumbs)
                    yield block_chunk

                    # If block has children, get them too
                    if block["has_children"]:
                        block_breadcrumb = Breadcrumb(
                            entity_id=block["id"],
                            name=block_chunk.text_content or "Block",
                            type="block",
                        )
                        child_breadcrumbs = [*block_breadcrumbs, block_breadcrumb]

                        async for child_block in self._get_block_children(client, block["id"]):
                            child_chunk = self._create_block_chunk(
                                child_block, block["id"], child_breadcrumbs
                            )
                            yield child_chunk
