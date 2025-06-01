"""OpenAI text2vec model for embedding."""

import asyncio
import random
import time
from typing import List, Optional

import httpx
from pydantic import Field

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel


@embedding_model(
    "OpenAI Text2Vec",
    "openai_text2vec",
    "openai",
    AuthType.config_class,
    "OpenAIAuthConfig",
)
class OpenAIText2Vec(BaseEmbeddingModel):
    """OpenAI text2vec model configuration for embedding."""

    model_name: str = "openai-text2vec"
    api_key: str = Field(..., description="OpenAI API key")
    vector_dimensions: int = 1536
    enabled: bool = True
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model name"
    )

    def __init__(self, **kwargs):
        """Initialize the OpenAI Text2Vec model."""
        super().__init__(**kwargs)
        self._client = None

    async def get_client(self):
        """Get or create the shared HTTP client for OpenAI API calls."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_keepalive_connections=5,  # Keep 5 connections alive
                    max_connections=10,  # Max 10 total connections
                    keepalive_expiry=30.0,  # Each connection lives 30s after last use
                ),
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    async def _retry_with_backoff(self, func, *args, max_retries=3, **kwargs):
        """Retry a function with exponential backoff.

        Args:
            func: The async function to retry
            *args: Arguments to pass to the function
            max_retries: Maximum number of retry attempts
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function call

        Raises:
            The last exception if all retries fail
        """
        last_exception = None

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # Don't retry on authentication errors or client errors (4xx except 429)
                if isinstance(e, httpx.HTTPStatusError):
                    status_code = e.response.status_code
                    if (
                        400 <= status_code < 500 and status_code != 429
                    ):  # 429 is rate limit, should retry
                        logger.error(f"Non-retryable HTTP error {status_code}: {e.response.text}")
                        raise e

                # Log the full error details
                error_type = type(e).__name__
                error_msg = str(e)
                if hasattr(e, "response") and hasattr(e.response, "text"):
                    error_msg += f" - Response: {e.response.text}"

                if attempt < max_retries:
                    # Calculate delay with exponential backoff and jitter
                    base_delay = 2**attempt  # 1s, 2s, 4s
                    jitter = random.uniform(0.1, 0.5)  # Add randomness
                    delay = base_delay + jitter

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed with {error_type}: "
                        f"{error_msg}. Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries + 1} attempts failed. "
                        f"Final error {error_type}: {error_msg}"
                    )

        # Re-raise the last exception if all retries failed
        raise last_exception

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float]:
        """Embed a single text string using OpenAI.

        Args:
            text: The text to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        if dimensions:
            # OpenAI doesn't support custom dimensions - would need post-processing
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        if not text.strip():
            logger.info("Empty text provided for embedding, returning zero vector")
            # Return zero vector for empty text
            return [0.0] * self.vector_dimensions

        used_model = model or self.embedding_model
        logger.info(f"Embedding single text with model {used_model} (text length: {len(text)})")

        async def _make_request():
            client = await self.get_client()
            logger.info("Sending embedding request to OpenAI API")
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": text, "model": used_model, "encoding_format": encoding_format},
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

        start_time = time.time()
        try:
            result = await self._retry_with_backoff(_make_request)
            elapsed = time.time() - start_time
            logger.info(f"Embedding completed in {elapsed:.2f}s, vector size: {len(result)}")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            error_type = type(e).__name__
            logger.error(f"Embedding failed after {elapsed:.2f}s with {error_type}: {str(e)}")
            raise

    async def _process_empty_texts(self, texts: List[str]) -> tuple:
        """Process texts to separate empty from non-empty.

        Returns:
            Tuple of (filtered_texts, empty_indices)
        """
        filtered_texts = []
        empty_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                filtered_texts.append(text)
            else:
                empty_indices.append(i)

        return filtered_texts, empty_indices

    async def _make_openai_request(
        self, filtered_texts: List[str], used_model: str, encoding_format: str
    ) -> List:
        """Make the actual request to OpenAI API with retry logic.

        Returns:
            List of embeddings
        """
        max_text_length = max(len(text) for text in filtered_texts) if filtered_texts else 0
        logger.info(f"Maximum text length in batch: {max_text_length} chars")

        async def _make_request():
            client = await self.get_client()

            # This will reuse an existing connection if available,
            # or create a new one if needed (up to max_connections=10)
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": filtered_texts,
                    "model": used_model,
                    "encoding_format": encoding_format,
                },
            )
            response.raise_for_status()
            return [e["embedding"] for e in response.json()["data"]]

        return await self._retry_with_backoff(_make_request)

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using OpenAI.

        Args:
            texts: List of texts to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding vectors
        """
        if dimensions:
            # OpenAI doesn't support custom dimensions - would need post-processing
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        if not texts:
            logger.info("Empty texts list provided for embedding")
            return []

        # Log batch size
        logger.info(f"Embedding batch of {len(texts)} texts")

        # Filter out empty texts and track their positions
        filtered_texts, empty_indices = await self._process_empty_texts(texts)

        if not filtered_texts:
            logger.info("All texts in batch were empty, returning zero vectors")
            return [[0.0] * self.vector_dimensions] * len(texts)

        # Log actual texts to embed
        logger.info(
            f"Embedding {len(filtered_texts)} non-empty texts "
            f"(skipped {len(empty_indices)} empty texts)"
        )

        used_model = model or self.embedding_model
        start_time = time.time()

        try:
            embeddings = await self._make_openai_request(
                filtered_texts, used_model, encoding_format
            )
            elapsed = time.time() - start_time
            logger.info(f"Batch embedding completed in {elapsed:.2f}s ({len(embeddings)} vectors)")

            # Reinsert empty vectors at the correct positions
            result = []
            embedding_idx = 0

            for i in range(len(texts)):
                if i in empty_indices:
                    result.append([0.0] * self.vector_dimensions)
                else:
                    result.append(embeddings[embedding_idx])
                    embedding_idx += 1

            logger.info(f"Final result contains {len(result)} vectors")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            error_type = type(e).__name__
            logger.error(f"Batch embedding failed after {elapsed:.2f}s with {error_type}: {str(e)}")
            raise

    async def close(self):
        """Clean up the client when done."""
        if self._client:
            await self._client.aclose()
            self._client = None
