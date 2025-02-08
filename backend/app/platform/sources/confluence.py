"""Confluence source implementation.

Retrieves data (read-only) from a user's Confluence instance:
  - Spaces
  - Pages (and their children)
  - Blog Posts
  - Comments
  - Labels
  - Tasks
  - Whiteboards
  - Custom Content
  - Databases
  - Folders

References:
    https://developer.atlassian.com/cloud/confluence/rest/v2/intro/
    https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
"""

from typing import AsyncGenerator, Dict, List

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.confluence import (
    ConfluenceBlogPostChunk,
    ConfluenceCommentChunk,
    ConfluenceDatabaseChunk,
    ConfluenceFolderChunk,
    ConfluenceLabelChunk,
    ConfluencePageChunk,
    ConfluenceSpaceChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Confluence", "confluence", AuthType.oauth2_with_refresh)
class ConfluenceSource(BaseSource):
    """Confluence source implementation, retrieving content in a hierarchical fashion.

    This connector retrieves data from Confluence to yield the following chunks:
      - Space
      - Page (including child pages as desired)
      - Blog Post
      - Comment
      - Label
      - Task
      - Whiteboard
      - Custom Content
      - (Optionally) Database, Folder, etc.
    """

    @classmethod
    async def create(cls, access_token: str) -> "ConfluenceSource":
        """Create a new Confluence source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make an authenticated GET request to the Confluence REST API v2."""
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return response.json()

    async def _generate_space_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ConfluenceSpaceChunk, None]:
        """Generate ConfluenceSpaceChunk objects."""
        url = "https://your-domain.atlassian.net/wiki/api/v2/spaces?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for space in data.get("results", []):
                yield ConfluenceSpaceChunk(
                    source_name="confluence",
                    entity_id=space["id"],
                    breadcrumbs=[],  # top-level object
                    space_key=space["key"],
                    name=space.get("name"),
                    space_type=space.get("type"),
                    description=space.get("description"),
                    status=space.get("status"),
                    homepage_id=space.get("homepageId"),
                    created_at=space.get("createdAt"),
                    updated_at=space.get("updatedAt"),
                )
            # Cursor-based pagination (check for next link)
            next_link = data.get("_links", {}).get("next")
            if next_link:
                # _links.next is usually a relative path; build a full URL if needed
                url = f"https://your-domain.atlassian.net{next_link}"
            else:
                url = None

    async def _generate_page_chunks(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ConfluencePageChunk, None]:
        """Generate ConfluencePageChunk objects for a space (optionally also retrieve children)."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/content/page?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for page in data.get("results", []):
                page_breadcrumbs = [space_breadcrumb]
                yield ConfluencePageChunk(
                    source_name="confluence",
                    entity_id=page["id"],
                    breadcrumbs=page_breadcrumbs,
                    content_id=page["id"],
                    title=page.get("title"),
                    space_key=space_key,
                    body=page.get("body", {}).get("storage", {}).get("value"),
                    version=page.get("version", {}).get("number"),
                    status=page.get("status"),
                    created_at=page.get("createdAt"),
                    updated_at=page.get("updatedAt"),
                )
                # Optionally fetch children or comments for each page
                # or recursively fetch child pages if you need deeper nesting.

            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    async def _generate_blog_post_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate ConfluenceBlogPostChunk objects."""
        url = "https://your-domain.atlassian.net/wiki/api/v2/blogposts?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for blog in data.get("results", []):
                yield ConfluenceBlogPostChunk(
                    source_name="confluence",
                    entity_id=blog["id"],
                    breadcrumbs=[],  # or possibly attach space breadcrumb if needed
                    content_id=blog["id"],
                    title=blog.get("title"),
                    space_key=blog.get("spaceId"),
                    body=(blog.get("body", {}).get("storage", {}).get("value")),
                    version=blog.get("version", {}).get("number"),
                    status=blog.get("status"),
                    created_at=blog.get("createdAt"),
                    updated_at=blog.get("updatedAt"),
                )

            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    async def _generate_comment_chunks(
        self, client: httpx.AsyncClient, content_id: str, parent_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate ConfluenceCommentChunk objects for a given content (page, blog, etc.).

        For example:
          GET /wiki/api/v2/pages/{content_id}/child/comment
        or
          GET /wiki/api/v2/blogposts/{content_id}/child/comment
        depending on the content type.
        """
        # Example: retrieving comments for a page
        url = f"https://your-domain.atlassian.net/wiki/api/v2/pages/{content_id}/child/comment?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for comment in data.get("results", []):
                yield ConfluenceCommentChunk(
                    source_name="confluence",
                    entity_id=comment["id"],
                    breadcrumbs=parent_breadcrumbs,
                    content_id=comment["id"],
                    parent_content_id=comment.get("container", {}).get("id"),
                    text=(comment.get("body", {}).get("storage", {}).get("value")),
                    created_by=comment.get("createdBy"),
                    created_at=comment.get("createdAt"),
                    updated_at=comment.get("updatedAt"),
                    status=comment.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    # You can define similar methods for label, task, whiteboard, custom content, etc.
    # For example:
    async def _generate_label_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate ConfluenceLabelChunk objects."""
        # The Confluence v2 REST API for labels is still evolving; example endpoint:
        url = "https://your-domain.atlassian.net/wiki/api/v2/labels?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for label_obj in data.get("results", []):
                yield ConfluenceLabelChunk(
                    source_name="confluence",
                    entity_id=label_obj["id"],
                    breadcrumbs=[],
                    name=label_obj.get("name", ""),
                    label_type=label_obj.get("type"),
                    owner_id=label_obj.get("ownerId"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    # Similar approach for tasks, whiteboards, custom content...
    # The actual endpoints may differ, but the pattern of pagination remains the same.

    async def _generate_database_chunks(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate ConfluenceDatabaseChunk objects for a given space."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/databases?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for database in data.get("results", []):
                yield ConfluenceDatabaseChunk(
                    source_name="confluence",
                    entity_id=database["id"],
                    breadcrumbs=[space_breadcrumb],
                    content_id=database["id"],
                    title=database.get("title"),
                    space_key=space_key,
                    description=database.get("description"),
                    created_at=database.get("createdAt"),
                    updated_at=database.get("updatedAt"),
                    status=database.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    async def _generate_folder_chunks(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate ConfluenceFolderChunk objects for a given space."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/folders?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for folder in data.get("results", []):
                yield ConfluenceFolderChunk(
                    source_name="confluence",
                    entity_id=folder["id"],
                    breadcrumbs=[space_breadcrumb],
                    content_id=folder["id"],
                    title=folder.get("title"),
                    space_key=space_key,
                    created_at=folder.get("createdAt"),
                    updated_at=folder.get("updatedAt"),
                    status=folder.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all Confluence content."""
        async with httpx.AsyncClient() as client:
            # 1) Yield all spaces (top-level)
            async for space_chunk in self._generate_space_chunks(client):
                yield space_chunk

                space_breadcrumb = Breadcrumb(
                    entity_id=space_chunk.entity_id,
                    name=space_chunk.name or "",
                    type="space",
                )

                # 2) For each space, yield pages and their children
                async for page_chunk in self._generate_page_chunks(
                    client,
                    space_key=space_chunk.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield page_chunk

                    page_breadcrumbs = [
                        space_breadcrumb,
                        Breadcrumb(
                            entity_id=page_chunk.entity_id,
                            name=page_chunk.title or "",
                            type="page",
                        ),
                    ]
                    async for comment_chunk in self._generate_comment_chunks(
                        client,
                        content_id=page_chunk.content_id,
                        parent_breadcrumbs=page_breadcrumbs,
                    ):
                        yield comment_chunk

                # 3) For each space, yield databases
                async for database_chunk in self._generate_database_chunks(
                    client,
                    space_key=space_chunk.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield database_chunk

                # 4) For each space, yield folders
                async for folder_chunk in self._generate_folder_chunks(
                    client,
                    space_key=space_chunk.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield folder_chunk

            # 5) Yield blog posts and their comments
            async for blog_chunk in self._generate_blog_post_chunks(client):
                yield blog_chunk

                blog_breadcrumb = Breadcrumb(
                    entity_id=blog_chunk.entity_id,
                    name=blog_chunk.title or "",
                    type="blogpost",
                )
                async for comment_chunk in self._generate_comment_chunks(
                    client,
                    blog_chunk.content_id,
                    [blog_breadcrumb],
                ):
                    yield comment_chunk

            # 6) Yield labels (global or any label scope)
            async for label_chunk in self._generate_label_chunks(client):
                yield label_chunk

            # 7) Yield tasks
            async for task_chunk in self._generate_task_chunks(client):
                yield task_chunk

            # 8) Yield whiteboards
            async for whiteboard_chunk in self._generate_whiteboard_chunks(client):
                yield whiteboard_chunk

            # 9) Yield custom content
            async for custom_content_chunk in self._generate_custom_content_chunks(client):
                yield custom_content_chunk
