"""Base class for embedding models."""

from abc import abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class BaseEmbeddingModel(BaseModel):
    """Abstract base class for embedding models.

    This base class defines a generic interface for embedding models
    that can be used with different vector stores (Weaviate, Pinecone, Milvus, etc.)
    """

    model_name: str
    vector_dimensions: int
    enabled: bool = True

    @abstractmethod
    def get_model_config(self) -> Dict[str, Any]:
        """Get the model configuration for the vector store."""
        pass

    @abstractmethod
    def get_additional_config(self) -> Optional[Dict[str, Any]]:
        """Get any additional configuration (e.g., for generative features)."""
        pass

    @abstractmethod
    def get_headers(self) -> dict:
        """Get necessary headers for the model."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Check if this model requires an API key."""
        pass

    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validate that the model is properly configured."""
        pass
