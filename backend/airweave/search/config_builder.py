"""Search configuration builder.

This module builds a SearchConfig from a SearchRequest, creating the execution
plan with the appropriate operations based on the request parameters.

DEFAULT VALUES:
--------------
All default values for search operations are centralized here:
- limit: 20 (if not specified)
- offset: 0 (if not specified)
- score_threshold: None (no threshold by default)
- search_method: "hybrid" (combines neural + BM25 search)
- decay_config: Enabled by default with 7-day linear decay (can be disabled with enable_decay=False)
- expansion_strategy: AUTO (if not specified, generates up to 4 query variations)
- response_type: RAW (if not specified)
- enable_reranking: True (ON by default, can be disabled with enable_reranking=False)
- enable_query_interpretation: True (ON by default, can be disabled with
  enable_query_interpretation=False)

These defaults can only be overridden by explicit values in the SearchRequest.
"""

from airweave.api.context import ApiContext
from airweave.platform.destinations._config import DecayConfig
from airweave.schemas.search import (
    QueryExpansionStrategy,
    ResponseType,
    SearchConfig,
    SearchRequest,
)
from airweave.search.operations import (
    CompletionGeneration,
    Embedding,
    LLMReranking,
    QdrantFilterOperation,
    QueryExpansion,
    QueryInterpretation,
    VectorSearch,
)


