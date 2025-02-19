"""Dropbox entity schemas."""

from datetime import datetime
from typing import Dict, Optional

from pydantic import Field

from app.platform.entities._base import BaseEntity


class DropboxAccountEntity(BaseEntity):
    """Schema for Dropbox account-level entities (e.g., user or team info).

    For MVP purposes, store minimal fields such as account ID, display name, and email.
    """

    display_name: str
    account_id: str
    email: Optional[str] = None
    profile_photo_url: Optional[str] = None
    is_team: bool = False  # Flag to indicate if this relates to a Dropbox Business/Team


class DropboxFolderEntity(BaseEntity):
    """Schema for Dropbox folder entities.

    Mirrors folder metadata (like path, IDs, etc.).
    """

    folder_id: str
    name: str
    path_lower: Optional[str] = None
    path_display: Optional[str] = None
    shared_folder_id: Optional[str] = None
    is_team_folder: bool = False


class DropboxFileEntity(BaseEntity):
    """Schema for Dropbox file entities.

    Includes core file metadata like file ID, path, size, timestamps.
    """

    file_id: str
    name: str
    path_lower: Optional[str] = None
    path_display: Optional[str] = None
    rev: Optional[str] = None
    client_modified: Optional[datetime] = None
    server_modified: Optional[datetime] = None
    size: Optional[int] = None
    is_downloadable: bool = True
    sharing_info: Optional[Dict] = Field(default_factory=dict)
