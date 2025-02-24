"""Jira entity schemas.

Based on the Jira Cloud REST API reference (read-only scope), we define
entity schemas for the major Jira objects relevant to our application:
 - Project
 - Issue
 - Comment

These schemas follow the patterns established by other integrations
(e.g., Asana, Todoist, HubSpot, Confluence). Each schema subclass extends
BaseEntity and includes relevant fields for that Jira entity.

Later iterations could include support for the following objects:
- Attachments
- Worklog entries
- Sprints/Boards (if using Agile)
- Custom fields
- Issue links
- Components
- Security levels
- Watchers
- Votes
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.platform.entities._base import BaseEntity


class JiraProjectEntity(BaseEntity):
    """Schema for a Jira Project.

    See:
      https://developer.atlassian.com/cloud/jira/platform/rest/v3/#api-rest-api-3-project-get
      (Project APIs in Jira Cloud)
    """

    project_key: str = Field(..., description="Unique key of the project (e.g., 'PROJ').")
    name: Optional[str] = Field(None, description="Name of the project.")
    project_type: Optional[str] = Field(
        None, description="Type of the project (e.g., 'software', 'service_desk')."
    )
    lead: Optional[Dict[str, Any]] = Field(
        None, description="Information about the project lead or owner."
    )
    description: Optional[str] = Field(None, description="Description of the project.")
    archived: bool = Field(False, description="Indicates if this project is archived.")


class JiraIssueEntity(BaseEntity):
    """Schema for a Jira Issue.

    See:
      https://developer.atlassian.com/cloud/jira/platform/rest/v3/#api-rest-api-3-issue-issueidorkey-get
      (Issue APIs in Jira Cloud)
    """

    issue_key: str = Field(..., description="Jira key for the issue (e.g. 'PROJ-123').")
    summary: Optional[str] = Field(None, description="Short summary field of the issue.")
    description: Optional[str] = Field(None, description="Detailed description of the issue.")
    status: Optional[str] = Field(None, description="Current workflow status of the issue.")
    priority: Optional[str] = Field(None, description="Priority level of the issue (e.g., 'High').")
    issue_type: Optional[str] = Field(
        None, description="Type of the issue (bug, task, story, etc.)."
    )
    assignee: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user/group assigned to this issue."
    )
    reporter: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user/group who created this issue."
    )
    resolution: Optional[str] = Field(
        None, description="Resolution text or code if the issue is resolved."
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the issue was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the issue was last updated."
    )
    resolved_at: Optional[datetime] = Field(
        None, description="Timestamp when the issue was resolved, if applicable."
    )
    labels: List[str] = Field([], description="List of labels associated with this issue.")
    watchers: List[Dict[str, Any]] = Field(
        [], description="List of watchers subscribed to this issue."
    )
    votes: Optional[int] = Field(None, description="Number of votes on the issue.")
    archived: bool = Field(False, description="Indicates if this issue has been archived.")


class JiraCommentEntity(BaseEntity):
    """Schema for a Jira Comment.

    See:
      https://developer.atlassian.com/cloud/jira/platform/rest/v3/#api-rest-api-3-issue-issueidorkey-comment-get
      (Comment APIs in Jira Cloud)
    """

    issue_key: str = Field(..., description="Key of the issue this comment belongs to.")
    body: Optional[str] = Field(None, description="Text/HTML body of the comment.")
    author: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who wrote this comment."
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when this comment was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when this comment was last updated."
    )
