"""BM25 text2vec model for embedding."""

from typing import List, Optional

from fastembed import SparseEmbedding, SparseTextEmbedding

from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel


@embedding_model(
    "BM25 Text2Vec",
    "bm25",
    "local",
    model_name="local-bm25-text2vec",
    model_version="1.0",
)
class BM25Text2Vec(BaseEmbeddingModel):
    """Local text2vec model configuration for embedding."""

    # Configuration parameters as class attributes
    _model: SparseTextEmbedding
    model_name: str = "local-bm25-text2vec"

    def __init__(
        self,
        logger: Optional[ContextualLogger] = None,
        **data,  # Pass through to BaseEmbeddingModel/Pydantic, if relevant
    ):
        """Initialize the local text2vec model."""
        # Always call parent __init__ (esp. with Pydantic models!)
        super().__init__(**data)
        self._model = SparseTextEmbedding("Qdrant/bm25")
        if logger:
            self.logger = logger  # Override with contextual logger if provided

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[float] | SparseEmbedding:
        """Embed a single text string using the BM25 text2vec model.

        Args:
            text: The text to embed
            model: Optional model override (defaults to self.model_name)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)

        Returns:
            List of embedding values
        """
        return self._model.embed(text)

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using the BM25 text2vec model.

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

        return self._model.embed(texts)
