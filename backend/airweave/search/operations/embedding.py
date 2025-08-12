"""Embedding generation operation.

This operation converts text queries into vector embeddings
that can be used for similarity search in the vector database.
"""

from typing import Any, Dict, List

from airweave.search.operations.base import SearchOperation


class Embedding(SearchOperation):
    """Generates vector embeddings for queries.

    This operation takes text queries (original or expanded) and
    converts them into vector embeddings using either OpenAI's
    embedding model or a local model depending on configuration.

    The embeddings are then used by the vector search operation
    to find similar documents in the vector database.
    """

    def __init__(self, model: str = "auto"):
        """Initialize embedding operation.

        Args:
            model: Embedding model to use ("auto", "openai", "local")
                  "auto" selects based on available API keys
        """
        self.model = model

    @property
    def name(self) -> str:
        """Operation name."""
        return "embedding"

    @property
    def depends_on(self) -> List[str]:
        """This depends on query expansion if it exists."""
        # We check at runtime if query_expansion actually ran
        return ["query_expansion"]

    async def execute(self, context: Dict[str, Any]) -> None:
        """Generate embeddings for queries.

        Reads from context:
            - query: Original query (fallback)
            - expanded_queries: Expanded queries (if available)
            - openai_api_key: For OpenAI embeddings
            - logger: For logging

        Writes to context:
            - embeddings: List of vector embeddings
        """
        from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
        from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec

        # Get queries to embed - use expanded if available, otherwise original
        queries = context.get("expanded_queries", [context["query"]])
        logger = context["logger"]
        openai_api_key = context.get("openai_api_key")

        logger.info(f"[Embedding] Generating embeddings for {len(queries)} queries")

        try:
            # Select embedding model based on configuration and available keys
            if self.model == "openai" and openai_api_key:
                embedder = OpenAIText2Vec(api_key=openai_api_key, logger=logger)
                logger.info("[Embedding] Using OpenAI embedding model")
            elif self.model == "local":
                embedder = LocalText2Vec(logger=logger)
                logger.info("[Embedding] Using local embedding model")
            elif self.model == "auto":
                # Auto-select based on API key availability
                if openai_api_key:
                    embedder = OpenAIText2Vec(api_key=openai_api_key, logger=logger)
                    logger.info("[Embedding] Auto-selected OpenAI embedding model")
                else:
                    embedder = LocalText2Vec(logger=logger)
                    logger.info("[Embedding] Auto-selected local embedding model (no OpenAI key)")
            else:
                # Default to local if model is unrecognized
                embedder = LocalText2Vec(logger=logger)
                logger.warning(
                    f"[Embedding] Unknown model '{self.model}', using local embedding model"
                )

            # Generate embeddings
            if len(queries) == 1:
                # Single query - use embed method
                embedding = await embedder.embed(queries[0])
                context["embeddings"] = [embedding]
            else:
                # Multiple queries - use embed_many for efficiency
                context["embeddings"] = await embedder.embed_many(queries)

            logger.info(
                f"[Embedding] Generated {len(context['embeddings'])} embeddings successfully"
            )

        except Exception as e:
            logger.error(f"[Embedding] Failed: {e}", exc_info=True)
            # Create fallback embeddings to allow search to continue
            # Use 384 dimensions (standard for sentence-transformers)
            fallback_embedding = [0.0] * 384
            context["embeddings"] = [fallback_embedding] * len(queries)
            logger.warning(f"[Embedding] Using fallback zero embeddings for {len(queries)} queries")
