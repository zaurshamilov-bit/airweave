"""Base source class."""

from abc import abstractmethod
from typing import Any, AsyncGenerator, ClassVar, List, Optional

from pydantic import BaseModel

from airweave.platform.entities._base import ChunkEntity


class BaseSource:
    """Base source class."""

    # Class variables for integration metadata
    _labels: ClassVar[List[str]] = []

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
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities for the source."""
        pass


class Relation(BaseModel):
    """A relation between two entities."""

    source_entity_type: type[ChunkEntity]
    source_entity_id_attribute: str
    target_entity_type: type[ChunkEntity]
    target_entity_id_attribute: str
    relation_type: str
