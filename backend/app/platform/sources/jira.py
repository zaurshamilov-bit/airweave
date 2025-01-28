"""Jira source implementation.

Retrieves data (read-only) from a user's Jira Cloud instance:
 - Projects
 - Issues (within each project)
 - Comments (within each issue)
 - Statuses (global list)

References:
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/overview
"""

import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.jira import (
    JiraProjectChunk,
    JiraIssueChunk,
    JiraCommentChunk,
    JiraStatusChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Jira", "jira", AuthType.oauth2_with_refresh)
class JiraSource(BaseSource):
    """
    Jira source implementation (read-only).

    This connector retrieves hierarchical data from Jira's REST API:
      - Statuses (global list)
      - Projects
      - Issues (within each project)
      - Comments (within each issue)

    The Jira chunk schemas are defined in chunks/jira.py.
    """

    @classmethod
    async def create(cls, access_token: str) -> "JiraSource":
        """Create a new Jira source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """
        Make an authenticated GET request to the Jira REST API using the provided URL.

        By default, we're using OAuth 2.0 with refresh tokens for authentication.
        """
        headers = {"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"}
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _generate_status_chunks(
        self, client: httpx.AsyncClient, base_url: str
    ) -> AsyncGenerator[JiraStatusChunk, None]:
        """
        Generate JiraStatusChunk objects.

        Endpoint:
            GET /rest/api/3/status
        """
        url = f"{base_url}/rest/api/3/status"
        data = await self._get_with_auth(client, url)

        # This endpoint returns a list of status objects directly.
        for status in data:
            yield JiraStatusChunk(
                source_name="jira",
                entity_id=status["id"],
                name=status.get("name", ""),
                category=status.get("statusCategory", {}).get("name"),
                description=status.get("description"),
            )

    async def _generate_project_chunks(
        self, client: httpx.AsyncClient, base_url: str
    ) -> AsyncGenerator[JiraProjectChunk, None]:
        """
        Generate JiraProjectChunk objects.

        Endpoint:
            GET /rest/api/3/project
        """
        url = f"{base_url}/rest/api/3/project"
        data = await self._get_with_auth(client, url)

        # This endpoint returns a list of projects.
        for project in data:
            yield JiraProjectChunk(
                source_name="jira",
                entity_id=project["id"],
                breadcrumbs=[],  # top-level object, no parent
                project_key=project["key"],
                name=project.get("name"),
                project_type=project.get("projectTypeKey"),
                lead=project.get("lead"),
                description=project.get("description"),
                archived=project.get("archived", False),
            )

    async def _generate_comment_chunks(
        self, client: httpx.AsyncClient, base_url: str, issue: JiraIssueChunk
    ) -> AsyncGenerator[JiraCommentChunk, None]:
        """
        Generate JiraCommentChunk for each comment on a given issue.

        Endpoint:
            GET /rest/api/3/issue/{issueKey}/comment
        """
        comment_url = f"{base_url}/rest/api/3/issue/{issue.issue_key}/comment"
        while True:
            data = await self._get_with_auth(client, comment_url)

            # Comments are nested under data["comments"] or data["values"] depending on the version.
            # For Jira cloud (v3), the field is typically "comments" in the "comments" resource.
            comments = data.get("comments", [])
            for comment in comments:
                yield JiraCommentChunk(
                    source_name="jira",
                    entity_id=comment["id"],
                    breadcrumbs=[
                        # Provide a breadcrumb back to the Issue this comment is on
                        Breadcrumb(entity_id=issue.entity_id, name=issue.issue_key, type="issue")
                    ],
                    issue_key=issue.issue_key,
                    body=(
                        comment.get("body", {}).get("content")
                        if isinstance(comment.get("body"), dict)
                        else comment.get("body")
                    ),
                    author=comment.get("author"),
                    created_at=comment.get("created"),
                    updated_at=comment.get("updated"),
                )

            # Handle pagination, if any. Some Jira comment endpoints use "startAt" and "maxResults".
            # Check if we have more in data["total"] vs. data["maxResults"], etc.
            total = data.get("total", 0)
            if not total:
                break

            start_at = data.get("startAt", 0)
            max_results = data.get("maxResults", 50)
            next_start = start_at + max_results

            # If we've retrieved everything or there's no next page, break.
            if next_start >= total:
                break

            # Else, retrieve the next page:
            comment_url = f"{base_url}/rest/api/3/issue/{issue.issue_key}/comment?startAt={next_start}&maxResults={max_results}"

    async def _generate_issue_chunks(
        self, client: httpx.AsyncClient, base_url: str, project: JiraProjectChunk
    ) -> AsyncGenerator[JiraIssueChunk, None]:
        """
        Generate JiraIssueChunk for each issue in the given project.

        We use the Search endpoint with JQL to get issues belonging to the project.
        Endpoint:
            GET /rest/api/3/search?jql=project=<PROJECT_KEY>
        We'll handle pagination by checking total, startAt, maxResults from the response.
        After we fetch an issue, we can optionally parse watchers, labels, etc.
        """
        start_at = 0
        max_results = 50
        project_key = project.project_key

        while True:
            search_url = (
                f"{base_url}/rest/api/3/search"
                f"?jql=project={project_key}"
                f"&startAt={start_at}"
                f"&maxResults={max_results}"
                # Expand watchers, names, etc. if desired:
                f"&expand=names,watcher"
            )
            data = await self._get_with_auth(client, search_url)

            issues = data.get("issues", [])
            total = data.get("total", 0)

            for issue_data in issues:
                fields = issue_data.get("fields", {})
                # We can gather watchers from a watchers field or by a separate call if needed.
                watchers_info = {}
                if "watches" in fields:
                    watchers_info = fields["watches"].get("watchers", [])
                else:
                    # If watchers info is not included, we can optionally fetch watchers separately.
                    watchers_info = []  # or call watchers endpoint, omitted here for brevity.

                # We can also parse votes from fields if present (fields["votes"]).
                votes_info = None
                if "votes" in fields:
                    votes_info = fields["votes"].get("votes")

                # Grab labels from fields if present
                labels_info = fields.get("labels", [])

                yield JiraIssueChunk(
                    source_name="jira",
                    entity_id=issue_data["id"],
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=project.entity_id, name=project.name or "", type="project"
                        )
                    ],
                    issue_key=issue_data["key"],
                    summary=fields.get("summary"),
                    description=fields.get("description"),
                    status=fields.get("status", {}).get("name"),
                    priority=fields.get("priority", {}).get("name"),
                    issue_type=fields.get("issuetype", {}).get("name"),
                    assignee=fields.get("assignee"),
                    reporter=fields.get("reporter"),
                    resolution=fields.get("resolution", {}).get("name"),
                    created_at=fields.get("created"),
                    updated_at=fields.get("updated"),
                    resolved_at=fields.get("resolutiondate"),
                    labels=labels_info,
                    watchers=watchers_info if isinstance(watchers_info, list) else [],
                    votes=votes_info if isinstance(votes_info, int) else None,
                    archived=False,  # Jira doesn't provide a direct archived field for issues by default
                )

            start_at += max_results
            if start_at >= total:
                break

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Jira: Statuses, Projects, Issues, Comments."""
        # TODO: Make this dynamic from user env.
        # In practice, you would determine your Jira Cloud base URL or site URL.
        # This may come from the user's settings or environment. Here's an example pattern:
        base_url = "https://your-domain.atlassian.net"

        async with httpx.AsyncClient() as client:
            # 1) Generate (and yield) all Statuses
            async for status_chunk in self._generate_status_chunks(client, base_url):
                yield status_chunk

            # 2) Generate (and yield) all Projects
            async for project_chunk in self._generate_project_chunks(client, base_url):
                yield project_chunk

                # 3) Generate (and yield) all Issues for each Project
                async for issue_chunk in self._generate_issue_chunks(
                    client, base_url, project_chunk
                ):
                    yield issue_chunk

                    # 4) Generate (and yield) Comments for each Issue
                    async for comment_chunk in self._generate_comment_chunks(
                        client, base_url, issue_chunk
                    ):
                        yield comment_chunk
