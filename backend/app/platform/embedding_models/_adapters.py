"""Weaviate adapter for embedding models."""

from typing import Any, Optional

from weaviate.collections.classes.config import Configure, GenerativeConfig, VectorizerConfig

from app.platform.embedding_models._base import BaseEmbeddingModel


class WeaviateModelAdapter:
    """Adapter to convert generic embedding models to Weaviate-specific config."""

    @staticmethod
    def get_vectorizer_config(model: BaseEmbeddingModel) -> VectorizerConfig:
        """Convert model config to Weaviate vectorizer config."""
        if model.model_name == "openai-text2vec":
            return Configure.Vectorizer.text2vec_openai(
                api_key=model.api_key,
                dimensions=model.vector_dimensions,
                model_name=model.model_name,
            )
        elif model.model_name == "local-text2vec-transformers":
            return Configure.Vectorizer.text2vec_transformers(
                inference_url=model.inference_url,
            )

        raise ValueError(f"Unsupported model type: {model.model_name}")

    @staticmethod
    def get_generative_config(model: BaseEmbeddingModel) -> Optional[GenerativeConfig]:
        """Convert additional config to Weaviate generative config."""
        additional_config = model.get_additional_config()
        if not additional_config:
            return None

        if model.model_name == "openai-text2vec":
            return Configure.Generative.openai(
                model=model.model_name,
            )

        return None


class PineconeModelAdapter:
    """Adapter to convert generic embedding models to Pinecone-specific config."""

    @staticmethod
    def get_index_config(model: BaseEmbeddingModel) -> dict[str, Any]:
        """Get Pinecone index configuration for the model."""
        base_config = {"dimension": model.vector_dimensions, "metric": "cosine"}

        # Add model-specific configurations
        if model.model_name == "openai-text2vec":
            base_config.update(
                {
                    "pod_type": "p1",  # Standard pod type
                    "metadata_config": {
                        "indexed": ["timestamp", "source"]  # Example metadata fields
                    },
                }
            )
        elif model.model_name == "local-text2vec-transformers":
            base_config.update(
                {
                    "pod_type": "s1",  # Starter pod type
                    "metadata_config": {"indexed": ["timestamp", "source"]},
                }
            )

        return base_config

    @staticmethod
    def get_api_config(model: BaseEmbeddingModel) -> dict[str, Any]:
        """Get Pinecone API configuration for the model."""
        config = model.get_model_config()
        headers = model.get_headers()

        return {
            "api_config": {"headers": headers, "timeout": 10},  # Default timeout in seconds
            "model_config": config,
        }
