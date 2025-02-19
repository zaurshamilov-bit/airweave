"""OneDrive entity schemas.

Based on the OneDrive (and SharePoint) API reference (read-only scope for OneDrive),
we define entity schemas for the following core objects:
  • Drive
  • DriveItem

Each schema inherits from BaseEntity, which already provides an entity_id field to
store the OneDrive object's unique ID (e.g., drive.id or driveItem.id).

References:
  https://learn.microsoft.com/en-us/onedrive/developer/rest-api/?view=odsp-graph-online
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from app.platform.entities._base import BaseEntity


class OneDriveDriveEntity(BaseEntity):
    """Schema for a OneDrive Drive object.

    The inherited entity_id stores the drive's unique ID. Additional key fields come
    from the OneDrive/SharePoint drive resource. Owner and quota are typically
    nested objects; we store them as dictionaries.
    """

    drive_type: Optional[str] = Field(
        None,
        description=(
            "Describes the type of drive represented by this resource (e.g., personal or business)."
        ),
    )
    owner: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user or application that owns this drive."
    )
    quota: Optional[Dict[str, Any]] = Field(
        None,
        description="Information about the drive's storage quota (total, used, remaining, etc.).",
    )

    created_at: Optional[datetime] = Field(
        None, description="Datetime when the drive was created (from createdDateTime)."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Datetime when the drive was last modified (from lastModifiedDateTime)."
    )


class OneDriveDriveItemEntity(BaseEntity):
    """Schema for a OneDrive DriveItem object (file or folder).

    The inherited entity_id stores the DriveItem's unique ID. Many fields are optional
    because a DriveItem may represent either a file or a folder, and some properties
    appear only in one context.
    """

    name: Optional[str] = Field(None, description="The name of the item (folder or file).")
    etag: Optional[str] = Field(
        None, description="An eTag for the content of the item. Used for change tracking."
    )
    ctag: Optional[str] = Field(
        None, description="A cTag for the content of the item. Used for internal sync."
    )

    created_at: Optional[datetime] = Field(
        None, description="Datetime when the item was created (from createdDateTime)."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Datetime when the item was last modified (from lastModifiedDateTime)."
    )

    size: Optional[int] = Field(None, description="Size of the item in bytes.")
    web_url: Optional[str] = Field(
        None, description="URL that displays the resource in the browser."
    )

    # The OneDrive API merges 'file' and 'folder' metadata into the same DriveItem structure.
    # For a file, 'file' may have fields like mimeType, hashes, etc.
    # For a folder, 'folder' can have a childCount property.
    file: Optional[Dict[str, Any]] = Field(
        None, description="File metadata if the item is a file (e.g., mimeType, hashes)."
    )
    folder: Optional[Dict[str, Any]] = Field(
        None, description="Folder metadata if the item is a folder (e.g., childCount)."
    )

    # Parent reference typically contains info like driveId, id, path, etc.
    parent_reference: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Information about the parent of this item, such as driveId or parent folder path."
        ),
    )
