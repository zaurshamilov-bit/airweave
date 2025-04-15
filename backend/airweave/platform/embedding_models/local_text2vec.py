"""Local text2vec model for embedding."""

from typing import List, Optional

import httpx
from pydantic import Field

from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel


@embedding_model(
    "Local Text2Vec",
    "local_text2vec",
    "local",
    model_name="local-text2vec-transformers",
    model_version="1.0",
)
class LocalText2Vec(BaseEmbeddingModel):
    """Local text2vec model configuration for embedding."""

    model_name: str = "local-text2vec-transformers"
    inference_url: str = Field(
        default="http://text2vec-transformers:8080", description="URL of the inference API"
    )
    vector_dimensions: int = 384  # MiniLM-L6-v2 dimensions
    enabled: bool = True

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string using the local text2vec model.

        Args:
            text: The text to embed
            model: Optional model override (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        if model:
            raise ValueError("Model override not supported for local text2vec")

        if dimensions:
            raise ValueError("Dimensions override not supported for local text2vec")

        if not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.vector_dimensions

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.inference_url}/vectors", json={"text": text})
            response.raise_for_status()
            return response.json()["vector"]

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using the local text2vec model.

        Args:
            texts: List of texts to embed
            model: Optional model override (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if model:
            raise ValueError("Model override not supported for local text2vec")

        if dimensions:
            raise ValueError("Dimensions override not supported for local text2vec")

        # Filter out empty texts
        filtered_texts = [text for text in texts if text.strip()]

        if not filtered_texts:
            return [[0.0] * self.vector_dimensions] * len(texts)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.inference_url}/vectors/batch", json={"texts": filtered_texts}
            )
            response.raise_for_status()
            vectors = response.json()["vectors"]

            # Ensure we return vectors for all texts, including empty ones
            result = []
            filtered_idx = 0

            for text in texts:
                if text.strip():
                    result.append(vectors[filtered_idx])
                    filtered_idx += 1
                else:
                    result.append([0.0] * self.vector_dimensions)

            return result
