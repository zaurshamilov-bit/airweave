"""Asana source implementation."""
from typing import AsyncGenerator, Dict, List, Optional
from uuid import UUID

import httpx

from app import schemas
from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.asana import (
    AsanaCommentChunk,
    AsanaProjectChunk,
    AsanaSectionChunk,
    AsanaTaskChunk,
    AsanaWorkspaceChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Asana", "asana", AuthType.oauth2)
class AsanaSource(BaseSource):
    """Asana source implementation."""

    @classmethod
    async def create(cls, user: schemas.User, sync_id: UUID) -> "AsanaSource":
        """Create a new Asana source."""
        instance = cls()
        # fetch secrets from db
        instance.access_token = ""  # temp
        instance.sync_id = sync_id
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make authenticated GET request to Asana API."""
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        response.raise_for_status()
        return response.json()

    async def _generate_workspace_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate workspace chunks."""
        workspaces_data = await self._get_with_auth(
            client, "https://app.asana.com/api/1.0/workspaces"
        )

        for workspace in workspaces_data.get("data", []):
            yield AsanaWorkspaceChunk(
                source_name="asana",
                entity_id=workspace["gid"],
                sync_id=self.sync_id,
                breadcrumbs=[],
                name=workspace["name"],
                asana_gid=workspace["gid"],
                is_organization=workspace.get("is_organization", False),
                email_domains=workspace.get("email_domains", []),
                permalink_url=f"https://app.asana.com/0/{workspace['gid']}"
            )

    async def _generate_project_chunks(
        self, client: httpx.AsyncClient, workspace: Dict, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate project chunks for a workspace."""
        projects_data = await self._get_with_auth(
            client, f"https://app.asana.com/api/1.0/workspaces/{workspace['gid']}/projects"
        )

        for project in projects_data.get("data", []):
            yield AsanaProjectChunk(
                source_name="asana",
                entity_id=project["gid"],
                sync_id=self.sync_id,
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
                permalink_url=project.get("permalink_url")
            )

    async def _generate_section_chunks(
        self, client: httpx.AsyncClient, project: Dict, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate section chunks for a project."""
        sections_data = await self._get_with_auth(
            client, f"https://app.asana.com/api/1.0/projects/{project['gid']}/sections"
        )

        for section in sections_data.get("data", []):
            yield AsanaSectionChunk(
                source_name="asana",
                entity_id=section["gid"],
                sync_id=self.sync_id,
                breadcrumbs=project_breadcrumbs,
                name=section["name"],
                project_gid=project["gid"],
                created_at=section.get("created_at"),
                projects=section.get("projects", [])
            )

    async def _generate_task_chunks(
        self,
        client: httpx.AsyncClient,
        project: Dict,
        section: Optional[Dict] = None,
        breadcrumbs: List[Breadcrumb] = None
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate task chunks for a project or section."""
        url = (
            f"https://app.asana.com/api/1.0/sections/{section['gid']}/tasks"
            if section
            else f"https://app.asana.com/api/1.0/projects/{project['gid']}/tasks"
        )

        tasks_data = await self._get_with_auth(client, url)

        for task in tasks_data.get("data", []):
            # If we have a section, add it to the breadcrumbs
            task_breadcrumbs = breadcrumbs
            if section:
                section_breadcrumb = Breadcrumb(
                    entity_id=section["gid"],
                    name=section["name"],
                    type="section"
                )
                task_breadcrumbs = [*breadcrumbs, section_breadcrumb]

            yield AsanaTaskChunk(
                source_name="asana",
                entity_id=task["gid"],
                sync_id=self.sync_id,
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
                workspace=task.get("workspace")
            )

    async def _generate_comment_chunks(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseChunk, None]:
        """Generate comment chunks for a task."""
        stories_data = await self._get_with_auth(
            client, f"https://app.asana.com/api/1.0/tasks/{task['gid']}/stories"
        )

        for story in stories_data.get("data", []):
            if story.get("resource_subtype") != "comment_added":
                continue

            yield AsanaCommentChunk(
                source_name="asana",
                entity_id=story["gid"],
                sync_id=self.sync_id,
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
                previews=story.get("previews", [])
            )

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Asana."""
        async with httpx.AsyncClient() as client:
            async for workspace_chunk in self._generate_workspace_chunks(client):
                yield workspace_chunk

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_chunk.asana_gid,
                    name=workspace_chunk.name,
                    type="workspace"
                )

                async for project_chunk in self._generate_project_chunks(
                    client,
                    {"gid": workspace_chunk.asana_gid, "name": workspace_chunk.name},
                    workspace_breadcrumb
                ):
                    yield project_chunk

                    project_breadcrumb = Breadcrumb(
                        entity_id=project_chunk.entity_id,
                        name=project_chunk.name,
                        type="project"
                    )
                    project_breadcrumbs = [workspace_breadcrumb, project_breadcrumb]

                    async for section_chunk in self._generate_section_chunks(
                        client,
                        {"gid": project_chunk.entity_id},
                        project_breadcrumbs  # Pass full project breadcrumbs
                    ):
                        yield section_chunk

                        # Generate tasks within section with full breadcrumb path
                        async for task_chunk in self._generate_task_chunks(
                            client,
                            {"gid": project_chunk.entity_id},
                            {"gid": section_chunk.entity_id, "name": section_chunk.name},
                            project_breadcrumbs  # Pass project breadcrumbs, section will be added in _generate_task_chunks
                        ):
                            yield task_chunk

                    # Generate tasks not in any section
                    async for task_chunk in self._generate_task_chunks(
                        client,
                        {"gid": project_chunk.entity_id},
                        breadcrumbs=project_breadcrumbs
                    ):
                        yield task_chunk
