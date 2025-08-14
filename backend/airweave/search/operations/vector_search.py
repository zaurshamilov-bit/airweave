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
        # Allow a pre-search operator to override decay_config dynamically
        decay_config = context.get("decay_config", getattr(config, "decay_config", None))

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

        # Extra transparency: log recency bias weight if available
        if decay_config is not None and hasattr(decay_config, "weight"):
            logger.info(
                f"[VectorSearch] Recency bias weight={getattr(decay_config, 'weight', None)}; "
                f"datetime_field={getattr(decay_config, 'datetime_field', None)}"
            )

        try:
            destination = await QdrantDestination.create(
                collection_id=UUID(config.collection_id), logger=logger
            )
            if len(embeddings) > 1:
                await self._execute_bulk(
                    destination,
                    embeddings,
                    sparse_embeddings,
                    filter_dict,
                    search_method,
                    decay_config,
                    limit,
                    config,
                    logger,
                    context,
                )
            else:
                await self._execute_single(
                    destination,
                    embeddings,
                    sparse_embeddings,
                    filter_dict,
                    search_method,
                    decay_config,
                    limit,
                    config,
                    logger,
                    context,
                )
        except Exception as e:
            logger.error(f"[VectorSearch] Failed: {e}", exc_info=True)
            context["raw_results"] = []
            raise

    async def _execute_bulk(
        self,
        destination,
        embeddings,
        sparse_embeddings,
        filter_dict,
        search_method,
        decay_config,
        limit,
        config,
        logger,
        context,
    ) -> None:
        logger.debug(f"[VectorSearch] Performing bulk search with {len(embeddings)} query vectors")
        if sparse_embeddings:
            count_sparse = len(sparse_embeddings)
            logger.info("[VectorSearch] HYBRID search with %s BM25 vectors", count_sparse)
            try:
                non_zeros = [len(v.indices) for v in sparse_embeddings if hasattr(v, "indices")]
                if non_zeros:
                    avg_nz = sum(non_zeros) / len(non_zeros)
                    logger.debug(f"[VectorSearch] BM25 sparse avg non-zeros={avg_nz:.1f}")
            except Exception:
                pass
        else:
            logger.info("[VectorSearch] Using NEURAL-only search (no sparse vectors)")

        if decay_config:
            logger.info(
                ("[VectorSearch] Time decay ENABLED: type=%s, field=%s, scale=%s %s, midpoint=%s"),
                decay_config.decay_type,
                decay_config.datetime_field,
                decay_config.scale_value,
                decay_config.scale_unit,
                decay_config.midpoint,
            )
        else:
            logger.info("[VectorSearch] Time decay DISABLED")

        filter_conditions = [filter_dict] * len(embeddings) if filter_dict else None
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
        all_results = batch_results if isinstance(batch_results, list) else []
        merged_results = self._deduplicate(all_results)
        if config.offset > 0:
            merged_results = (
                merged_results[config.offset :] if config.offset < len(merged_results) else []
            )
        if len(merged_results) > limit:
            merged_results = merged_results[:limit]
        context["raw_results"] = merged_results

    async def _execute_single(
        self,
        destination,
        embeddings,
        sparse_embeddings,
        filter_dict,
        search_method,
        decay_config,
        limit,
        config,
        logger,
        context,
    ) -> None:
        logger.debug(f"[VectorSearch] Performing single vector search with method={search_method}")
        if sparse_embeddings and sparse_embeddings[0]:
            logger.info("[VectorSearch] Using HYBRID search with BM25 sparse vector")
            try:
                nz = len(getattr(sparse_embeddings[0], "indices", []) or [])
                logger.debug(f"[VectorSearch] BM25 sparse non-zeros (query 0)={nz}")
            except Exception:
                pass
        else:
            logger.info("[VectorSearch] Using NEURAL-only search (no sparse vector)")

        if decay_config:
            logger.info(
                ("[VectorSearch] Time decay ENABLED: type=%s, field=%s, scale=%s %s, midpoint=%s"),
                decay_config.decay_type,
                decay_config.datetime_field,
                decay_config.scale_value,
                decay_config.scale_unit,
                decay_config.midpoint,
            )
        else:
            logger.info("[VectorSearch] Time decay DISABLED")

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
        if context.get("raw_results") and logger.isEnabledFor(10):
            top_results = context["raw_results"][:5]
            for i, result in enumerate(top_results, 1):
                if isinstance(result, dict):
                    score = result.get("score", 0)
                    payload = result.get("payload", {})
                    date_field = None
                    if decay_config and isinstance(payload, dict):
                        if "airweave_system_metadata" in decay_config.datetime_field:
                            metadata = payload.get("airweave_system_metadata", {})
                            if isinstance(metadata, dict):
                                field_name = decay_config.datetime_field.split(".")[-1]
                                date_field = metadata.get(field_name)
                        else:
                            date_field = payload.get(decay_config.datetime_field)
                    entity_name = (
                        payload.get("name", payload.get("entity_id", ""))[:50]
                        if isinstance(payload, dict)
                        else ""
                    )
                    logger.debug(
                        f"[VectorSearch] Result {i}: score={score:.3f}, date={date_field or 'N/A'},"
                        f"name={entity_name}"
                    )

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
            # Skip non-dict results
            if not isinstance(result, dict):
                continue

            # Try to extract document ID from various possible locations
            doc_id = None
            # Try direct ID field
            doc_id = result.get("id") or result.get("_id")

            # If not found, try in payload
            if not doc_id and "payload" in result:
                payload = result.get("payload", {})
                if isinstance(payload, dict):
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
                if doc_id not in best_results:
                    best_results[doc_id] = result
                elif score > best_results[doc_id].get("score", 0):
                    best_results[doc_id] = result
            else:
                # If we can't find an ID, include the result anyway
                # Use a unique key based on result position
                unique_key = f"no_id_{len(best_results)}_{id(result)}"
                best_results[unique_key] = result

        # Convert back to list and sort by score
        merged = list(best_results.values())
        # Filter out any non-dict values that shouldn't be there
        merged = [r for r in merged if isinstance(r, dict)]
        if merged:
            merged.sort(key=lambda x: x.get("score", 0), reverse=True)

        return merged
