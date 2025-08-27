"""GitHub entity schemas.

Based on the GitHub REST API (read-only scope), we define entity schemas for:
  • Repository
  • Repository Contents

References:
  • https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28 (Repositories)
  • https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28 (Repository contents)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, CodeFileEntity, ParentEntity


class GitHubRepositoryEntity(ParentEntity):
    """Schema for GitHub repository entity."""

    name: str = AirweaveField(..., description="Repository name", embeddable=True)
    full_name: str = AirweaveField(
        ..., description="Full repository name including owner", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Repository description", embeddable=True
    )
    default_branch: str = AirweaveField(
        ..., description="Default branch of the repository", embeddable=True
    )
    created_at: datetime = AirweaveField(..., description="Creation timestamp", is_created_at=True)
    updated_at: datetime = AirweaveField(
        ..., description="Last update timestamp", is_updated_at=True
    )
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository", embeddable=True
    )
    fork: bool = AirweaveField(..., description="Whether the repository is a fork")
    size: int = AirweaveField(..., description="Size of the repository in KB")
    stars_count: Optional[int] = AirweaveField(None, description="Number of stars")
    watchers_count: Optional[int] = AirweaveField(None, description="Number of watchers")
    forks_count: Optional[int] = AirweaveField(None, description="Number of forks")
    open_issues_count: Optional[int] = AirweaveField(None, description="Number of open issues")


class GitHubDirectoryEntity(ChunkEntity):
    """Schema for GitHub directory entity."""

    path: str = AirweaveField(
        ..., description="Path of the directory within the repository", embeddable=True
    )
    repo_name: str = AirweaveField(
        ..., description="Name of the repository containing this directory", embeddable=True
    )
    repo_owner: str = AirweaveField(..., description="Owner of the repository", embeddable=True)


class GitHubCodeFileEntity(CodeFileEntity):
    """Schema for GitHub code file entity."""

    # GitHub specific fields only
    sha: str = AirweaveField(..., description="SHA hash of the file content")
    path: str = AirweaveField(
        ..., description="Path of the file within the repository", embeddable=True
    )
    is_binary: bool = AirweaveField(False, description="Flag indicating if file is binary")


class GithubRepoEntity(ChunkEntity):
    """Schema for a GitHub repository.

    References:
      https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28
    """

    name: Optional[str] = AirweaveField(
        None, description="Name of the repository.", embeddable=True
    )
    full_name: Optional[str] = AirweaveField(
        None, description="Full name (including owner) of the repo.", embeddable=True
    )
    owner_login: Optional[str] = AirweaveField(
        None, description="Login/username of the repository owner.", embeddable=True
    )
    private: bool = AirweaveField(False, description="Whether the repository is private.")
    description: Optional[str] = AirweaveField(
        None, description="Short description of the repository.", embeddable=True
    )
    fork: bool = AirweaveField(False, description="Whether this repository is a fork.")
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the repository was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the repository was last updated.", is_updated_at=True
    )
    pushed_at: Optional[datetime] = AirweaveField(
        None, description="When the repository was last pushed."
    )
    homepage: Optional[str] = AirweaveField(None, description="Homepage URL for the repository.")
    size: Optional[int] = AirweaveField(None, description="Size of the repository (in kilobytes).")
    stargazers_count: int = AirweaveField(0, description="Number of stars on this repository.")
    watchers_count: int = AirweaveField(0, description="Number of people watching this repository.")
    language: Optional[str] = AirweaveField(
        None, description="Primary language of the repository.", embeddable=True
    )
    forks_count: int = AirweaveField(0, description="Number of forks for this repository.")
    open_issues_count: int = AirweaveField(
        0, description="Number of open issues on this repository."
    )
    topics: List[str] = AirweaveField(
        default_factory=list, description="Topics/tags applied to this repo.", embeddable=True
    )
    default_branch: Optional[str] = AirweaveField(
        None, description="Default branch name of the repository.", embeddable=True
    )
    archived: bool = AirweaveField(False, description="Whether the repository is archived.")
    disabled: bool = AirweaveField(
        False, description="Whether the repository is disabled in GitHub."
    )


class GithubContentEntity(ChunkEntity):
    """Schema for a GitHub repository's content (file, directory, submodule, etc.).

    References:
      https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28
    """

    repo_full_name: Optional[str] = AirweaveField(
        None, description="Full name of the parent repository.", embeddable=True
    )
    path: Optional[str] = AirweaveField(
        None, description="Path of the file or directory within the repo.", embeddable=True
    )
    sha: Optional[str] = AirweaveField(None, description="SHA identifier for this content item.")
    item_type: Optional[str] = AirweaveField(
        None, description="Type of content. Typically 'file', 'dir', 'submodule', or 'symlink'."
    )
    size: Optional[int] = AirweaveField(None, description="Size of the content (in bytes).")
    html_url: Optional[str] = AirweaveField(
        None, description="HTML URL for viewing this content on GitHub."
    )
    download_url: Optional[str] = AirweaveField(
        None, description="Direct download URL if applicable."
    )
    content: Optional[str] = AirweaveField(
        None,
        description="File content (base64-encoded) if retrieved via 'mediaType=raw' or similar.",
        embeddable=True,
    )
    encoding: Optional[str] = AirweaveField(
        None, description="Indicates the encoding of the content (e.g., 'base64')."
    )


class GitHubFileDeletionEntity(ChunkEntity):
    """Schema for GitHub file deletion entity.

    This entity is used to signal that a file has been removed from the repository
    and should be deleted from the destination.
    """

    file_path: str = AirweaveField(
        ..., description="Path of the deleted file within the repository"
    )
    repo_name: str = AirweaveField(
        ..., description="Name of the repository containing the deleted file"
    )
    repo_owner: str = AirweaveField(..., description="Owner of the repository")
    deletion_status: str = AirweaveField(..., description="Status indicating the file was removed")

    def to_storage_dict(self, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Override to include deletion metadata for proper handling."""
        data = super().to_storage_dict(exclude_fields)
        data["_deletion_entity"] = True
        data["_deletion_target"] = self.entity_id
        return data
