"""Local text2vec model for embedding."""
from typing import Any, Dict, Optional

from pydantic import Field

from app.core.logging import logger

from ._base import BaseEmbeddingModel


class LocalText2Vec(BaseEmbeddingModel):
    """Local text2vec model configuration for embedding."""

    model_name: str = "local-text2vec-transformers"
    inference_url: str = Field(
        default="http://text2vec-transformers:8080",
        description="URL of the inference API"
    )
    vector_dimensions: int = 384  # MiniLM-L6-v2 dimensions
    enabled: bool = True

    def get_model_config(self) -> Dict[str, Any]:
        """Get the model configuration."""
        return {
            "type": "text2vec-transformers",
            "inference_api": self.inference_url,
            "dimensions": self.vector_dimensions
        }

    def get_additional_config(self) -> Optional[Dict[str, Any]]:
        """Get additional configuration for generative features."""
        return None

    def get_headers(self) -> dict:
        """Get necessary headers for the vectorizer."""
        return {}

    @property
    def requires_api_key(self) -> bool:
        """Check if this vectorizer requires an API key."""
        return False

    def validate_configuration(self) -> bool:
        """Validate that the model is properly configured."""
        try:
            if not self.enabled:
                logger.warning("Local text2vec model is disabled")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating local text2vec configuration: {e}")
            return False


