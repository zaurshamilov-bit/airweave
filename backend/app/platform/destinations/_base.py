"""Base destination class."""

from abc import abstractmethod
from typing import List
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
    async def bulk_insert(self, chunks: List[BaseChunk]) -> None:
        """Bulk insert chunks into the destination."""
        pass

    @abstractmethod
    async def bulk_delete(self, chunk_ids: List[str]) -> None:
        """Bulk delete chunks from the destination."""
        pass

    async def get_credentials(self, user: schemas.User) -> None:
        """Get credentials for the destination."""
        pass
