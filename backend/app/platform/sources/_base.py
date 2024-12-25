"""Base source class."""

from abc import abstractmethod
from typing import Any, AsyncGenerator

from app import schemas
from app.platform.chunks._base import BaseChunk


class BaseSource:
    """Base source class."""

    @abstractmethod
    async def create(self, user: schemas.User) -> None:
        """Create a new source."""
        pass

    @abstractmethod
    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate chunks for the source."""
        pass

    async def get_credentials(self, user: schemas.User) -> Any:
        """Get credentials for the source."""
        pass
