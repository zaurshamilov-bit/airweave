"""Entity schemas."""

import hashlib
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, create_model


class DestinationAction(str, Enum):
    """Action for an entity."""

    INSERT = "insert"
    UPDATE = "update"
    KEEP = "keep"


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str
    name: str
    type: str


class BaseEntity(BaseModel):
    """Base entity schema."""

    # Set in connector
    entity_id: str = Field(
        ..., description="ID of the entity this entity represents in the source."
    )
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="List of breadcrumbs for this entity."
    )

    # Set in sync service
    db_entity_id: UUID = Field(
        default_factory=uuid4, description="Unique ID of the entity in the DB."
    )
    source_name: Optional[str] = Field(
        None, description="Name of the source this entity came from."
    )
    sync_id: Optional[UUID] = Field(None, description="ID of the sync this entity belongs to.")
    sync_job_id: Optional[UUID] = Field(
        None, description="ID of the sync job this entity belongs to."
    )
    url: Optional[str] = Field(None, description="URL to the original content, if applicable.")
    sync_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the sync."
    )
    white_label_user_identifier: Optional[str] = Field(
        None, description="White label user identifier."
    )
    white_label_id: Optional[UUID] = Field(None, description="White label ID.")
    white_label_name: Optional[str] = Field(None, description="White label name.")

    class Config:
        """Pydantic config."""

        from_attributes = True

    def hash(self) -> str:
        """Hash the entity."""

        # Convert model to dict first, then sanitize any non-serializable values to strings
        def sanitize_value(v: Any) -> Any:
            if isinstance(v, (str, int, float, bool, type(None))):
                return v
            if isinstance(v, dict):
                return sanitize_dict(v)
            if isinstance(v, (list, tuple, set)):
                return [sanitize_value(x) for x in v]
            return str(v)

        def sanitize_dict(d: dict) -> dict:
            return {k: sanitize_value(v) for k, v in d.items()}

        data = self.model_dump(exclude={"sync_job_id"})
        sanitized_data = sanitize_dict(data)
        return hashlib.sha256(str(sanitized_data).encode()).hexdigest()


class ChunkEntity(BaseEntity):
    """Base class for entities that are storable and embeddable chunks of data."""

    parent_db_entity_id: Optional[UUID] = Field(
        None, description="ID of the parent entity in the DB."
    )


class ParentEntity(BaseEntity):
    """Base class for entities that are parents of other entities."""

    pass


class PolymorphicEntity(ChunkEntity):
    """Base class for dynamically generated entities.

    This class serves as the base for entities that are created at runtime,
    particularly for database table entities where the schema is determined
    by the table structure.
    """

    __abstract__ = True
    table_name: str
    schema_name: Optional[str] = None
    primary_key_columns: List[str] = Field(default_factory=list)

    @classmethod
    def create_table_entity_class(
        cls,
        table_name: str,
        schema_name: Optional[str],
        columns: Dict[str, Any],
        primary_keys: List[str],
    ) -> Type["PolymorphicEntity"]:
        """Create a new entity class for a database table.

        Args:
            table_name: Name of the database table
            schema_name: Optional database schema name
            columns: Dictionary of column names to their types and metadata
            primary_keys: List of primary key column names

        Returns:
            A new entity class with fields matching the table structure
        """
        # Create field definitions for the new model
        fields: Dict[str, Any] = {
            "table_name": (str, Field(default=table_name)),
            "schema_name": (Optional[str], Field(default=schema_name)),
            "primary_key_columns": (List[str], Field(default_factory=lambda: primary_keys)),
        }

        # Add fields for each database column
        for col_name, col_info in columns.items():
            python_type = col_info.get("python_type", Any)
            if col_name == "id":
                col_name = "id_"
            fields[col_name] = (Optional[python_type], Field(default=None))

        # Create the new model class
        model_name = f"{table_name.title().replace('_', '')}TableEntity"
        return create_model(
            model_name,
            __base__=cls,
            **fields,
        )


class FileEntity(BaseEntity):
    """Base schema for file entities."""

    file_id: str = Field(..., description="ID of the file in the source system")
    name: str = Field(..., description="Name of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    size: Optional[int] = Field(None, description="Size of the file in bytes")
    download_url: str = Field(..., description="URL to download the file")

    # File handling fields - set by file handler
    file_uuid: Optional[UUID] = Field(None, description="UUID assigned by the file manager")
    local_path: Optional[str] = Field(
        None, description="Temporary local path if file is downloaded"
    )
    checksum: Optional[str] = Field(None, description="File checksum/hash if available")
    total_size: Optional[int] = Field(None, description="Total size of the file in bytes")

    def hash(self) -> str:
        """Hash the file entity.

        For files, we try the following strategies in order:
        1. If local_path is available, compute hash from actual file contents
        2. If checksum is available, use it as part of metadata hash
        3. Fall back to parent hash method using all metadata
        """
        if self.local_path:
            # If we have the actual file, compute hash from its contents
            try:
                with open(self.local_path, "rb") as f:
                    content = f.read()
                    return hashlib.sha256(content).hexdigest()
            except Exception:
                # If file read fails, fall through to next method
                pass
        else:
            raise ValueError("File has no local path")

    @classmethod
    def create_parent_chunk_models(cls) -> Tuple[Type["ParentEntity"], Type["ChunkEntity"]]:
        """Create parent and chunk entity models for this file entity.

        This method dynamically generates two models:
        1. A parent model that inherits all fields from the source FileEntity subclass
           and represents the complete file metadata from the source system
        2. A chunk model that represents a chunk of the file's content with standardized
           fields for vector/graph DB storage

        Returns:
            A tuple of (ParentEntityClass, ChunkEntityClass)
        """
        # Get the class name prefix (e.g., "AsanaFile" from "AsanaFileEntity")
        class_name_prefix = cls.__name__.replace("Entity", "")

        # For parent, get all fields from the source FileEntity subclass
        parent_fields = {
            "number_of_chunks": (
                int,
                Field(default=0, description="Number of chunks of this file"),
            ),
        }
        for name, field in cls.model_fields.items():
            parent_fields[name] = (field.annotation, field)

        parent_model = create_model(
            f"{class_name_prefix}Parent", __base__=ParentEntity, **parent_fields
        )

        # For chunk, create standardized fields for vector/graph DB storage
        chunk_fields = {
            "md_title": (Optional[str], Field(None, description="Title or heading of the chunk")),
            "md_content": (str, Field(..., description="The actual content of the chunk")),
            "md_type": (
                str,
                Field(..., description="Type of content (e.g., paragraph, table, list)"),
            ),
            "metadata": (
                Dict[str, Any],
                Field(default_factory=dict, description="Additional metadata about the chunk"),
            ),
            "md_position": (
                Optional[int],
                Field(None, description="Position of this chunk in the document"),
            ),
            "md_parent_title": (
                Optional[str],
                Field(None, description="Title of the parent document"),
            ),
            "md_parent_url": (
                Optional[str],
                Field(None, description="URL of the parent document if available"),
            ),
        }

        chunk_model = create_model(
            f"{class_name_prefix}Chunk", __base__=ChunkEntity, **chunk_fields
        )

        return parent_model, chunk_model
