"""OpenAI text2vec model for embedding."""
from typing import Any, Dict, Optional

from pydantic import Field

from app.core.logging import logger

from ._base import BaseEmbeddingModel


class OpenAIText2Vec(BaseEmbeddingModel):
    """OpenAI text2vec model configuration for embedding."""

    model_name: str = "openai-text2vec"
    api_key: str = Field(..., description="OpenAI API key")
    vector_dimensions: int = 1536
    enabled: bool = True

    def get_model_config(self) -> Dict[str, Any]:
        """Get the model configuration."""
        return {
            "type": "text2vec-openai",
            "api_key": self.api_key,
            "dimensions": self.vector_dimensions
        }

    def get_additional_config(self) -> Optional[Dict[str, Any]]:
        """Get additional configuration for generative features."""
        return {
            "type": "generative-openai",
            "api_key": self.api_key
        }

    def get_headers(self) -> dict:
        """Get necessary headers for the model."""
        return {"X-OpenAI-Api-Key": self.api_key} if self.api_key else {}

    @property
    def requires_api_key(self) -> bool:
        """Check if this model requires an API key."""
        return True

    def validate_configuration(self) -> bool:
        """Validate that the model is properly configured."""
        try:
            if not self.enabled:
                logger.warning("OpenAI text2vec model is disabled")
                return False

            if not self.api_key:
                logger.error("OpenAI API key is required")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating OpenAI text2vec configuration: {e}")
            return False
