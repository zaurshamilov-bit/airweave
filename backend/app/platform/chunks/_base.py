"""Chunk schemas."""

import hashlib
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, create_model


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str
    name: str
    type: str


class BaseChunk(BaseModel):
    """Base chunk schema."""

    # Set in connector
    chunk_id: UUID = Field(default_factory=uuid4)
    entity_id: str
    breadcrumbs: List[Breadcrumb] = Field(default_factory=list)

    # Set in sync service
    db_chunk_id: Optional[UUID] = None  # The ID of the chunk in the DB
    source_name: Optional[str] = None
    sync_id: Optional[UUID] = None
    sync_job_id: Optional[UUID] = None
    url: Optional[str] = None
    sync_metadata: Optional[dict[str, Any]] = None
    white_label_user_identifier: Optional[str] = None
    white_label_id: Optional[str] = None
    white_label_name: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True

    def hash(self) -> str:
        """Hash the chunk."""

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


class PolymorphicChunk(BaseChunk):
    """Base class for dynamically generated chunks.

    This class serves as the base for chunks that are created at runtime,
    particularly for database table chunks where the schema is determined
    by the table structure.
    """

    __abstract__ = True
    table_name: str
    schema_name: Optional[str] = None
    primary_key_columns: List[str] = Field(default_factory=list)
    column_metadata: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def create_table_chunk_class(
        cls,
        table_name: str,
        schema_name: Optional[str],
        columns: Dict[str, Any],
        primary_keys: List[str],
    ) -> Type["PolymorphicChunk"]:
        """Create a new chunk class for a database table.

        Args:
            table_name: Name of the database table
            schema_name: Optional database schema name
            columns: Dictionary of column names to their types and metadata
            primary_keys: List of primary key column names

        Returns:
            A new chunk class with fields matching the table structure
        """
        # Create field definitions for the new model
        fields: Dict[str, Any] = {
            "table_name": (str, Field(default=table_name)),
            "schema_name": (Optional[str], Field(default=schema_name)),
            "primary_key_columns": (List[str], Field(default_factory=lambda: primary_keys)),
            "column_metadata": (Dict[str, Dict[str, Any]], Field(default_factory=lambda: columns)),
        }

        # Add fields for each database column
        for col_name, col_info in columns.items():
            python_type = col_info.get("python_type", Any)
            fields[col_name] = (Optional[python_type], Field(default=None))

        # Create the new model class
        model_name = f"{table_name.title().replace('_', '')}TableChunk"
        return create_model(
            model_name,
            __base__=cls,
            **fields,
        )


T = TypeVar("T", bound=PolymorphicChunk)
