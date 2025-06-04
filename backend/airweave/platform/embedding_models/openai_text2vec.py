"""Simplified OpenAI text2vec model for embedding using official OpenAI client."""

import asyncio
from typing import List, Optional

from openai import AsyncOpenAI
from pydantic import Field

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel


@embedding_model(
    "OpenAI Text2Vec Simple",
    "openai_text2vec_simple",
    "openai",
    AuthType.config_class,
    "OpenAIAuthConfig",
)
class OpenAIText2Vec(BaseEmbeddingModel):
    """Simplified OpenAI text2vec model configuration for embedding using official OpenAI client."""

    model_name: str = "openai-text2vec-simple"
    api_key: str = Field(..., description="OpenAI API key")
    vector_dimensions: int = 1536
    enabled: bool = True
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model name"
    )

    def __init__(self, **kwargs):
        """Initialize the OpenAI Text2Vec model with a shared client."""
        super().__init__(**kwargs)

        # Create a single shared client
        self._client = AsyncOpenAI(
            api_key=self.api_key,
        )
        logger.info("Created shared OpenAI client")

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        entity_context: Optional[str] = None,
    ) -> List[float]:
        """Embed a single text string using OpenAI official client.

        Args:
            text: The text to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)
            entity_context: Optional context string for entity identification in logs

        Returns:
            List of embedding values
        """
        if dimensions:
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        context_prefix = f"{entity_context} " if entity_context else ""

        if not text.strip():
            logger.info(f"{context_prefix}Empty text provided for embedding, returning zero vector")
            return [0.0] * self.vector_dimensions

        used_model = model or self.embedding_model
        logger.info(
            f"{context_prefix}Embedding single text with model {used_model} "
            f"(text length: {len(text)})"
        )

        loop = asyncio.get_event_loop()
        cpu_start = loop.time()
        try:
            # Wait for the API call to complete with await
            response = await self._client.embeddings.create(
                input=text,
                model=used_model,
                encoding_format=encoding_format,
            )

            embedding = response.data[0].embedding
            cpu_elapsed = loop.time() - cpu_start
            logger.info(
                f"{context_prefix}Embedding completed in {cpu_elapsed:.2f}s, "
                f"vector size: {len(embedding)}"
            )
            return embedding

        except Exception as e:
            cpu_elapsed = loop.time() - cpu_start
            error_type = type(e).__name__
            logger.error(
                f"{context_prefix}Embedding failed after {cpu_elapsed:.2f}s "
                f"with {error_type}: {str(e)}"
            )
            raise

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        entity_context: Optional[str] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using OpenAI official client.

        Args:
            texts: List of texts to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)
            entity_context: Optional context string for entity identification in logs

        Returns:
            List of embedding vectors
        """
        if dimensions:
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        context_prefix = f"{entity_context} " if entity_context else ""

        if not texts:
            logger.info(f"{context_prefix}Empty texts list provided for embedding")
            return []

        logger.info(f"{context_prefix}Embedding batch of {len(texts)} texts")

        # Filter out empty texts and track their positions
        filtered_texts = []
        empty_indices = set()

        for i, text in enumerate(texts):
            if text.strip():
                filtered_texts.append(text)
            else:
                empty_indices.add(i)

        if not filtered_texts:
            logger.info(f"{context_prefix}All texts in batch were empty, returning zero vectors")
            return [[0.0] * self.vector_dimensions] * len(texts)

        logger.info(
            f"{context_prefix}Embedding {len(filtered_texts)} non-empty texts "
            f"(skipped {len(empty_indices)} empty texts)"
        )

        used_model = model or self.embedding_model
        loop = asyncio.get_event_loop()
        cpu_start = loop.time()

        try:
            # Wait for the API call to complete with await
            response = await self._client.embeddings.create(
                input=filtered_texts,
                model=used_model,
                encoding_format=encoding_format,
            )

            # Extract embeddings from response
            embeddings = [embedding_data.embedding for embedding_data in response.data]

            cpu_elapsed = loop.time() - cpu_start
            logger.info(
                f"{context_prefix}Batch embedding completed in {cpu_elapsed:.2f}s "
                f"({len(embeddings)} vectors)"
            )

            # Reinsert empty vectors at the correct positions
            result = []
            embedding_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    result.append([0.0] * self.vector_dimensions)
                else:
                    result.append(embeddings[embedding_idx])
                    embedding_idx += 1

            logger.info(f"{context_prefix}Final result contains {len(result)} vectors")
            return result

        except Exception as e:
            cpu_elapsed = loop.time() - cpu_start
            error_type = type(e).__name__
            logger.error(
                f"{context_prefix}Batch embedding failed after {cpu_elapsed:.2f}s "
                f"with {error_type}: {str(e)}"
            )
            raise

    async def close(self):
        """Clean up the shared client when done."""
        if self._client:
            await self._client.close()
            logger.info("OpenAI client closed successfully")
