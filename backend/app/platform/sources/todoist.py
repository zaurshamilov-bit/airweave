"""Todoist source implementation."""

from typing import AsyncGenerator, Dict, List, Optional

import httpx

from app.platform.auth.schemas import AuthType
from app.platform.chunks._base import BaseChunk, Breadcrumb
from app.platform.chunks.todoist import (
    TodoistCommentChunk,
    TodoistProjectChunk,
    TodoistSectionChunk,
    TodoistTaskChunk,
)
from app.platform.decorators import source
from app.platform.sources._base import BaseSource


@source("Todoist", "todoist", AuthType.oauth2)
class TodoistSource(BaseSource):
    """Todoist source implementation.

    This connector retrieves hierarchical data from the Todoist REST API:
    - Projects
    - Sections (within each project)
    - Tasks (within each project, optionally nested under a section)
    - Comments (within each task)

    The Todoist chunk schemas are defined in chunks/todoist.py.
    """

    @classmethod
    async def create(cls, access_token: str) -> "TodoistSource":
        """Create a new Todoist source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Optional[dict]:
        """Make an authenticated GET request to the Todoist REST API using the provided URL.

        Returns the JSON response as a dict (or list if not JSON-object).
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await client.get(url, headers=headers)
        response.raise_for_status()

        # Depending on the endpoint, responses may be a list or a dict.
        # We'll attempt to parse JSON and return whatever type we get:
        try:
            return response.json()
        except ValueError:
            return None

    async def _generate_project_chunks(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[TodoistProjectChunk, None]:
        """Retrieve and yield Project chunks.

        GET https://api.todoist.com/rest/v2/projects
        """
        url = "https://api.todoist.com/rest/v2/projects"
        projects = await self._get_with_auth(client, url)
        if not projects:
            return

        # 'projects' should be a list of project objects
        for project in projects:
            yield TodoistProjectChunk(
                source_name="todoist",
                entity_id=project["id"],
                name=project["name"],
                color=project.get("color"),
                comment_count=project.get("comment_count", 0),
                order=project.get("order", 0),
                is_shared=project.get("is_shared", False),
                is_favorite=project.get("is_favorite", False),
                is_inbox_project=project.get("is_inbox_project", False),
                is_team_inbox=project.get("is_team_inbox", False),
                view_style=project.get("view_style"),
                url=project.get("url"),
                parent_id=project.get("parent_id"),
            )

    async def _generate_section_chunks(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        project_name: str,
        project_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TodoistSectionChunk, None]:
        """Retrieve and yield Section chunks for a given project.

        GET https://api.todoist.com/rest/v2/projects/{project_id}/sections
        """
        url = f"https://api.todoist.com/rest/v2/projects/{project_id}/sections"
        sections = await self._get_with_auth(client, url)
        if not sections:
            return

        for section in sections:
            yield TodoistSectionChunk(
                source_name="todoist",
                entity_id=section["id"],
                breadcrumbs=[project_breadcrumb],
                name=section["name"],
                project_id=section["project_id"],
                order=section.get("order", 0),
            )

    async def _fetch_all_tasks_for_project(
        self, client: httpx.AsyncClient, project_id: str
    ) -> List[Dict]:
        """Fetch all tasks for a given project.

        GET https://api.todoist.com/rest/v2/tasks?project_id={project_id}

        Returns a list of task objects.
        """
        url = f"https://api.todoist.com/rest/v2/tasks?project_id={project_id}"
        tasks = await self._get_with_auth(client, url)
        return tasks if isinstance(tasks, list) else []

    async def _generate_task_chunks(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        section_id: Optional[str],
        all_tasks: List[Dict],
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistTaskChunk, None]:
        """Retrieve and yield Task chunks.

        Yield task chunks for either
          - tasks that belong to a given section, if section_id is provided
          - tasks that have no section, if section_id is None

        We assume 'all_tasks' is the full list of tasks for the project.
        """
        for task in all_tasks:
            # Determine if this task matches the requested (section_id or None).
            if section_id is None:
                # We yield tasks that have no section (section_id=None).
                if task.get("section_id") is not None:
                    continue
            else:
                # We yield tasks that match the provided section_id.
                if task.get("section_id") != section_id:
                    continue

            yield TodoistTaskChunk(
                source_name="todoist",
                entity_id=task["id"],
                breadcrumbs=breadcrumbs,
                content=task["content"],
                description=task.get("description"),
                comment_count=task.get("comment_count", 0),
                is_completed=task.get("is_completed", False),
                labels=task.get("labels", []),
                order=task.get("order", 0),
                priority=task.get("priority", 1),
                project_id=task.get("project_id"),
                section_id=task.get("section_id"),
                parent_id=task.get("parent_id"),
                creator_id=task.get("creator_id"),
                created_at=task.get("created_at"),
                due_date=(task["due"]["date"] if task.get("due") else None),
                due_datetime=(
                    task["due"]["datetime"]
                    if (task.get("due") and task["due"].get("datetime"))
                    else None
                ),
                due_string=(task["due"]["string"] if task.get("due") else None),
                due_is_recurring=(task["due"]["is_recurring"] if task.get("due") else False),
                due_timezone=(task["due"]["timezone"] if task.get("due") else None),
                url=task.get("url"),
            )

    async def _generate_comment_chunks(
        self,
        client: httpx.AsyncClient,
        task_chunk: TodoistTaskChunk,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistCommentChunk, None]:
        """Retrieve and yield Comment chunks for a given task.

        GET https://api.todoist.com/rest/v2/comments?task_id={task_id}
        """
        task_id = task_chunk.entity_id
        url = f"https://api.todoist.com/rest/v2/comments?task_id={task_id}"
        comments = await self._get_with_auth(client, url)
        if not isinstance(comments, list):
            return

        for comment in comments:
            yield TodoistCommentChunk(
                source_name="todoist",
                entity_id=comment["id"],
                breadcrumbs=task_breadcrumbs,
                task_id=str(comment.get("task_id") or ""),
                content=comment.get("content"),
                posted_at=comment["posted_at"],
            )

    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate all chunks from Todoist: Projects, Sections, Tasks, and Comments.

        For each project:
          - yield a TodoistProjectChunk
          - yield TodoistSectionChunks
          - fetch all tasks for that project once
          - yield tasks that fall under each section
          - yield tasks not associated with any section
          - yield TodoistCommentChunks for each task
        """
        async with httpx.AsyncClient() as client:
            # 1) Generate (and yield) all Projects
            async for project_chunk in self._generate_project_chunks(client):
                yield project_chunk

                # Create a breadcrumb for this project
                project_breadcrumb = Breadcrumb(
                    entity_id=project_chunk.entity_id,
                    name=project_chunk.name,
                    type="project",
                )

                # 2) Generate (and yield) all Sections for this project
                async for section_chunk in self._generate_section_chunks(
                    client,
                    project_chunk.entity_id,
                    project_chunk.name,
                    project_breadcrumb,
                ):
                    yield section_chunk

                # Prepare to retrieve tasks for this project,
                # so we only make one request per project.
                all_tasks = await self._fetch_all_tasks_for_project(client, project_chunk.entity_id)

                # Re-fetch sections in-memory to attach tasks to them,
                # or reuse the info from above if desired
                url_sections = (
                    f"https://api.todoist.com/rest/v2/projects/{project_chunk.entity_id}/sections"
                )
                sections_data = await self._get_with_auth(client, url_sections)
                sections = sections_data if isinstance(sections_data, list) else []

                # 3) For each section, yield tasks that belong to it, plus comments
                for section_data in sections:
                    section_breadcrumb = Breadcrumb(
                        entity_id=section_data["id"],
                        name=section_data["name"],
                        type="section",
                    )
                    project_section_breadcrumbs = [project_breadcrumb, section_breadcrumb]

                    async for task_chunk in self._generate_task_chunks(
                        client,
                        project_chunk.entity_id,
                        section_data["id"],
                        all_tasks,
                        project_section_breadcrumbs,
                    ):
                        yield task_chunk
                        # generate comments for each task
                        task_breadcrumb = Breadcrumb(
                            entity_id=task_chunk.entity_id,
                            name=task_chunk.content,
                            type="task",
                        )
                        async for comment_chunk in self._generate_comment_chunks(
                            client,
                            task_chunk,
                            project_section_breadcrumbs + [task_breadcrumb],
                        ):
                            yield comment_chunk

                # 4) Generate tasks for this project that are NOT in any section
                async for task_chunk in self._generate_task_chunks(
                    client,
                    project_chunk.entity_id,
                    section_id=None,
                    all_tasks=all_tasks,
                    breadcrumbs=[project_breadcrumb],
                ):
                    yield task_chunk
                    # generate comments for each of these tasks as well
                    task_breadcrumb = Breadcrumb(
                        entity_id=task_chunk.entity_id,
                        name=task_chunk.content,
                        type="task",
                    )
                    async for comment_chunk in self._generate_comment_chunks(
                        client,
                        task_chunk,
                        [project_breadcrumb, task_breadcrumb],
                    ):
                        yield comment_chunk
