"""Base source class."""

from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional

from app.platform.chunks._base import BaseChunk


class BaseSource:
    """Base source class."""

    @classmethod
    @abstractmethod
    async def create(cls, credentials: Optional[Any] = None) -> "BaseSource":
        """Create a new source instance.

        Args:
            credentials: Optional credentials for authenticated sources.
                       For AuthType.none sources, this can be None.
        """
        pass

    @abstractmethod
    async def generate_chunks(self) -> AsyncGenerator[BaseChunk, None]:
        """Generate chunks for the source."""
        pass
