"""Base destination classes."""

import json
import logging
from abc import ABC, abstractmethod
from typing import ClassVar, List, Optional
from uuid import UUID

from airweave import schemas
from airweave.core.logging import logger as default_logger
from airweave.platform.entities._base import ChunkEntity


class BaseDestination(ABC):
    """Common base destination class. This is the umbrella interface for all destinations."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

    def __init__(self):
        """Initialize the base destination."""
        self._logger: Optional[logging.Logger] = (
            None  # Store contextual logger as instance variable
        )

    @property
    def logger(self):
        """Get the logger for this destination, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Fall back to default logger
        return default_logger

    def set_logger(self, logger: logging.Logger) -> None:
        """Set a contextual logger for this destination."""
        self._logger = logger

    @abstractmethod
    async def create(self, collection_id: UUID) -> "BaseDestination":
        """Create a new destination."""
        pass

    @abstractmethod
    async def setup_collection(self, collection_id: UUID, vector_size: int) -> None:
        """Set up the collection for storing entities."""
        pass

    @abstractmethod
    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into the destination."""
        pass

    @abstractmethod
    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into the destination."""
        pass

    @abstractmethod
    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from the destination."""
        pass

    @abstractmethod
    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entities from the destination."""
        pass

    @abstractmethod
    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities from the destination by sync ID."""
        pass

    @abstractmethod
    async def bulk_delete_by_parent_id(self, parent_id: UUID) -> None:
        """Bulk delete entities from the destination by parent ID and entity ID."""
        pass

    @abstractmethod
    async def search(self, query_vector: list[float]) -> None:
        """Search for a sync_id in the destination."""
        pass

    @abstractmethod
    async def get_credentials(self, user: schemas.User) -> None:
        """Get credentials for the destination."""
        pass


class VectorDBDestination(BaseDestination):
    """Abstract base class for destinations backed by a vector database.

    Inherits from BaseDestination and can have additional vector-specific methods if necessary.
    """

    # For now, no additional abstract methods are defined here; it uses BaseDestination's interface.
    pass


class GraphDBDestination(BaseDestination):
    """Abstract base class for destinations backed by a graph database."""

    # No additional abstract methods needed - the graph-specific operations
    # should be implementation details of the standard methods.

    # If needed, add helper methods that are not abstract:

    def _entity_to_node_properties(self, entity: ChunkEntity) -> dict:
        """Convert a ChunkEntity to Neo4j-compatible node properties."""
        # Get the basic serialized properties
        properties = entity.to_storage_dict()

        # Handle special fields like breadcrumbs for Neo4j
        if "breadcrumbs" in properties and isinstance(properties["breadcrumbs"], list):
            # Either serialize breadcrumbs to JSON string
            properties["breadcrumbs"] = json.dumps(properties["breadcrumbs"])
            # OR extract the most important properties from breadcrumbs
            # and store them as separate properties

        return properties
