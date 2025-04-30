"""Linear source implementation."""

import asyncio
import re
from typing import AsyncGenerator, Dict, List, Union
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.linear import (
    LinearAttachmentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from airweave.platform.sources._base import BaseSource


@source("Linear", "linear", AuthType.oauth2, labels=["Project Management"])
class LinearSource(BaseSource):
    """Linear source implementation."""

    # Add rate limiting constants
    REQUESTS_PER_HOUR = 1200  # For OAuth vs 1500 for API keys
    REQUESTS_PER_SECOND = REQUESTS_PER_HOUR / 3600  # ~0.33 requests/second
    RATE_LIMIT_PERIOD = 1.0
    MAX_RETRIES = 3

    def __init__(self):
        """Initialize the LinearSource instance with rate limiting state."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
        }

    @classmethod
    async def create(cls, access_token: str) -> "LinearSource":
        """Create instance of the Linear source."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _wait_for_rate_limit(self):
        """Implement adaptive rate limiting for Linear API requests."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()

            # Track hourly request count
            hour_ago = current_time - 3600
            self._request_times = [t for t in self._request_times if t > hour_ago]
            hourly_count = len(self._request_times)

            # Adaptive throttling based on usage
            if hourly_count < 600:  # First half of quota - no throttling
                wait_time = 0
            elif hourly_count < 900:  # 50-75% of quota - light throttling
                wait_time = 1.0
            elif hourly_count < 1000:  # 75-83% of quota - medium throttling
                wait_time = 2.0
            else:  # >83% of quota - heavy throttling
                wait_time = 3.0

            # Apply throttling if needed
            if wait_time > 0 and self._request_times:
                last_request = max(self._request_times)
                sleep_time = last_request + wait_time - current_time
                if sleep_time > 0:
                    logger.debug(
                        f"Rate limit throttling ({hourly_count}/1200 requests). "
                        f"Waiting {sleep_time:.2f}s"
                    )
                    self._stats["rate_limit_waits"] += 1
                    await asyncio.sleep(sleep_time)

            # Record this request
            self._request_times.append(current_time)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post_with_auth(self, client: httpx.AsyncClient, query: str) -> Dict:
        await self._wait_for_rate_limit()
        self._stats["api_calls"] += 1

        try:
            response = await client.post(
                "https://api.linear.app/graphql",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
                json={"query": query},
            )
            response.raise_for_status()

            # Check for rate limit headers
            if "X-RateLimit-Requests-Remaining" in response.headers:
                remaining = int(response.headers.get("X-RateLimit-Requests-Remaining", "0"))
                logger.debug(f"Rate limit remaining: {remaining}")

            return response.json()
        except httpx.HTTPStatusError as e:
            # Log more details about the error
            error_content = None
            try:
                error_content = e.response.json()
                logger.error(f"GraphQL API error: {error_content}")
            except Exception:
                logger.error(f"HTTP Error content: {e.response.text}")
            raise

    async def _generate_attachments_for_issue(
        self,
        client: httpx.AsyncClient,
        issue_id: str,
        issue_identifier: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Union[LinearAttachmentEntity, None], None]:
        """Generate attachment entities for a specific issue."""
        query = f"""
        {{
          issue(id: "{issue_id}") {{
            id
            title
            identifier
            attachments {{
              nodes {{
                id
                title
                subtitle
                url
                metadata
                source
                createdAt
                updatedAt
              }}
            }}
          }}
        }}
        """

        response = await self._post_with_auth(client, query)

        # Add debug logging with issue title
        issue_data = response.get("data", {}).get("issue", {})
        issue_title = issue_data.get("title", "Unknown title")
        logger.info(f"Processing attachments for issue {issue_identifier} - '{issue_title}'")

        attachments_data = issue_data.get("attachments", {})
        attachments = attachments_data.get("nodes", [])

        logger.info(
            f"Found {len(attachments)} attachments for issue {issue_identifier} - '{issue_title}'"
        )

        for attachment in attachments:
            # Skip attachments without a URL
            if not attachment.get("url"):
                logger.warning(f"Attachment {attachment.get('id')} has no URL, skipping")
                continue

            # Create file name from title or generate a default one
            file_name = attachment.get("title") or f"Attachment-{attachment.get('id')}"

            # Create the attachment entity
            attachment_entity = LinearAttachmentEntity(
                entity_id=attachment.get("id"),
                file_id=attachment.get("id"),
                breadcrumbs=breadcrumbs.copy(),
                # FileEntity required fields
                name=file_name,
                download_url=attachment.get("url"),
                # LinearAttachmentEntity specific fields
                issue_id=issue_id,
                issue_identifier=issue_identifier,
                title=attachment.get("title"),
                subtitle=attachment.get("subtitle"),
                source=attachment.get("source"),
                created_at=attachment.get("createdAt"),
                updated_at=attachment.get("updatedAt"),
                metadata=attachment.get("metadata"),
            )

            # Only include attachments that have a URL we can download
            try:
                # Process the file using the BaseSource helper method
                processed_entity = await self.process_file_entity(
                    file_entity=attachment_entity,
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                yield processed_entity

            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('id')}: {str(e)}")

    async def _generate_attachment_entities_from_description(
        self,
        client: httpx.AsyncClient,
        issue_id: str,
        issue_identifier: str,
        issue_description: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Union[LinearAttachmentEntity, None], None]:
        """Generate attachment entities from markdown links in issue descriptions."""
        if not issue_description:
            return

        # Regular expression to find markdown links [filename](url)
        # Captures filename and URL as groups
        markdown_link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

        # Find all matches in the description
        matches = re.findall(markdown_link_pattern, issue_description)

        logger.info(
            f"Found {len(matches)} potential attachments in description "
            f"for issue {issue_identifier}"
        )

        for file_name, url in matches:
            # Only process Linear upload URLs
            if "uploads.linear.app" in url:
                logger.info(f"Processing attachment from description: {file_name} - URL: {url}")

                # Generate a unique ID for this attachment
                attachment_id = str(uuid4())

                # Create the attachment entity
                attachment_entity = LinearAttachmentEntity(
                    entity_id=attachment_id,
                    file_id=attachment_id,
                    breadcrumbs=breadcrumbs.copy(),
                    # FileEntity required fields
                    name=file_name,
                    download_url=url,
                    # LinearAttachmentEntity specific fields
                    issue_id=issue_id,
                    issue_identifier=issue_identifier,
                    title=file_name,
                    subtitle="Extracted from issue description",
                    source={"type": "description_link"},
                    created_at=None,  # We don't know when it was added to the description
                    updated_at=None,
                    metadata={"extracted_from": "description"},
                )

                # Process the file using the BaseSource helper method
                try:
                    processed_entity = await self.process_file_entity(
                        file_entity=attachment_entity,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )

                    yield processed_entity

                except Exception as e:
                    logger.error(
                        f"Error processing attachment {attachment_id} from description: {str(e)}"
                    )

    async def _generate_issue_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Union[LinearIssueEntity, LinearAttachmentEntity], None]:
        """Generate entities for all issues in the workspace.

        Also extracts attachments from issue descriptions.
        """
        has_next_page = True
        cursor = None

        while has_next_page:
            # Build pagination parameters
            pagination = "first: 50"
            if cursor:
                pagination += f', after: "{cursor}"'

            # Query for issues
            query = f"""
            {{
              issues({pagination}) {{
                nodes {{
                  id
                  identifier
                  title
                  description
                  priority
                  completedAt
                  createdAt
                  updatedAt
                  dueDate
                  state {{
                    name
                  }}
                  team {{
                    id
                    name
                  }}
                  project {{
                    id
                    name
                  }}
                  assignee {{
                    name
                  }}
                }}
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
              }}
            }}
            """

            response = await self._post_with_auth(client, query)

            # Extract data from response
            issues_data = response.get("data", {}).get("issues", {})
            issues = issues_data.get("nodes", [])

            # Process each issue
            for issue in issues:
                issue_identifier = issue.get("identifier")
                issue_title = issue.get("title")
                issue_description = issue.get("description", "")

                logger.info(f"Processing issue: {issue_identifier} - '{issue_title}'")

                # Build breadcrumbs list
                breadcrumbs = []

                # Add team breadcrumb if available
                team_id = None
                team_name = None
                if issue.get("team"):
                    team_id = issue["team"].get("id")
                    team_name = issue["team"].get("name")
                    team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                    breadcrumbs.append(team_breadcrumb)

                # Add project breadcrumb if available
                project_id = None
                project_name = None
                if issue.get("project"):
                    project_id = issue["project"].get("id")
                    project_name = issue["project"].get("name")
                    project_breadcrumb = Breadcrumb(
                        entity_id=project_id, name=project_name, type="project"
                    )
                    breadcrumbs.append(project_breadcrumb)

                # Create issue URL
                issue_url = f"https://linear.app/issue/{issue.get('identifier')}"
                issue_id = issue.get("id")

                # Create and yield LinearIssueEntity for each issue
                issue_entity = LinearIssueEntity(
                    entity_id=issue_id,
                    title=issue.get("title", ""),
                    breadcrumbs=breadcrumbs,
                    url=issue_url,
                    # LinearIssueEntity specific fields
                    identifier=issue_identifier,
                    description=issue_description,
                    priority=issue.get("priority"),
                    state=issue.get("state", {}).get("name"),
                    team_id=team_id,
                    team_name=team_name,
                    project_id=project_id,
                    project_name=project_name,
                    assignee=issue.get("assignee", {}).get("name")
                    if issue.get("assignee")
                    else None,
                    created_at=issue.get("createdAt"),
                    updated_at=issue.get("updatedAt"),
                    completed_at=issue.get("completedAt"),
                    due_date=issue.get("dueDate"),
                )

                # First yield the issue entity
                yield issue_entity

                # Create issue breadcrumb for attachments
                issue_breadcrumb = Breadcrumb(
                    entity_id=issue_entity.entity_id, name=issue_entity.title, type="issue"
                )

                # Combine existing breadcrumbs with issue breadcrumb
                issue_breadcrumbs = breadcrumbs + [issue_breadcrumb]

                # Extract attachments from description
                if issue_description:
                    async for attachment in self._generate_attachment_entities_from_description(
                        client, issue_id, issue_identifier, issue_description, issue_breadcrumbs
                    ):
                        if attachment:  # Only yield non-None attachments
                            yield attachment

            # Update pagination info for next iteration
            page_info = issues_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearProjectEntity, None]:
        """Generate entities for all projects in the workspace."""
        has_next_page = True
        cursor = None

        while has_next_page:
            # Build pagination parameters
            pagination = "first: 50"
            if cursor:
                pagination += f', after: "{cursor}"'

            # Query for projects
            query = f"""
            {{
              projects({pagination}) {{
                nodes {{
                  id
                  name
                  slugId
                  description
                  priority
                  startDate
                  targetDate
                  state
                  createdAt
                  updatedAt
                  completedAt
                  startedAt
                  progress
                  teams {{
                    nodes {{
                      id
                      name
                    }}
                  }}
                  lead {{
                    name
                  }}
                }}
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
              }}
            }}
            """

            response = await self._post_with_auth(client, query)

            # Extract data from response
            projects_data = response.get("data", {}).get("projects", {})
            projects = projects_data.get("nodes", [])

            logger.info(f"Found {len(projects)} projects")

            # Process each project
            for project in projects:
                project_id = project.get("id")
                project_name = project.get("name")

                logger.info(f"Processing project: {project_name}")

                # Extract team data
                team_ids = []
                team_names = []
                teams = project.get("teams", {}).get("nodes", [])

                for team in teams:
                    team_ids.append(team.get("id"))
                    team_names.append(team.get("name"))

                # Build breadcrumbs list
                breadcrumbs = []

                # Add team breadcrumbs if available
                for i, team_id in enumerate(team_ids):
                    team_name = team_names[i]
                    team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                    breadcrumbs.append(team_breadcrumb)

                # Create project URL
                project_url = f"https://linear.app/project/{project.get('slugId')}"

                # Create and yield LinearProjectEntity for each project
                yield LinearProjectEntity(
                    entity_id=project_id,
                    name=project.get("name", ""),
                    breadcrumbs=breadcrumbs,
                    url=project_url,
                    # LinearProjectEntity specific fields
                    slug_id=project.get("slugId"),
                    description=project.get("description"),
                    priority=project.get("priority"),
                    state=project.get("state"),
                    team_ids=team_ids if team_ids else None,
                    team_names=team_names if team_names else None,
                    created_at=project.get("createdAt"),
                    updated_at=project.get("updatedAt"),
                    completed_at=project.get("completedAt"),
                    started_at=project.get("startedAt"),
                    target_date=project.get("targetDate"),
                    start_date=project.get("startDate"),
                    progress=project.get("progress"),
                    lead=project.get("lead", {}).get("name") if project.get("lead") else None,
                )

            # Update pagination info for next iteration
            page_info = projects_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

    async def _generate_team_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearTeamEntity, None]:
        """Generate entities for all teams in the workspace."""
        has_next_page = True
        cursor = None

        try:
            while has_next_page:
                # Build pagination parameters
                pagination = "first: 50"
                if cursor:
                    pagination += f', after: "{cursor}"'

                # Query for teams
                query = f"""
                {{
                  teams({pagination}) {{
                    nodes {{
                      id
                      name
                      key
                      description
                      color
                      icon
                      private
                      timezone
                      createdAt
                      updatedAt
                      parent {{
                        id
                        name
                      }}
                      issueCount
                    }}
                    pageInfo {{
                      hasNextPage
                      endCursor
                    }}
                  }}
                }}
                """

                logger.info(f"Sending team query with pagination: {pagination}")

                try:
                    response = await self._post_with_auth(client, query)

                    # Debug: Log raw response to see any errors
                    if "errors" in response:
                        logger.error(f"GraphQL errors in team query: {response['errors']}")
                        return

                    # Extract data from response
                    teams_data = response.get("data", {}).get("teams", {})
                    teams = teams_data.get("nodes", [])

                    logger.info(f"Found {len(teams)} teams")

                    # Process each team
                    for team in teams:
                        team_id = team.get("id")
                        team_name = team.get("name")
                        team_key = team.get("key")
                        team_description = team.get("description", "")
                        team_color = team.get("color", "")
                        team_icon = team.get("icon", "")
                        team_private = team.get("private", False)
                        team_timezone = team.get("timezone", "")
                        team_created_at = team.get("createdAt", "")
                        team_updated_at = team.get("updatedAt", "")
                        parent = team.get("parent")
                        team_parent_id = parent.get("id", "") if parent else ""
                        team_parent_name = parent.get("name", "") if parent else ""
                        team_issue_count = team.get("issueCount", 0)

                        logger.info(f"Processing team: {team_name} ({team_key})")

                        # Build breadcrumbs list
                        breadcrumbs = []

                        # Add team breadcrumbs if available
                        team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                        breadcrumbs.append(team_breadcrumb)

                        # Create team URL
                        team_url = f"https://linear.app/team/{team.get('key')}"

                        # Create and yield LinearTeamEntity for each team
                        yield LinearTeamEntity(
                            entity_id=team_id,
                            name=team_name,
                            breadcrumbs=breadcrumbs,
                            url=team_url,
                            # LinearTeamEntity specific fields
                            key=team_key,
                            description=team_description,
                            color=team_color,
                            icon=team_icon,
                            private=team_private,
                            timezone=team_timezone,
                            created_at=team_created_at,
                            updated_at=team_updated_at,
                            parent_id=team_parent_id,
                            parent_name=team_parent_name,
                            issue_count=team_issue_count,
                        )

                    # Update pagination info for next iteration
                    page_info = teams_data.get("pageInfo", {})
                    has_next_page = page_info.get("hasNextPage", False)
                    cursor = page_info.get("endCursor")

                except Exception as e:
                    logger.error(f"Error in team query: {str(e)}")
                    raise

        except Exception as e:
            logger.error(f"Error in team entity generation: {str(e)}")
            # Try to continue with other entity types
            return

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearUserEntity, None]:
        """Generate entities for all users in the workspace."""
        has_next_page = True
        cursor = None

        while has_next_page:
            # Build pagination parameters
            pagination = "first: 50"
            if cursor:
                pagination += f', after: "{cursor}"'

            # Query for users with their team memberships
            query = f"""
            {{
              users({pagination}) {{
                nodes {{
                  id
                  name
                  displayName
                  email
                  avatarUrl
                  description
                  timezone
                  active
                  admin
                  guest
                  lastSeen
                  statusEmoji
                  statusLabel
                  statusUntilAt
                  createdIssueCount
                  createdAt
                  updatedAt
                  teams {{
                    nodes {{
                      id
                      name
                      key
                    }}
                  }}
                }}
                pageInfo {{
                  hasNextPage
                  endCursor
                }}
              }}
            }}
            """

            response = await self._post_with_auth(client, query)

            # Extract data from response
            users_data = response.get("data", {}).get("users", {})
            users = users_data.get("nodes", [])

            logger.info(f"Found {len(users)} users")

            # Process each user
            for user in users:
                user_id = user.get("id")
                user_name = user.get("name")
                display_name = user.get("displayName")

                logger.info(f"Processing user: {user_name} ({display_name})")

                # Extract team data
                team_ids = []
                team_names = []
                teams = user.get("teams", {}).get("nodes", [])

                for team in teams:
                    team_ids.append(team.get("id"))
                    team_names.append(team.get("name"))

                # Build breadcrumbs list
                breadcrumbs = []

                # Add team breadcrumbs
                for i, team_id in enumerate(team_ids):
                    team_name = team_names[i]
                    team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                    breadcrumbs.append(team_breadcrumb)

                # Create user URL
                user_url = f"https://linear.app/u/{user.get('id')}"

                # Create and yield LinearUserEntity for each user
                yield LinearUserEntity(
                    entity_id=user_id,
                    name=user_name,
                    breadcrumbs=breadcrumbs,
                    url=user_url,
                    # LinearUserEntity specific fields
                    display_name=display_name,
                    email=user.get("email"),
                    avatar_url=user.get("avatarUrl"),
                    description=user.get("description"),
                    timezone=user.get("timezone"),
                    active=user.get("active"),
                    admin=user.get("admin"),
                    guest=user.get("guest"),
                    last_seen=user.get("lastSeen"),
                    status_emoji=user.get("statusEmoji"),
                    status_label=user.get("statusLabel"),
                    status_until_at=user.get("statusUntilAt"),
                    created_issue_count=user.get("createdIssueCount"),
                    team_ids=team_ids if team_ids else None,
                    team_names=team_names if team_names else None,
                    created_at=user.get("createdAt"),
                    updated_at=user.get("updatedAt"),
                )

            # Update pagination info for next iteration
            page_info = users_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

    async def generate_entities(
        self,
    ) -> AsyncGenerator[
        Union[
            LinearTeamEntity,
            LinearProjectEntity,
            LinearUserEntity,
            LinearIssueEntity,
            LinearAttachmentEntity,
        ],
        None,
    ]:
        """Main entry point to generate all entities from Linear."""
        async with httpx.AsyncClient() as client:
            # Re-enable teams with proper error handling
            try:
                logger.info("Starting team entity generation")
                async for team_entity in self._generate_team_entities(client):
                    yield team_entity
            except Exception as e:
                logger.error(f"Failed to generate team entities: {str(e)}")
                logger.info("Continuing with other entity types")

            # Next, collect all projects
            try:
                logger.info("Starting project entity generation")
                async for project_entity in self._generate_project_entities(client):
                    yield project_entity
            except Exception as e:
                logger.error(f"Failed to generate project entities: {str(e)}")

            # Then, collect all users
            try:
                logger.info("Starting user entity generation")
                async for user_entity in self._generate_user_entities(client):
                    yield user_entity
            except Exception as e:
                logger.error(f"Failed to generate user entities: {str(e)}")

            # Finally, collect all issues and description-based attachments
            try:
                logger.info("Starting issue and attachment entity generation")
                async for entity in self._generate_issue_entities(client):
                    yield entity
            except Exception as e:
                logger.error(f"Failed to generate issue/attachment entities: {str(e)}")
