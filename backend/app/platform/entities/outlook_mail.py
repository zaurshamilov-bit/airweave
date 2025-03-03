"""Outlook Mail entity schemas.

Based on the Microsoft Graph Mail API (read-only scope), we define entity schemas for
the major Outlook mail objects relevant to our application:
 - MailFolder
 - Message

Objects that reference a hierarchical relationship (e.g., nested mail folders)
will represent that hierarchy through a list of breadcrumbs (see Breadcrumb in
app.platform.entities._base) rather than nested objects.

References:
    https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.platform.entities._base import Breadcrumb, ChunkEntity


class OutlookMailFolderEntity(ChunkEntity):
    """Schema for an Outlook mail folder.

    See:
      https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0
    """

    display_name: str = Field(..., description="Display name of the mail folder (e.g., 'Inbox').")
    parent_folder_id: Optional[str] = Field(
        None, description="ID of the parent mail folder, if any."
    )
    child_folder_count: Optional[int] = Field(
        None, description="Number of child mail folders under this folder."
    )
    total_item_count: Optional[int] = Field(
        None, description="Total number of items (messages) in this folder."
    )
    unread_item_count: Optional[int] = Field(
        None, description="Number of unread items in this folder."
    )
    well_known_name: Optional[str] = Field(
        None, description="Well-known name of this folder if applicable (e.g., 'inbox')."
    )


class OutlookMessageEntity(ChunkEntity):
    """Schema for an Outlook message.

    See:
      https://learn.microsoft.com/en-us/graph/api/resources/message?view=graph-rest-1.0
    """

    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list,
        description="Breadcrumb hierarchy (e.g., parent mail folder).",
    )
    subject: Optional[str] = Field(None, description="Subject of the email message.")
    body_preview: Optional[str] = Field(None, description="Short text preview of the message body.")
    body_content: Optional[str] = Field(None, description="Full text or HTML body of the message.")
    is_read: Optional[bool] = Field(
        False, description="Indicates if the message has been read (True) or is unread (False)."
    )
    is_draft: Optional[bool] = Field(
        False, description="Indicates if the message is still a draft."
    )
    importance: Optional[str] = Field(
        None, description="Indicates the importance of the message (Low, Normal, High)."
    )
    has_attachments: Optional[bool] = Field(
        False, description="Indicates if the message has file attachments."
    )
    internet_message_id: Optional[str] = Field(
        None, description="Internet message ID of the email (RFC 2822 format)."
    )
    from_: Optional[Dict[str, Any]] = Field(
        None,
        alias="from",
        description=(
            "Information about the sender. Typically includes emailAddress { name, address }."
        ),
    )
    to_recipients: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of primary recipients (each typically contains emailAddress info).",
    )
    cc_recipients: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of CC recipients (each typically contains emailAddress info).",
    )
    bcc_recipients: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of BCC recipients (each typically contains emailAddress info).",
    )
    sent_at: Optional[datetime] = Field(None, description="Timestamp when the message was sent.")
    received_at: Optional[datetime] = Field(
        None, description="Timestamp when the message was received."
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the message resource was created (if available)."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the message was last updated (if available)."
    )
