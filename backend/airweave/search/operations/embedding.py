"""Embedding generation operation.

This operation converts text queries into vector embeddings
that can be used for similarity search in the vector database.
"""

from typing import Any, Dict, List, Literal

from airweave.search.operations.base import SearchOperation


class Embedding(SearchOperation):
    """Generates vector embeddings for queries.

    This operation takes text queries (original or expanded) and
    converts them into vector embeddings using either OpenAI's
    embedding model or a local model depending on configuration.

    For hybrid search, it also generates sparse BM25 embeddings.

    The embeddings are then used by the vector search operation
    to find similar documents in the vector database.
    """

    def __init__(
        self, model: str = "auto", search_method: Literal["hybrid", "neural", "keyword"] = "hybrid"
    ):
        """Initialize embedding operation.

        Args:
            model: Embedding model to use ("auto", "openai", "local")
                  "auto" selects based on available API keys
            search_method: Search method that determines which embeddings to generate
        """
        self.model = model
        self.search_method = search_method

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
            - embeddings: List of neural vector embeddings
            - sparse_embeddings: List of sparse BM25 embeddings (if hybrid/keyword search)
        """
        from airweave.platform.embedding_models.bm25_text2vec import BM25Text2Vec
        from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
        from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec

        # Get queries to embed - use expanded if available, otherwise original
        queries = context.get("expanded_queries", [context["query"]])
        logger = context["logger"]
        openai_api_key = context.get("openai_api_key")

        logger.info(
            f"[Embedding] Generating embeddings for {len(queries)} queries "
            f"with search_method={self.search_method}"
        )

        try:
            # Generate neural embeddings if needed
            if self.search_method in ["hybrid", "neural"]:
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
                        logger.info(
                            "[Embedding] Auto-selected local embedding model (no OpenAI key)"
                        )
                else:
                    # Default to local if model is unrecognized
                    embedder = LocalText2Vec(logger=logger)
                    logger.warning(
                        f"[Embedding] Unknown model '{self.model}', using local embedding model"
                    )

                # Generate neural embeddings
                if len(queries) == 1:
                    # Single query - use embed method
                    embedding = await embedder.embed(queries[0])
                    context["embeddings"] = [embedding]
                else:
                    # Multiple queries - use embed_many for efficiency
                    context["embeddings"] = await embedder.embed_many(queries)

                logger.info(f"[Embedding] Generated {len(context['embeddings'])} neural embeddings")
            else:
                # For keyword-only search, create dummy neural embeddings
                context["embeddings"] = [[0.0] * 384] * len(queries)
                logger.info("[Embedding] Skipping neural embeddings for keyword-only search")

            # Generate sparse BM25 embeddings if needed
            if self.search_method in ["hybrid", "keyword"]:
                bm25_embedder = BM25Text2Vec(logger=logger)
                logger.info("[Embedding] Generating BM25 sparse embeddings")

                if len(queries) == 1:
                    sparse_embedding = await bm25_embedder.embed(queries[0])
                    context["sparse_embeddings"] = [sparse_embedding]
                else:
                    context["sparse_embeddings"] = await bm25_embedder.embed_many(queries)

                logger.info(
                    f"[Embedding] Generated {len(context['sparse_embeddings'])} sparse embeddings"
                )
            else:
                context["sparse_embeddings"] = None
                logger.info("[Embedding] Skipping sparse embeddings for neural-only search")

        except Exception as e:
            logger.error(f"[Embedding] Failed: {e}", exc_info=True)
            # Create fallback embeddings to allow search to continue
            # Use 384 dimensions (standard for sentence-transformers)
            fallback_embedding = [0.0] * 384
            context["embeddings"] = [fallback_embedding] * len(queries)
            logger.warning(f"[Embedding] Using fallback zero embeddings for {len(queries)} queries")
