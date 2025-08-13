"""Vector search operation.

This operation performs the actual similarity search against
the Qdrant vector database using the generated embeddings.
"""

from typing import Any, Dict, List, Literal
from uuid import UUID

from airweave.search.operations.base import SearchOperation


class VectorSearch(SearchOperation):
    """Performs vector similarity search in Qdrant.

    This is the core search operation that queries the vector database
    using embeddings to find semantically similar documents. It handles
    both single and multi-query searches (from query expansion) and
    applies any filters that were generated or provided.

    Supports hybrid search (neural + BM25) and time-based decay.

    The operation also handles deduplication when multiple expanded
    queries return overlapping results.
    """

    def __init__(
        self,
        default_limit: int = 20,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
    ):
        """Initialize vector search operation.

        Args:
            default_limit: Default number of results if not specified
            search_method: Search method to use (hybrid, neural, or keyword)
        """
        self.default_limit = default_limit
        self.search_method = search_method

    @property
    def name(self) -> str:
        """Operation name."""
        return "vector_search"

    @property
    def depends_on(self) -> List[str]:
        """Dependencies - needs embeddings and optionally filters."""
        return ["embedding", "query_interpretation", "qdrant_filter"]

    async def execute(self, context: Dict[str, Any]) -> None:
        """Execute vector search against Qdrant.

        Reads from context:
            - embeddings: Neural vector embeddings to search with
            - sparse_embeddings: Optional sparse BM25 embeddings for hybrid search
            - filter: Optional Qdrant filter
            - config: SearchConfig for limit, offset, threshold, search_method, decay_config
            - logger: For logging

        Writes to context:
            - raw_results: Search results from Qdrant
        """
        from airweave.platform.destinations.qdrant import QdrantDestination

        config = context["config"]
        embeddings = context["embeddings"]
        sparse_embeddings = context.get("sparse_embeddings")
        # Use filter from context (set by qdrant_filter or query_interpretation ops)
        filter_dict = context.get("filter")
        logger = context["logger"]

        # Get search method and decay config from SearchConfig
        search_method = getattr(config, "search_method", self.search_method)
        decay_config = getattr(config, "decay_config", None)

        # Determine limit - fetch extra if we're going to rerank
        limit = config.limit
        # Check if reranking is enabled
        if config.reranking is not None:
            # Fetch more results for reranking to work with
            limit = min(int(config.limit * 2.5), 100)

        logger.info(
            f"[VectorSearch] Searching with {len(embeddings)} embeddings, "
            f"search_method={search_method}, limit={limit}, offset={config.offset}, "
            f"score_threshold={config.score_threshold}, filter={bool(filter_dict)}, "
            f"decay={bool(decay_config)}"
        )

        try:
            # Create Qdrant destination
            destination = await QdrantDestination.create(
                collection_id=UUID(config.collection_id), logger=logger
            )

            if len(embeddings) > 1:
                # Multiple embeddings - use bulk search
                logger.debug(
                    f"[VectorSearch] Performing bulk search with {len(embeddings)} query vectors"
                )

                # Create filter conditions list (same filter for all queries)
                filter_conditions = [filter_dict] * len(embeddings) if filter_dict else None

                # Perform bulk search with hybrid search and decay support
                batch_results = await destination.bulk_search(
                    embeddings,
                    limit=limit,
                    score_threshold=config.score_threshold,
                    with_payload=True,
                    filter_conditions=filter_conditions,
                    sparse_vectors=sparse_embeddings,
                    search_method=search_method,
                    decay_config=decay_config,
                )

                # Flatten results from all queries
                all_results = []
                for query_results in batch_results:
                    all_results.extend(query_results)

                # Deduplicate and merge results
                merged_results = self._deduplicate(all_results)

                # Apply offset after merging (since bulk search doesn't support offset)
                if config.offset > 0:
                    if config.offset < len(merged_results):
                        merged_results = merged_results[config.offset :]
                    else:
                        merged_results = []

                # Ensure we don't exceed limit
                if len(merged_results) > limit:
                    merged_results = merged_results[:limit]

                context["raw_results"] = merged_results

            else:
                # Single embedding - use regular search
                logger.debug(
                    f"[VectorSearch] Performing single vector search with method={search_method}"
                )

                results = await destination.search(
                    embeddings[0],
                    filter=filter_dict,
                    limit=limit,
                    offset=config.offset,
                    score_threshold=config.score_threshold,
                    with_payload=True,
                    sparse_vector=sparse_embeddings[0] if sparse_embeddings else None,
                    search_method=search_method,
                    decay_config=decay_config,
                )

                context["raw_results"] = results

            logger.info(f"[VectorSearch] Found {len(context['raw_results'])} results")

        except Exception as e:
            logger.error(f"[VectorSearch] Failed: {e}", exc_info=True)
            # Return empty results to allow pipeline to continue
            context["raw_results"] = []
            raise  # Re-raise to let executor handle based on optional flag

    def _deduplicate(self, results: List[Dict]) -> List[Dict]:
        """Deduplicate results keeping highest scores.

        When using query expansion, the same document might be found
        by multiple query variants. This method keeps only the best
        scoring instance of each document.

        Args:
            results: List of search results

        Returns:
            Deduplicated results sorted by score
        """
        if not results:
            return []

        best_results = {}

        for result in results:
            # Try to extract document ID from various possible locations
            doc_id = None
            if isinstance(result, dict):
                # Try direct ID field
                doc_id = result.get("id") or result.get("_id")

                # If not found, try in payload
                if not doc_id and "payload" in result:
                    payload = result.get("payload", {})
                    doc_id = (
                        payload.get("entity_id")
                        or payload.get("id")
                        or payload.get("_id")
                        or payload.get("db_entity_id")
                    )

            if doc_id:
                # Get current score
                score = result.get("score", 0)

                # Keep result with highest score
                if doc_id not in best_results or score > best_results[doc_id].get("score", 0):
                    best_results[doc_id] = result
            else:
                # If we can't find an ID, include the result anyway
                # Use a unique key based on result position
                unique_key = f"no_id_{len(best_results)}_{id(result)}"
                best_results[unique_key] = result

        # Convert back to list and sort by score
        merged = list(best_results.values())
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        return merged