class SearchConfigBuilder:
    """Builds SearchConfig with operations from SearchRequest.

    This builder analyzes the SearchRequest and creates a SearchConfig
    with the appropriate operations configured and assigned to their
    specific fields.
    """

    def build(
        self, search_request: SearchRequest, collection_id: str, ctx: ApiContext
    ) -> SearchConfig:
        """Build SearchConfig from SearchRequest.

        This method:
        1. Extracts parameters from the request
        2. Applies defaults for missing values
        3. Creates and configures appropriate operations
        4. Returns SearchConfig with operations assigned to fields

        Args:
            search_request: User's search request
            collection_id: ID of the collection to search
            ctx: API context for logging

        Returns:
            SearchConfig with operations configured
        """
        ctx.logger.info(
            f"Building search config for query: '{search_request.query[:50]}...', "
            f"collection: {collection_id}"
        )

        # Build the operations based on request
        ops = self._create_operations(search_request, ctx)

        # Log which operations are enabled
        enabled_ops = []
        if ops["query_interpretation"]:
            enabled_ops.append("query_interpretation")
        if ops["query_expansion"]:
            enabled_ops.append("query_expansion")
        if ops["qdrant_filter"]:
            enabled_ops.append("qdrant_filter")
        enabled_ops.extend(["embedding", "vector_search"])  # Always present
        if ops["reranking"]:
            enabled_ops.append(f"reranking({ops['reranking'].name})")
        if ops["completion"]:
            enabled_ops.append("completion")

        ctx.logger.info(f"Enabled operations: {enabled_ops}")

        # Apply defaults for all parameters
        # Use explicit None checks to handle 0 values correctly
        limit = search_request.limit if search_request.limit is not None else 20
        offset = search_request.offset if search_request.offset is not None else 0
        score_threshold = search_request.score_threshold  # None is valid (no threshold)

        # Handle hybrid search and decay parameters
        search_method = search_request.search_method or "hybrid"

        # Handle decay config - apply defaults
        if search_request.decay_config:
            # User provided explicit decay config
            decay_config = search_request.decay_config
        elif search_request.enable_decay is False:
            # User explicitly disabled decay
            decay_config = None
        else:
            # Default: Enable decay with default config (unless explicitly disabled)
            # This applies when enable_decay is True or None (not specified)
            decay_config = DecayConfig(
                decay_type="linear",
                datetime_field="airweave_system_metadata.airweave_updated_at",
                scale_unit="day",
                scale_value=7,  # Decay over 7 days
                midpoint=0.5,  # 50% score at 7 days old
            )

        # Create the config with operations as fields
        config = SearchConfig(
            # Core parameters with defaults
            query=search_request.query,
            collection_id=collection_id,
            limit=limit,
            offset=offset,
            score_threshold=score_threshold,
            # Hybrid search and decay parameters
            search_method=search_method,
            decay_config=decay_config,
            # Operations as fields
            query_interpretation=ops["query_interpretation"],
            query_expansion=ops["query_expansion"],
            qdrant_filter=ops["qdrant_filter"],
            embedding=ops["embedding"],
            vector_search=ops["vector_search"],
            reranking=ops["reranking"],
            completion=ops["completion"],
        )

        return config

    def _create_operations(self, search_request: SearchRequest, ctx: ApiContext) -> dict:
        """Create operations based on request parameters.

        Returns a dictionary with operation instances or None for each field.

        Args:
            search_request: User's search request
            ctx: API context for logging

        Returns:
            Dictionary with operation instances keyed by field name
        """
        ops = {}

        # Get search method for operations that need it
        search_method = search_request.search_method or "hybrid"

        # ========== Query Interpretation (Optional) ==========
        if self._should_enable_query_interpretation(search_request):
            ctx.logger.debug("Enabling query interpretation")
            ops["query_interpretation"] = QueryInterpretation()
        else:
            ops["query_interpretation"] = None

        # ========== Query Expansion (Optional) ==========
        # Apply default expansion strategy if not specified
        expansion_strategy = search_request.expansion_strategy
        if expansion_strategy is None:
            expansion_strategy = QueryExpansionStrategy.AUTO

        if expansion_strategy != QueryExpansionStrategy.NO_EXPANSION:
            ctx.logger.debug(f"Enabling query expansion with strategy: {expansion_strategy}")
            ops["query_expansion"] = QueryExpansion(strategy=expansion_strategy, max_expansions=4)
        else:
            ops["query_expansion"] = None

        # ========== Qdrant Filter (Optional) ==========
        if search_request.filter:
            ctx.logger.debug("Enabling Qdrant filter")
            # Store the filter dict in the operation
            filter_op = QdrantFilterOperation()
            # Store the filter dict for the operation to use
            filter_op.filter_dict = (
                search_request.filter.model_dump(exclude_none=True)
                if search_request.filter
                else None
            )
            ops["qdrant_filter"] = filter_op
        else:
            ops["qdrant_filter"] = None

        # ========== Core Operations (Always Required) ==========
        ctx.logger.debug(
            f"Adding core operations: embedding, vector_search with search_method={search_method}"
        )
        ops["embedding"] = Embedding(search_method=search_method)
        ops["vector_search"] = VectorSearch(search_method=search_method)

        # ========== Reranking (Optional) ==========
        if self._should_enable_reranking(search_request):
            ctx.logger.debug("Enabling LLM reranking")
            ops["reranking"] = LLMReranking()
        else:
            ops["reranking"] = None

        # ========== Completion (Optional) ==========
        # Apply default response type if not specified
        response_type = search_request.response_type
        if response_type is None:
            response_type = ResponseType.RAW

        if response_type == ResponseType.COMPLETION:
            ctx.logger.debug("Enabling completion generation")
            ops["completion"] = CompletionGeneration(default_model="gpt-4o", max_results_context=10)
        else:
            ops["completion"] = None

        return ops

    def _should_enable_query_interpretation(self, search_request: SearchRequest) -> bool:
        """Determine if query interpretation should be enabled.

        Args:
            search_request: User's search request

        Returns:
            Whether to enable query interpretation
        """
        # Default is ON, can be explicitly disabled with False
        if search_request.enable_query_interpretation is None:
            return True  # Default ON
        return bool(search_request.enable_query_interpretation)

    def _should_enable_reranking(self, search_request: SearchRequest) -> bool:
        """Determine if reranking should be enabled.

        Args:
            search_request: User's search request

        Returns:
            Whether to enable reranking
        """
        # Default is ON, can be explicitly disabled with False
        if search_request.enable_reranking is None:
            return True  # Default ON
        return bool(search_request.enable_reranking)
