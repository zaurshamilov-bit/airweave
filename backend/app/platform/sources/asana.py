"""Asana source implementation."""
from typing import AsyncGenerator, Dict

import httpx

from app import schemas
from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.asana import (
    AsanaCommentChunk,
    AsanaProjectChunk,
    AsanaTaskChunk,
    AsanaWorkspaceChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Asana", "asana", AuthType.oauth2)
class AsanaSource(BaseSource):
    """Asana source implementation."""

    @classmethod
    async def create(cls, user: schemas.User) -> "AsanaSource":
        """Create a new Asana source."""
        instance = cls()
        instance.access_token = "" # temp
        # self.access_token = await secrets_service.get_secret(user, "asana")
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to Asana API."""
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return response.json()

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Asana."""
        async with httpx.AsyncClient() as client:
            # Get all workspaces
            workspaces_data = await self._get_with_auth(
                client, "https://app.asana.com/api/1.0/workspaces"
            )

            for workspace in workspaces_data.get("data", []):
                workspace_breadcrumb = Breadcrumb(
                    id=workspace["gid"],
                    name=workspace["name"],
                    type="workspace"
                )

                # Workspace chunk
                yield AsanaWorkspaceChunk(
                    source_name="asana",
                    content=f"Workspace: {workspace['name']}",
                    breadcrumbs=[workspace_breadcrumb],
                    url=f"https://app.asana.com/0/{workspace['gid']}",
                    asana_gid=workspace["gid"],
                    name=workspace["name"],
                    is_organization=workspace.get("is_organization", False),
                    email_domains=workspace.get("email_domains", [])
                )

                # Get all projects in workspace
                projects_data = await self._get_with_auth(
                    client, f"https://app.asana.com/api/1.0/workspaces/{workspace['gid']}/projects"
                )

                for project in projects_data.get("data", []):
                    project_breadcrumb = Breadcrumb(
                        id=project["gid"],
                        name=project["name"],
                        type="project"
                    )

                    # Project chunk
                    yield AsanaProjectChunk(
                        source_name="asana",
                        content=f"Project: {project['name']}\nDescription: {project.get('notes', '')}",
                        breadcrumbs=[workspace_breadcrumb, project_breadcrumb],
                        url=f"https://app.asana.com/0/{project['gid']}",
                        asana_gid=project["gid"],
                        workspace_gid=workspace["gid"],
                        workspace_name=workspace["name"],
                        color=project.get("color"),
                        due_date=project.get("due_on"),
                        is_archived=project.get("archived", False),
                        owner=project.get("owner"),
                        team=project.get("team"),
                        custom_fields=project.get("custom_fields", [])
                    )

                    # Get all sections in project
                    sections_data = await self._get_with_auth(
                        client, f"https://app.asana.com/api/1.0/projects/{project['gid']}/sections"
                    )

                    for section in sections_data.get("data", []):
                        section_breadcrumb = Breadcrumb(
                            id=section["gid"],
                            name=section["name"],
                            type="section"
                        )

                        # Section chunk
                        yield BaseChunk(
                            source_name="asana",
                            content=f"Section: {section['name']}",
                            breadcrumbs=[workspace_breadcrumb, project_breadcrumb, section_breadcrumb],
                            url=f"https://app.asana.com/0/{project['gid']}#{section['gid']}",
                            asana_gid=section["gid"]
                        )

                        # Get all tasks in section
                        tasks_data = await self._get_with_auth(
                            client, f"https://app.asana.com/api/1.0/sections/{section['gid']}/tasks"
                        )

                        for task in tasks_data.get("data", []):
                            task_data = (await self._get_with_auth(
                                client, f"https://app.asana.com/api/1.0/tasks/{task['gid']}"
                            ))["data"]

                            task_breadcrumb = Breadcrumb(
                                id=task_data["gid"],
                                name=task_data["name"],
                                type="task"
                            )

                            # Task chunk
                            yield AsanaTaskChunk(
                                source_name="asana",
                                content=f"Task: {task_data['name']}\nDescription: {task_data.get('notes', '')}",
                                breadcrumbs=[workspace_breadcrumb, project_breadcrumb, section_breadcrumb, task_breadcrumb],
                                url=f"https://app.asana.com/0/{project['gid']}/{task_data['gid']}",
                                asana_gid=task_data["gid"],
                                project_gid=project["gid"],
                                section_gid=section["gid"],
                                assignee=task_data.get("assignee"),
                                due_date=task_data.get("due_on"),
                                completed=task_data.get("completed", False),
                                tags=task_data.get("tags", []),
                                custom_fields=task_data.get("custom_fields", [])
                            )

                            # Get all comments for task
                            stories_data = await self._get_with_auth(
                                client, f"https://app.asana.com/api/1.0/tasks/{task_data['gid']}/stories"
                            )

                            for story in stories_data.get("data", []):
                                if story["resource_subtype"] == "comment_added":
                                    # Comment chunk
                                    yield AsanaCommentChunk(
                                        source_name="asana",
                                        content=f"Comment by {story['created_by']['name']}: {story['text']}",
                                        breadcrumbs=[workspace_breadcrumb, project_breadcrumb, section_breadcrumb, task_breadcrumb],
                                        url=f"https://app.asana.com/0/{project['gid']}/{task_data['gid']}",
                                        task_gid=task_data["gid"],
                                        author=story["created_by"],
                                        created_at=story["created_at"],
                                        is_pinned=story.get("is_pinned", False)
                                    )
