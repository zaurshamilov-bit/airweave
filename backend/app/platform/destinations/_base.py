"""Base destination class."""

from abc import abstractmethod
from uuid import UUID

from app import schemas
from app.platform.chunks._base import BaseChunk


class BaseDestination:
    """Base destination class."""

    @abstractmethod
    async def create(self, user: schemas.User) -> None:
        """Create a new destination."""
        pass

    @abstractmethod
    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up the collection for storing chunks."""
        pass

    @abstractmethod
    async def insert(self, chunk: BaseChunk) -> None:
        """Insert a single chunk into the destination."""
        pass

    @abstractmethod
    async def bulk_insert(self, chunks: list[BaseChunk]) -> None:
        """Bulk insert chunks into the destination."""
        pass

    @abstractmethod
    async def delete(self, db_chunk_id: UUID) -> None:
        """Delete a single chunk from the destination."""
        pass

    @abstractmethod
    async def bulk_delete(self, chunk_ids: list[str]) -> None:
        """Bulk delete chunks from the destination."""
        pass

    @abstractmethod
    async def search_for_sync_id(self, sync_id: UUID) -> None:
        """Search for a sync_id in the destination."""
        pass

    async def get_credentials(self, user: schemas.User) -> None:
        """Get credentials for the destination."""
        pass
