"""Base destination classes."""

from abc import ABC, abstractmethod
from typing import ClassVar, List
from uuid import UUID

from airweave import schemas
from airweave.platform.entities._base import ChunkEntity


class BaseDestination(ABC):
    """Common base destination class. This is the umbrella interface for all destinations."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

    @abstractmethod
    async def create(self, user: schemas.User) -> None:
        """Create a new destination."""
        pass

    @abstractmethod
    async def setup_collection(self, sync_id: UUID) -> None:
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
    async def bulk_delete_by_parent_id(self, parent_id: UUID) -> None:
        """Bulk delete entities from the destination by parent ID and entity ID."""
        pass

    @abstractmethod
    async def search_for_sync_id(self, sync_id: UUID) -> None:
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
    """Abstract base class for destinations backed by a graph database.

    This interface defines additional methods specific to graph operations.
    """

    @abstractmethod
    async def create_node(self, node_properties: dict, label: str) -> None:
        """Create a node in the graph database."""
        pass

    @abstractmethod
    async def create_relationship(
        self, from_node_id: str, to_node_id: str, rel_type: str, properties: dict = None
    ) -> None:
        """Create a relationship between two nodes in the graph database."""
        pass

    @abstractmethod
    async def bulk_create_nodes(self, nodes: list[dict]) -> None:
        """Bulk create nodes in the graph database."""
        pass

    @abstractmethod
    async def bulk_create_relationships(self, relationships: list[dict]) -> None:
        """Bulk create relationships in the graph database."""
        pass
