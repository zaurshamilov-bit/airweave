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

from typing import Any, AsyncGenerator, List

import httpx

from app.core.logging import logger
from app.platform.auth.schemas import AuthType
from app.platform.decorators import source
from app.platform.entities._base import BaseEntity, Breadcrumb
from app.platform.entities.confluence import (
    ConfluenceBlogPostEntity,
    ConfluenceCommentEntity,
    ConfluenceDatabaseEntity,
    ConfluenceFolderEntity,
    ConfluenceLabelEntity,
    ConfluencePageEntity,
    ConfluenceSpaceEntity,
)
from app.platform.sources._base import BaseSource


@source("Confluence", "confluence", AuthType.oauth2_with_refresh)
class ConfluenceSource(BaseSource):
    """Confluence source implementation, retrieving content in a hierarchical fashion.

    This connector retrieves data from Confluence to yield the following entities:
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

    @staticmethod
    async def _get_accessible_resources(access_token: str) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token.

        Args:
            access_token: The OAuth access token

        Returns:
            list[dict]: List of accessible resources, each containing 'id' and 'url' keys
        """
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            try:
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
                )
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Error getting accessible resources: {str(e)}")
                return []

    @staticmethod
    async def _extract_cloud_id(access_token: str) -> tuple[str, str]:
        """Extract the Atlassian Cloud ID from OAuth 2.0 accessible-resources.

        Args:
            access_token: The OAuth access token

        Returns:
            cloud_id (str): The cloud instance ID
        """
        try:
            resources = await ConfluenceSource._get_accessible_resources(access_token)

            if not resources:
                logger.warning("No accessible resources found")
                return ""

            # Use the first available resource
            # In most cases, there will only be one resource
            resource = resources[0]
            cloud_id = resource.get("id", "")

            if not cloud_id:
                logger.warning("Missing ID in accessible resources")
            return cloud_id

        except Exception as e:
            logger.error(f"Error extracting cloud ID: {str(e)}")
            return ""

    @classmethod
    async def create(cls, access_token: str) -> "ConfluenceSource":
        """Create a new Confluence source instance."""
        instance = cls()
        instance.access_token = access_token
        instance.cloud_id = await cls._extract_cloud_id(access_token)
        instance.base_url = f"https://api.atlassian.com/ex/confluence/{instance.cloud_id}"
        logger.info(f"Initialized Confluence source with base URL: {instance.base_url}")
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Confluence REST API using the provided URL.

        By default, we're using OAuth 2.0 with refresh tokens for authentication.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",  # Required for CSRF protection
        }

        # Add cloud instance ID if available
        if self.cloud_id:
            headers["X-Cloud-ID"] = self.cloud_id

        logger.debug(f"Making request to {url} with headers: {headers}")
        response = await client.get(url, headers=headers)

        if not response.is_success:
            logger.error(f"Request failed with status {response.status_code}")
            logger.error(f"Response headers: {dict(response.headers)}")
            logger.error(f"Response body: {response.text}")

        response.raise_for_status()
        return response.json()

    async def _generate_space_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ConfluenceSpaceEntity, None]:
        """Generate ConfluenceSpaceEntity objects."""
        url = "https://your-domain.atlassian.net/wiki/api/v2/spaces?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for space in data.get("results", []):
                yield ConfluenceSpaceEntity(
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

    async def _generate_page_entities(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ConfluencePageEntity, None]:
        """Generate ConfluencePageEntity objects for a space (optionally also retrieve children)."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/content/page?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for page in data.get("results", []):
                page_breadcrumbs = [space_breadcrumb]
                yield ConfluencePageEntity(
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

    async def _generate_blog_post_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceBlogPostEntity objects."""
        url = "https://your-domain.atlassian.net/wiki/api/v2/blogposts?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for blog in data.get("results", []):
                yield ConfluenceBlogPostEntity(
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

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, content_id: str, parent_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceCommentEntity objects for a given content (page, blog, etc.).

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
                yield ConfluenceCommentEntity(
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
    async def _generate_label_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceLabelEntity objects."""
        # The Confluence v2 REST API for labels is still evolving; example endpoint:
        url = "https://your-domain.atlassian.net/wiki/api/v2/labels?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for label_obj in data.get("results", []):
                yield ConfluenceLabelEntity(
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

    async def _generate_database_entities(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceDatabaseEntity objects for a given space."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/databases?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for database in data.get("results", []):
                yield ConfluenceDatabaseEntity(
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

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceFolderEntity objects for a given space."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/folders?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for folder in data.get("results", []):
                yield ConfluenceFolderEntity(
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

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all Confluence content."""
        async with httpx.AsyncClient() as client:
            # 1) Yield all spaces (top-level)
            async for space_entity in self._generate_space_entities(client):
                yield space_entity

                space_breadcrumb = Breadcrumb(
                    entity_id=space_entity.entity_id,
                    name=space_entity.name or "",
                    type="space",
                )

                # 2) For each space, yield pages and their children
                async for page_entity in self._generate_page_entities(
                    client,
                    space_key=space_entity.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield page_entity

                    page_breadcrumbs = [
                        space_breadcrumb,
                        Breadcrumb(
                            entity_id=page_entity.entity_id,
                            name=page_entity.title or "",
                            type="page",
                        ),
                    ]
                    async for comment_entity in self._generate_comment_entities(
                        client,
                        content_id=page_entity.content_id,
                        parent_breadcrumbs=page_breadcrumbs,
                    ):
                        yield comment_entity

                # 3) For each space, yield databases
                async for database_entity in self._generate_database_entities(
                    client,
                    space_key=space_entity.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield database_entity

                # 4) For each space, yield folders
                async for folder_entity in self._generate_folder_entities(
                    client,
                    space_key=space_entity.space_key,
                    space_breadcrumb=space_breadcrumb,
                ):
                    yield folder_entity

            # 5) Yield blog posts and their comments
            async for blog_entity in self._generate_blog_post_entities(client):
                yield blog_entity

                blog_breadcrumb = Breadcrumb(
                    entity_id=blog_entity.entity_id,
                    name=blog_entity.title or "",
                    type="blogpost",
                )
                async for comment_entity in self._generate_comment_entities(
                    client,
                    blog_entity.content_id,
                    [blog_breadcrumb],
                ):
                    yield comment_entity

            # 6) Yield labels (global or any label scope)
            async for label_entity in self._generate_label_entities(client):
                yield label_entity

            # 7) Yield tasks
            async for task_entity in self._generate_task_entities(client):
                yield task_entity

            # 8) Yield whiteboards
            async for whiteboard_entity in self._generate_whiteboard_entities(client):
                yield whiteboard_entity

            # 9) Yield custom content
            async for custom_content_entity in self._generate_custom_content_entities(client):
                yield custom_content_entity
