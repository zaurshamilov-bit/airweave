"""Notion entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.core.datetime_utils import utc_now_naive
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import ChunkEntity, FileEntity


class NotionDatabaseEntity(ChunkEntity):
    """Schema for a Notion database."""

    database_id: str = AirweaveField(..., description="The ID of the database")
    title: str = AirweaveField(..., description="The title of the database", embeddable=True)
    description: str = AirweaveField(
        default="", description="The description of the database", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Database properties schema", embeddable=False
    )
    properties_text: Optional[str] = AirweaveField(
        default=None, description="Human-readable schema description", embeddable=True
    )
    parent_id: str = AirweaveField(description="The ID of the parent")
    parent_type: str = AirweaveField(
        description="The type of the parent (workspace, page_id, etc.)"
    )
    icon: Optional[Dict[str, Any]] = AirweaveField(None, description="The icon of the database")
    cover: Optional[Dict[str, Any]] = AirweaveField(None, description="The cover of the database")
    archived: bool = AirweaveField(default=False, description="Whether the database is archived")
    is_inline: bool = AirweaveField(default=False, description="Whether the database is inline")
    url: str = AirweaveField(description="The URL of the database")
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the database was created", is_created_at=True
    )
    last_edited_time: Optional[datetime] = AirweaveField(
        None, description="When the database was last edited", is_updated_at=True
    )

    def model_post_init(self, __context) -> None:
        """Post-init hook to generate properties_text from schema."""
        super().model_post_init(__context)

        # Generate human-readable schema text if not already set
        if self.properties and not self.properties_text:
            self.properties_text = self._generate_schema_text()

    def _generate_schema_text(self) -> str:
        """Generate human-readable text from database schema for embedding.

        Creates a clean representation of the database structure.
        """
        if not self.properties:
            return ""

        text_parts = []

        for prop_name, prop_info in self.properties.items():
            if isinstance(prop_info, dict):
                prop_type = prop_info.get("type", "unknown")

                # Build property description
                desc_parts = [f"{prop_name} ({prop_type})"]

                # Add options if available
                if "options" in prop_info and prop_info["options"]:
                    options_str = ", ".join(prop_info["options"][:5])  # Limit to first 5
                    if len(prop_info["options"]) > 5:
                        options_str += f" +{len(prop_info['options']) - 5} more"
                    desc_parts.append(f"options: {options_str}")

                # Add format for numbers
                if "format" in prop_info:
                    desc_parts.append(f"format: {prop_info['format']}")

                text_parts.append(" ".join(desc_parts))

        return " | ".join(text_parts) if text_parts else ""


class NotionPageEntity(ChunkEntity):
    """Schema for a Notion page with aggregated content."""

    page_id: str = AirweaveField(..., description="The ID of the page")
    parent_id: str = AirweaveField(description="The ID of the parent")
    parent_type: str = AirweaveField(
        description="The type of the parent (workspace, page_id, database_id, etc.)"
    )
    title: str = AirweaveField(..., description="The title of the page", embeddable=True)
    content: Optional[str] = AirweaveField(
        default=None, description="Full aggregated content", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Formatted page properties for search", embeddable=False
    )
    properties_text: Optional[str] = AirweaveField(
        default=None, description="Human-readable properties text", embeddable=True
    )
    property_entities: List[Any] = AirweaveField(
        default_factory=list, description="Structured property entities", embeddable=False
    )
    files: List[Any] = AirweaveField(
        default_factory=list, description="Files referenced in the page"
    )
    icon: Optional[Dict[str, Any]] = AirweaveField(None, description="The icon of the page")
    cover: Optional[Dict[str, Any]] = AirweaveField(None, description="The cover of the page")
    archived: bool = AirweaveField(default=False, description="Whether the page is archived")
    in_trash: bool = AirweaveField(default=False, description="Whether the page is in trash")
    url: str = AirweaveField(description="The URL of the page")
    content_blocks_count: int = AirweaveField(default=0, description="Number of blocks processed")
    max_depth: int = AirweaveField(default=0, description="Maximum nesting depth of blocks")
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the page was created", is_created_at=True
    )
    last_edited_time: Optional[datetime] = AirweaveField(
        None, description="When the page was last edited", is_updated_at=True
    )

    # Lazy mechanics removed; eager-only entity

    def model_post_init(self, __context) -> None:
        """Post-init hook to generate properties_text from properties dict."""
        super().model_post_init(__context)

        # Generate human-readable properties text if not already set
        if self.properties and not self.properties_text:
            self.properties_text = self._generate_properties_text()

    def _generate_properties_text(self) -> str:
        """Generate human-readable text from properties for embedding.

        Creates a clean, searchable representation of property values.
        """
        if not self.properties:
            return ""

        text_parts = []

        # Process properties in a logical order
        priority_keys = [
            "Product Name",
            "Name",
            "Title",
            "Status",
            "Priority",
            "Launch Status",
            "Owner",
            "Team",
            "Description",
        ]

        # First add priority properties
        for key in priority_keys:
            if key in self.properties:
                value = self.properties[key]
                if value and str(value).strip():
                    # Skip if it's the same as the page title
                    if key in ["Product Name", "Name", "Title"] and value == self.title:
                        continue
                    text_parts.append(f"{key}: {value}")

        # Then add remaining properties
        for key, value in self.properties.items():
            if key not in priority_keys and not key.endswith("_options"):
                if value and str(value).strip():
                    # Format the key nicely
                    formatted_key = key.replace("_", " ").title()
                    text_parts.append(f"{formatted_key}: {value}")

        return " | ".join(text_parts) if text_parts else ""


class NotionPropertyEntity(ChunkEntity):
    """Schema for a Notion database page property."""

    property_id: str = AirweaveField(..., description="The ID of the property")
    property_name: str = AirweaveField(..., description="The name of the property", embeddable=True)
    property_type: str = AirweaveField(..., description="The type of the property", embeddable=True)
    page_id: str = AirweaveField(..., description="The ID of the page this property belongs to")
    database_id: str = AirweaveField(
        ..., description="The ID of the database this property belongs to"
    )
    value: Optional[Any] = AirweaveField(
        None, description="The raw value of the property", embeddable=True
    )
    formatted_value: str = AirweaveField(
        default="", description="The formatted/display value of the property", embeddable=True
    )


class NotionFileEntity(FileEntity):
    """Schema for a Notion file."""

    # Notion-specific fields
    file_type: str = AirweaveField(
        ..., description="The type of file (file, external, file_upload)"
    )
    url: str = AirweaveField(..., description="The URL to access the file")
    expiry_time: Optional[datetime] = AirweaveField(
        None, description="When the file URL expires (for Notion-hosted files)"
    )
    caption: str = AirweaveField(default="", description="The caption of the file")

    # Initialize metadata field to ensure it exists
    metadata: Optional[Dict[str, Any]] = AirweaveField(
        default_factory=dict, description="Additional metadata about the file"
    )

    def needs_refresh(self) -> bool:
        """Check if the file URL needs to be refreshed (for Notion-hosted files)."""
        if self.file_type == "file" and self.expiry_time:
            return utc_now_naive() >= self.expiry_time
        return False

    def hash(self) -> str:
        """Hash the file entity.

        For files, we try the following strategies in order:
        1. If local_path is available, compute hash from actual file contents
        2. If checksum is available, use it as part of metadata hash
        3. Fall back to parent hash method using all metadata
        """
        if getattr(self, "_hash", None):
            return self._hash

        if self.airweave_system_metadata.local_path:
            # If we have the actual file, compute hash from its contents
            try:
                import hashlib

                with open(self.airweave_system_metadata.local_path, "rb") as f:
                    content = f.read()
                    self._hash = hashlib.sha256(content).hexdigest()
                    return self._hash
            except Exception:
                # If file read fails, fall through to next method
                pass

        # Fall back to parent hash method
        return super().hash()
