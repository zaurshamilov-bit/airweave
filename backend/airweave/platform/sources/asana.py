"""Asana source implementation for syncing workspaces, projects, tasks, and comments."""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Asana",
    short_name="asana",
    auth_type=AuthType.oauth2_with_refresh,
    auth_config_class="AsanaAuthConfig",
    config_class="AsanaConfig",
    labels=["Project Management"],
)
class AsanaSource(BaseSource):
    """Asana source connector integrates with the Asana API to extract and synchronize data.

    Connects to your Asana workspaces.

    It supports syncing workspaces, projects, tasks, sections, comments, and file attachments.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "AsanaSource":
        """Create a new Asana source.

        Args:
            access_token: OAuth access token for Asana API
            config: Optional configuration parameters, like exclude_path

        Returns:
            Configured AsanaSource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        if config:
            instance.exclude_path = config.get("exclude_path", "")
        else:
            instance.exclude_path = ""

        return instance

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Asana API with token manager support.

        This method uses the token manager for authentication and handles
        401 errors by refreshing the token and retrying.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters including opt_fields
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry the request with the new token
                        self.logger.info(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Asana API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Asana API: {url}, {str(e)}")
            raise

    def _get_cursor_data(self) -> Dict[str, Any]:
        """Get cursor data from sync cursor.

        Returns:
            Cursor data dictionary, empty dict if no cursor exists
        """
        if hasattr(self, "cursor") and self.cursor:
            return getattr(self.cursor, "cursor_data", {})
        return {}

    def _update_cursor_data(self, timestamp: str):
        """Update cursor data with latest sync timestamp.

        Args:
            timestamp: ISO 8601 timestamp to store
        """
        if hasattr(self, "cursor") and self.cursor:
            self.cursor.cursor_data.update(
                {
                    "last_sync_timestamp": timestamp,
                    "source": "asana",
                }
            )
            self.logger.debug(f"Updated cursor data: {self.cursor.cursor_data}")

    async def _search_modified_tasks(
        self,
        client: httpx.AsyncClient,
        workspace_gid: str,
        modified_after: str,
        limit: int = 100,
    ) -> List[Dict]:
        """Search for tasks modified after a specific timestamp.

        Args:
            client: HTTP client
            workspace_gid: Workspace ID to search in
            modified_after: ISO 8601 timestamp
            limit: Number of results per page (max 100)

        Returns:
            List of task objects
        """
        search_url = f"https://app.asana.com/api/1.0/workspaces/{workspace_gid}/tasks/search"

        # Build search parameters
        params = {
            "modified_at.after": modified_after,
            "limit": limit,
            "opt_fields": (
                "gid,name,notes,html_notes,completed,completed_at,completed_by,"
                "created_at,modified_at,due_at,due_on,start_at,start_on,"
                "assignee,assignee_status,parent,projects,memberships,tags,"
                "workspace,num_likes,num_subtasks,liked,resource_subtype,"
                "is_rendered_as_separator,external,custom_fields,followers,"
                "dependencies,dependents,permalink_url"
            ),
            "sort_by": "modified_at",
            "sort_ascending": "true",
        }

        all_tasks = []

        # Manual pagination - search results are not stable
        # We sort by modified_at and keep fetching until we get all results
        last_modified_at = modified_after

        while True:
            # Update the search to exclude already seen tasks
            params["modified_at.after"] = last_modified_at

            # Get fresh token for each request
            access_token = await self.get_access_token()
            headers = {"Authorization": f"Bearer {access_token}"}

            response = await client.get(search_url, headers=headers, params=params)

            # Handle 402 Payment Required (non-premium workspace)
            if response.status_code == 402:
                self.logger.warning(
                    f"Workspace {workspace_gid} requires premium access for search. "
                    "Falling back to full sync for this workspace."
                )
                return []  # Return empty list to trigger fallback

            response.raise_for_status()
            data = response.json()

            tasks = data.get("data", [])
            if not tasks:
                break

            all_tasks.extend(tasks)

            # Update last_modified_at to the last task's modified_at for next page
            # This handles unstable pagination
            if tasks:
                last_task_modified = tasks[-1].get("modified_at")
                if last_task_modified and last_task_modified > last_modified_at:
                    last_modified_at = last_task_modified
                else:
                    # If we're not making progress, stop to avoid infinite loop
                    break

            # If we got less than the limit, we've reached the end
            if len(tasks) < limit:
                break

            self.logger.debug(f"Fetched {len(tasks)} tasks, total so far: {len(all_tasks)}")

        self.logger.info(f"Found {len(all_tasks)} modified tasks in workspace {workspace_gid}")
        return all_tasks

    async def _generate_workspace_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate workspace entities."""
        # Request all available fields for workspaces
        workspace_fields = ["gid", "name", "is_organization", "email_domains", "resource_type"]
        workspaces_data = await self._get_with_auth(
            client,
            "https://app.asana.com/api/1.0/workspaces",
            params={"opt_fields": ",".join(workspace_fields)},
        )

        for workspace in workspaces_data.get("data", []):
            yield AsanaWorkspaceEntity(
                entity_id=workspace["gid"],
                breadcrumbs=[],
                name=workspace["name"],
                asana_gid=workspace["gid"],
                is_organization=workspace.get("is_organization", False),
                email_domains=workspace.get("email_domains", []),
                permalink_url=f"https://app.asana.com/0/{workspace['gid']}",
            )

    async def _generate_project_entities(
        self, client: httpx.AsyncClient, workspace: Dict, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate project entities for a workspace."""
        # Request all available fields for projects, including timestamps
        project_fields = [
            "gid",
            "name",
            "color",
            "archived",
            "created_at",
            "modified_at",
            "current_status",
            "current_status.text",
            "current_status.color",
            "default_view",
            "due_on",
            "html_notes",
            "notes",
            "public",
            "start_on",
            "owner",
            "owner.name",
            "team",
            "team.name",
            "members",
            "members.name",
            "followers",
            "followers.name",
            "custom_fields",
            "custom_field_settings",
            "default_access_level",
            "icon",
            "permalink_url",
        ]
        projects_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/workspaces/{workspace['gid']}/projects",
            params={"opt_fields": ",".join(project_fields)},
        )

        for project in projects_data.get("data", []):
            project_name = project["name"]

            # Skip projects matching exclude_path
            if self.exclude_path and self.exclude_path in project_name:
                self.logger.info(f"Skipping excluded project: {project_name}")
                continue

            yield AsanaProjectEntity(
                entity_id=project["gid"],
                breadcrumbs=[workspace_breadcrumb],
                name=project["name"],
                workspace_gid=workspace["gid"],
                workspace_name=workspace["name"],
                color=project.get("color"),
                archived=project.get("archived", False),
                created_at=project.get("created_at"),
                current_status=project.get("current_status"),
                default_view=project.get("default_view"),
                due_date=project.get("due_on"),
                due_on=project.get("due_on"),
                html_notes=project.get("html_notes"),
                notes=project.get("notes"),
                is_public=project.get("public", False),
                start_on=project.get("start_on"),
                modified_at=project.get("modified_at"),
                owner=project.get("owner"),
                team=project.get("team"),
                members=project.get("members", []),
                followers=project.get("followers", []),
                custom_fields=project.get("custom_fields", []),
                custom_field_settings=project.get("custom_field_settings", []),
                default_access_level=project.get("default_access_level"),
                icon=project.get("icon"),
                permalink_url=project.get("permalink_url"),
            )

    async def _generate_section_entities(
        self, client: httpx.AsyncClient, project: Dict, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate section entities for a project."""
        # Request all available fields for sections
        section_fields = ["gid", "name", "created_at", "projects", "projects.name"]
        sections_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/projects/{project['gid']}/sections",
            params={"opt_fields": ",".join(section_fields)},
        )

        for section in sections_data.get("data", []):
            yield AsanaSectionEntity(
                entity_id=section["gid"],
                breadcrumbs=project_breadcrumbs,
                name=section["name"],
                project_gid=project["gid"],
                created_at=section.get("created_at"),
                projects=section.get("projects", []),
            )

    async def _generate_task_entities(
        self,
        client: httpx.AsyncClient,
        project: Dict,
        section: Optional[Dict] = None,
        breadcrumbs: List[Breadcrumb] = None,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate task entities for a project or section."""
        url = (
            f"https://app.asana.com/api/1.0/sections/{section['gid']}/tasks"
            if section
            else f"https://app.asana.com/api/1.0/projects/{project['gid']}/tasks"
        )

        # Request ALL available fields for tasks, especially timestamps
        task_fields = [
            "gid",
            "name",
            "actual_time_minutes",
            "approval_status",
            "assignee",
            "assignee.name",
            "assignee_status",
            "completed",
            "completed_at",
            "completed_by",
            "completed_by.name",
            "created_at",
            "modified_at",  # Important timestamps
            "dependencies",
            "dependents",
            "due_at",
            "due_on",
            "start_at",
            "start_on",  # All date/time fields
            "external",
            "html_notes",
            "notes",
            "is_rendered_as_separator",
            "liked",
            "memberships",
            "num_likes",
            "num_subtasks",
            "parent",
            "parent.name",
            "permalink_url",
            "resource_subtype",
            "tags",
            "tags.name",
            "custom_fields",
            "followers",
            "followers.name",
            "workspace",
            "workspace.name",
        ]

        tasks_data = await self._get_with_auth(
            client, url, params={"opt_fields": ",".join(task_fields)}
        )

        for task in tasks_data.get("data", []):
            # If we have a section, add it to the breadcrumbs
            task_breadcrumbs = breadcrumbs
            if section:
                section_breadcrumb = Breadcrumb(
                    entity_id=section["gid"], name=section["name"], type="section"
                )
                task_breadcrumbs = [*breadcrumbs, section_breadcrumb]

            yield AsanaTaskEntity(
                entity_id=task["gid"],
                breadcrumbs=task_breadcrumbs,
                name=task["name"],
                project_gid=project["gid"],
                section_gid=section["gid"] if section else None,
                actual_time_minutes=task.get("actual_time_minutes"),
                approval_status=task.get("approval_status"),
                assignee=task.get("assignee"),
                assignee_status=task.get("assignee_status"),
                completed=task.get("completed", False),
                completed_at=task.get("completed_at"),
                completed_by=task.get("completed_by"),
                created_at=task.get("created_at"),
                dependencies=task.get("dependencies", []),
                dependents=task.get("dependents", []),
                due_at=task.get("due_at"),
                due_on=task.get("due_on"),
                external=task.get("external"),
                html_notes=task.get("html_notes"),
                notes=task.get("notes"),
                is_rendered_as_separator=task.get("is_rendered_as_separator", False),
                liked=task.get("liked", False),
                memberships=task.get("memberships", []),
                modified_at=task.get("modified_at"),
                num_likes=task.get("num_likes", 0),
                num_subtasks=task.get("num_subtasks", 0),
                parent=task.get("parent"),
                permalink_url=task.get("permalink_url"),
                resource_subtype=task.get("resource_subtype", "default_task"),
                start_at=task.get("start_at"),
                start_on=task.get("start_on"),
                tags=task.get("tags", []),
                custom_fields=task.get("custom_fields", []),
                followers=task.get("followers", []),
                workspace=task.get("workspace"),
            )

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate comment entities for a task."""
        # Request all available fields for stories/comments
        story_fields = [
            "gid",
            "created_at",
            "created_by",
            "created_by.name",
            "resource_subtype",
            "text",
            "html_text",
            "is_pinned",
            "is_edited",
            "sticker_name",
            "num_likes",
            "liked",
            "type",
            "previews",
        ]
        stories_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/tasks/{task['gid']}/stories",
            params={"opt_fields": ",".join(story_fields)},
        )

        for story in stories_data.get("data", []):
            if story.get("resource_subtype") != "comment_added":
                continue

            yield AsanaCommentEntity(
                entity_id=story["gid"],
                breadcrumbs=task_breadcrumbs,
                task_gid=task["gid"],
                author=story["created_by"],
                created_at=story["created_at"],
                resource_subtype="comment_added",
                text=story.get("text"),
                html_text=story.get("html_text"),
                is_pinned=story.get("is_pinned", False),
                is_edited=story.get("is_edited", False),
                sticker_name=story.get("sticker_name"),
                num_likes=story.get("num_likes", 0),
                liked=story.get("liked", False),
                type=story.get("type", "comment"),
                previews=story.get("previews", []),
            )

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        task: Dict,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file attachment entities for a task."""
        # Request basic attachment list first
        attachment_list_fields = ["gid", "name", "resource_type"]
        attachments_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/tasks/{task['gid']}/attachments",
            params={"opt_fields": ",".join(attachment_list_fields)},
        )

        for attachment in attachments_data.get("data", []):
            # Request all available fields for individual attachment, including timestamps
            attachment_fields = [
                "gid",
                "name",
                "resource_type",
                "created_at",
                "modified_at",
                "download_url",
                "permanent",
                "host",
                "parent",
                "parent.name",
                "size",
                "view_url",
                "mime_type",
            ]
            attachment_response = await self._get_with_auth(
                client,
                f"https://app.asana.com/api/1.0/attachments/{attachment['gid']}",
                params={"opt_fields": ",".join(attachment_fields)},
            )

            attachment_detail = attachment_response.get("data")

            if (
                "download_url" not in attachment_detail
                or attachment_detail.get("download_url") is None
            ):
                self.logger.warning(
                    f"No download URL found for attachment {attachment['gid']} "
                    f"in task {task['gid']}"
                )
                continue

            # Create the file entity with metadata
            file_entity = AsanaFileEntity(
                entity_id=attachment_detail["gid"],
                breadcrumbs=task_breadcrumbs,
                file_id=attachment["gid"],
                name=attachment_detail.get("name"),
                mime_type=attachment_detail.get("mime_type"),
                size=attachment_detail.get("size"),
                total_size=attachment_detail.get("size"),  # Set total_size from API response
                download_url=attachment_detail.get("download_url"),
                created_at=attachment_detail.get("created_at"),
                modified_at=attachment_detail.get("modified_at"),
                task_gid=task["gid"],
                task_name=task["name"],
                resource_type=attachment_detail.get("resource_type"),
                host=attachment_detail.get("host"),
                parent=attachment_detail.get("parent"),
                view_url=attachment_detail.get("view_url"),
                permanent=attachment_detail.get("permanent", False),
            )

            # Different headers based on URL type
            headers = None
            if file_entity.download_url.startswith("https://app.asana.com/"):
                # Get fresh token for the download request
                token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {token}"}

            # Use the BaseSource helper method - it will use token manager automatically
            processed_entity = await self.process_file_entity(
                file_entity=file_entity,
                headers=headers,
                # No need to pass access_token - process_file_entity will get it from token manager
            )

            yield processed_entity

    async def _generate_task_entity_from_data(
        self,
        task_data: Dict,
        client: httpx.AsyncClient,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate a task entity from task data retrieved via search.

        This reconstructs the breadcrumbs and yields the task entity.
        Used for incremental sync where we get tasks directly from search.

        Args:
            task_data: Task data from Asana API
            client: HTTP client for additional API calls if needed
        """
        # Build breadcrumbs from task's project and workspace info
        breadcrumbs = []

        # Get workspace info from task
        workspace = task_data.get("workspace", {})
        if workspace:
            workspace_breadcrumb = Breadcrumb(
                entity_id=workspace.get("gid"),
                name=workspace.get("name", "Unknown Workspace"),
                type="workspace",
            )
            breadcrumbs.append(workspace_breadcrumb)

        # Get first project if exists (tasks can be in multiple projects)
        projects = task_data.get("projects", [])
        if projects and len(projects) > 0:
            project = projects[0]  # Use first project for breadcrumb
            project_breadcrumb = Breadcrumb(
                entity_id=project.get("gid"),
                name=project.get("name", "Unknown Project"),
                type="project",
            )
            breadcrumbs.append(project_breadcrumb)

        # Get section info if task has memberships
        section_gid = None
        memberships = task_data.get("memberships", [])
        for membership in memberships:
            section = membership.get("section")
            if section:
                section_gid = section.get("gid")
                section_breadcrumb = Breadcrumb(
                    entity_id=section_gid,
                    name=section.get("name", "Unknown Section"),
                    type="section",
                )
                # Only add section breadcrumb if we have a project
                if len(breadcrumbs) > 1:
                    breadcrumbs.append(section_breadcrumb)
                break

        # Create the task entity
        yield AsanaTaskEntity(
            entity_id=task_data["gid"],
            breadcrumbs=breadcrumbs,
            name=task_data.get("name", ""),
            project_gid=projects[0].get("gid") if projects else None,
            section_gid=section_gid,
            actual_time_minutes=task_data.get("actual_time_minutes"),
            approval_status=task_data.get("approval_status"),
            assignee=task_data.get("assignee"),
            assignee_status=task_data.get("assignee_status"),
            completed=task_data.get("completed", False),
            completed_at=task_data.get("completed_at"),
            completed_by=task_data.get("completed_by"),
            created_at=task_data.get("created_at"),
            dependencies=task_data.get("dependencies", []),
            dependents=task_data.get("dependents", []),
            due_at=task_data.get("due_at"),
            due_on=task_data.get("due_on"),
            external=task_data.get("external"),
            html_notes=task_data.get("html_notes"),
            notes=task_data.get("notes"),
            is_rendered_as_separator=task_data.get("is_rendered_as_separator", False),
            liked=task_data.get("liked", False),
            memberships=task_data.get("memberships", []),
            modified_at=task_data.get("modified_at"),
            num_likes=task_data.get("num_likes", 0),
            num_subtasks=task_data.get("num_subtasks", 0),
            parent=task_data.get("parent"),
            permalink_url=task_data.get("permalink_url"),
            resource_subtype=task_data.get("resource_subtype", "default_task"),
            start_at=task_data.get("start_at"),
            start_on=task_data.get("start_on"),
            tags=task_data.get("tags", []),
            custom_fields=task_data.get("custom_fields", []),
            followers=task_data.get("followers", []),
            workspace=task_data.get("workspace"),
        )

    async def _generate_entities_incremental(
        self,
        since_timestamp: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate only entities that changed since the given timestamp.

        For now, this only handles tasks as they support modified_at filtering.
        Other entities (projects, workspaces) will be synced in full mode only.

        Args:
            since_timestamp: ISO 8601 timestamp of last sync
        """
        # Record current timestamp at start of sync
        current_timestamp = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient() as client:
            # First, get all workspaces (we need these for context)
            workspaces_data = await self._get_with_auth(
                client, "https://app.asana.com/api/1.0/workspaces"
            )

            # For each workspace, search for modified tasks
            for workspace in workspaces_data.get("data", []):
                workspace_gid = workspace["gid"]
                workspace_name = workspace["name"]

                self.logger.info(
                    f"Searching for tasks modified after {since_timestamp} "
                    f"in workspace: {workspace_name}"
                )

                # Get modified tasks using search API
                modified_tasks = await self._search_modified_tasks(
                    client,
                    workspace_gid,
                    since_timestamp,
                )

                # If search failed (e.g., non-premium), we got empty list
                if not modified_tasks:
                    self.logger.warning(
                        f"No modified tasks found or search not available "
                        f"for workspace {workspace_name}"
                    )
                    continue

                # Process each modified task
                for task_data in modified_tasks:
                    # Skip tasks matching exclude_path
                    task_name = task_data.get("name", "")
                    if self.exclude_path and self.exclude_path in task_name:
                        self.logger.debug(f"Skipping excluded task: {task_name}")
                        continue

                    # Generate task entity
                    async for entity in self._generate_task_entity_from_data(task_data, client):
                        yield entity

                self.logger.info(
                    f"Processed {len(modified_tasks)} modified tasks "
                    f"from workspace {workspace_name}"
                )

            # Update cursor with current timestamp for next sync
            self._update_cursor_data(current_timestamp)
            self.logger.info(
                f"Incremental sync complete. New cursor timestamp: {current_timestamp}"
            )

    async def _generate_entities_full(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Asana (full sync).

        This is the original implementation moved to a separate method.
        """
        async with httpx.AsyncClient() as client:
            async for workspace_entity in self._generate_workspace_entities(client):
                yield workspace_entity

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_entity.asana_gid,
                    name=workspace_entity.name,
                    type="workspace",
                )

                async for project_entity in self._generate_project_entities(
                    client,
                    {"gid": workspace_entity.asana_gid, "name": workspace_entity.name},
                    workspace_breadcrumb,
                ):
                    yield project_entity

                    project_breadcrumb = Breadcrumb(
                        entity_id=project_entity.entity_id, name=project_entity.name, type="project"
                    )
                    project_breadcrumbs = [workspace_breadcrumb, project_breadcrumb]

                    async for section_entity in self._generate_section_entities(
                        client,
                        {"gid": project_entity.entity_id},
                        project_breadcrumbs,
                    ):
                        yield section_entity

                        # Generate tasks within section with full breadcrumb path
                        async for task_entity in self._generate_task_entities(
                            client,
                            {"gid": project_entity.entity_id},
                            {"gid": section_entity.entity_id, "name": section_entity.name},
                            project_breadcrumbs,
                        ):
                            yield task_entity

                            # Generate file attachments for the task
                            task_breadcrumb = Breadcrumb(
                                entity_id=task_entity.entity_id,
                                name=task_entity.name,
                                type="task",
                            )
                            task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                            async for file_entity in self._generate_file_entities(
                                client,
                                {
                                    "gid": task_entity.entity_id,
                                    "name": task_entity.name,
                                },
                                task_breadcrumbs,
                            ):
                                yield file_entity

                    # Generate tasks not in any section
                    async for task_entity in self._generate_task_entities(
                        client,
                        {"gid": project_entity.entity_id},
                        breadcrumbs=project_breadcrumbs,
                    ):
                        yield task_entity

                        # Generate file attachments for the task
                        task_breadcrumb = Breadcrumb(
                            entity_id=task_entity.entity_id,
                            name=task_entity.name,
                            type="task",
                        )
                        task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                        async for file_entity in self._generate_file_entities(
                            client,
                            {
                                "gid": task_entity.entity_id,
                                "name": task_entity.name,
                            },
                            task_breadcrumbs,
                        ):
                            yield file_entity

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities from Asana with incremental sync support.

        This method checks for cursor data to determine whether to perform:
        - Incremental sync: Only fetch tasks modified since last sync
        - Full sync: Fetch all entities (workspaces, projects, sections, tasks, files)
        """
        # Check for cursor data to determine sync type
        cursor_data = self._get_cursor_data()
        last_sync_timestamp = cursor_data.get("last_sync_timestamp")

        if last_sync_timestamp:
            # We have a previous sync timestamp, do incremental sync
            self.logger.info(f"Performing incremental sync since {last_sync_timestamp}")
            self.logger.info(
                "Note: Incremental sync only updates tasks. "
                "Projects, workspaces, and sections are not checked for updates."
            )

            async for entity in self._generate_entities_incremental(last_sync_timestamp):
                yield entity
        else:
            # No cursor data, do full sync
            self.logger.info("No previous sync found, performing full sync")

            # Record timestamp at start of full sync
            current_timestamp = datetime.now(timezone.utc).isoformat()

            # Perform full sync
            async for entity in self._generate_entities_full():
                yield entity

            # Update cursor after successful full sync
            self._update_cursor_data(current_timestamp)
            self.logger.info(f"Full sync complete. Stored cursor timestamp: {current_timestamp}")
