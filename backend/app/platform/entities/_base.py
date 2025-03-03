"""Entity schemas."""

import hashlib
from typing import Any, Dict, List, Optional, Type, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, create_model


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str
    name: str
    type: str


class BaseEntity(BaseModel):
    """Base entity schema."""

    # Set in source connector
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


class PolymorphicEntity(BaseEntity):
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


T = TypeVar("T", bound=PolymorphicEntity)
