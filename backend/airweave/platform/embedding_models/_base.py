"""Base class for embedding models."""

import logging
from abc import abstractmethod
from typing import List, Optional

from airweave.core.logging import logger as default_logger


class BaseEmbeddingModel:
    """Abstract base class for embedding models.

    This base class defines a generic interface for embedding models
    that can be used with different vector stores.
    """

    def __init__(self):
        """Initialize the base embedding model."""
        self._logger: Optional[logging.Logger] = (
            None  # Store contextual logger as instance variable
        )

    @property
    def logger(self):
        """Get the logger for this embedding model, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Fall back to default logger
        return default_logger

    @logger.setter
    def logger(self, logger: logging.Logger) -> None:
        """Set a contextual logger for this embedding model."""
        self._logger = logger

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string.

        Args:
            text: The text to embed
            model: Optional specific model to use (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        pass

    @abstractmethod
    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings.

        Args:
            texts: List of texts to embed
            model: Optional specific model to use (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        pass
