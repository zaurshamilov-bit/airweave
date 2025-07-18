"""Search service for vector database integrations."""

import json
import logging

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.locator import resource_locator
from airweave.schemas.auth import AuthContext
from airweave.schemas.search import QueryExpansionStrategy, ResponseType, SearchStatus


class SearchService:
    """Service for handling vector database searches."""

    # OpenAI configuration constants
    DEFAULT_MODEL = "gpt-4o"
    DEFAULT_MODEL_SETTINGS = {
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
    }

    CONTEXT_PROMPT = """You are an AI assistant with access to a knowledge base.
    Use the following relevant context to help answer the user's question.
    Always format your responses in proper markdown, including:
    - Using proper headers (# ## ###)
    - Formatting code blocks with ```language
    - Using tables with | header | header |
    - Using bullet points and numbered lists
    - Using **bold** and *italic* where appropriate

    Here's the context:
    {context}

    Remember to:
    1. Be helpful, clear, and accurate
    2. Maintain a professional tone
    3. Format ALL responses in proper markdown
    4. Use tables when presenting structured data
    5. Use code blocks with proper language tags"""

    def __init__(self):
        """Initialize the search service with OpenAI client."""
        if not settings.OPENAI_API_KEY:
            logger = logging.getLogger(__name__)
            logger.warning("OPENAI_API_KEY is not set in environment variables")
            self.openai_client = None
        else:
            self.openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
            )

    def _clean_search_results(self, results: list[dict], for_display: bool = True) -> list[dict]:
        """Clean search results by removing large fields and optionally truncating content.

        Args:
            results: Raw search results from vector database
            for_display: If True, truncate large text fields for frontend display.
                        If False, only remove truly unnecessary fields (vectors, download_urls)

        Returns:
            Cleaned search results
        """
        cleaned_results = []

        for result in results:
            if not isinstance(result, dict):
                cleaned_results.append(result)
                continue

            cleaned_result = result.copy()

            if "payload" in cleaned_result and isinstance(cleaned_result["payload"], dict):
                payload = cleaned_result["payload"].copy()

                # Always remove these fields - they're too large or unnecessary
                fields_to_always_remove = [
                    "vector",
                    "download_url",
                    "local_path",
                    "file_uuid",
                    "checksum",
                ]
                for field in fields_to_always_remove:
                    payload.pop(field, None)

                if for_display:
                    # Handle nested JSON strings - parse them for better display
                    json_fields = ["metadata", "sync_metadata", "auth_fields", "config_fields"]
                    for field in json_fields:
                        if field in payload and isinstance(payload[field], str):
                            try:
                                # Try to parse JSON string to object for better display
                                payload[field] = json.loads(payload[field])
                            except json.JSONDecodeError:
                                # If it's not valid JSON, keep as is (no truncation)
                                pass

                cleaned_result["payload"] = payload

            cleaned_results.append(cleaned_result)

        return cleaned_results

    def _merge_search_results(
        self, all_results: list[dict], max_results: int = 15, logger: ContextualLogger = None
    ) -> list[dict]:
        """Merge and deduplicate search results from multiple query expansions.

        Deduplicates by document ID, keeping the highest score for each unique document.
        Results are re-sorted by score in descending order.

        Args:
            all_results (list[dict]): Combined results from multiple search queries
            max_results (int): Maximum number of results to return
            logger (ContextualLogger): Logger instance

        Returns:
            list[dict]: Deduplicated and sorted results
        """
        if not all_results:
            return []

        best_results = {}

        for result in all_results:
            doc_id = None
            if isinstance(result, dict):
                doc_id = result.get("id") or result.get("_id")
                if not doc_id and "payload" in result:
                    payload = result.get("payload", {})
                    doc_id = payload.get("entity_id") or payload.get("id") or payload.get("_id")

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

        # Optionally limit results to maintain performance
        if len(merged) > max_results:
            merged = merged[:max_results]

        logger.info(f"Merged {len(all_results)} results into {len(merged)} unique documents")

        return merged

    async def search(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        auth_context: AuthContext,
        logger: ContextualLogger,
        expansion_strategy: QueryExpansionStrategy | None = None,
    ) -> list[dict]:
        """Search across vector database using existing connections.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            readable_id (str): Readable ID of the collection to search within
            auth_context (AuthContext): Authentication context
            logger (ContextualLogger): Logger instance
            expansion_strategy (ExpansionStrategy | None): Query expansion strategy.
                If None, no expansion is performed.

        Returns:
            list[dict]: List of cleaned search results

        Raises:
            NotFoundException: If sync or connections not found
        """
        try:
            # Get collection and validate
            collection = await self._get_collection(db, readable_id, auth_context)

            # Get destination for vector search
            destination_class = await self._get_destination_class(db)
            destination = await destination_class.create(collection_id=collection.id)

            # Get appropriate embedding model
            embedding_model = self._get_embedding_model(readable_id, collection.id)

            # Perform search based on query expansion strategy
            if expansion_strategy and expansion_strategy != QueryExpansionStrategy.NO_EXPANSION:
                search_results = await self._search_with_expansion(
                    query, expansion_strategy, embedding_model, destination
                )
                embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)
            else:
                search_results = await self._search_single_query(
                    query, embedding_model, destination
                )

            # Clean and return results
            return self._clean_search_results(search_results, for_display=True)

        except NotFoundException:
            # Re-raise NotFoundExceptions as-is
            raise
        except ConnectionError as e:
            logger.error(f"Vector database connection error: {str(e)}")
            raise ConnectionError(f"Unable to connect to vector database: {str(e)}") from e
        except Exception as e:
            logger.error(f"Search error: {str(e)}", exc_info=True)
            # Add more context to the error
            if "connection" in str(e).lower():
                raise ConnectionError(f"Vector database connection failed: {str(e)}") from e
            raise

    async def _get_collection(
        self, db: AsyncSession, readable_id: str, auth_context: AuthContext
    ) -> schemas.Collection:
        """Get collection by readable ID and validate it exists."""
        collection = await crud.collection.get_by_readable_id(db, readable_id, auth_context)
        if not collection:
            raise NotFoundException("Collection not found")
        return collection

    async def _get_destination_class(self, db: AsyncSession):
        """Get the destination class for vector database operations."""
        destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
        if not destination_model:
            raise NotFoundException("Destination not found")
        return resource_locator.get_destination(destination_model)

    def _get_embedding_model(
        self, readable_id: str, collection_id: str, logger: ContextualLogger
    ) -> BaseEmbeddingModel:
        """Get the appropriate embedding model based on configuration."""
        if settings.OPENAI_API_KEY:
            logger.info(
                f"Using OpenAI embedding model for search in collection "
                f"{readable_id} {collection_id}"
            )
            return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)
        else:
            logger.info(
                f"Using local embedding model for search in collection "
                f"{readable_id} {collection_id}"
            )
            return LocalText2Vec(logger=logger)

    async def _search_with_expansion(
        self,
        query: str,
        expansion_strategy: QueryExpansionStrategy,
        embedding_model: BaseEmbeddingModel,
        destination: BaseDestination,
        logger: ContextualLogger,
    ) -> list[dict]:
        """Perform search with query expansion."""
        from airweave.core.query_preprocessor import query_preprocessor

        # Expand the query
        expanded_queries = await query_preprocessor.expand(query, strategy=expansion_strategy)
        logger.info(
            f"Expanded query '{query}' to {len(expanded_queries)} variants "
            f"using {expansion_strategy.value} strategy"
        )

        # Embed all expanded queries
        vectors = await embedding_model.embed_many(expanded_queries)

        # Search with each vector and collect results
        all_results = []
        for i, vector in enumerate(vectors):
            results = await destination.search(vector)
            # Tag results with which query variant found them (optional metadata)
            for result in results:
                result["_query_variant"] = expanded_queries[i]
            all_results.extend(results)

        # Merge and deduplicate results
        return self._merge_search_results(all_results)

    async def _search_single_query(
        self,
        query: str,
        embedding_model: BaseEmbeddingModel,
        destination: BaseDestination,
    ) -> list[dict]:
        """Perform search with a single query (no expansion)."""
        vector = await embedding_model.embed(query)
        return await destination.search(vector)

    async def search_with_completion(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        auth_context: AuthContext,
        logger: ContextualLogger,
        response_type: ResponseType = ResponseType.RAW,
        expansion_strategy: QueryExpansionStrategy | None = None,
    ) -> schemas.SearchResponse:
        """Search and optionally generate AI completion for results.

        Args:
            db: The database session
            query: The search query text
            readable_id: Readable ID of the collection to search in
            auth_context: Authentication context
            logger: Logger instance
            response_type: Type of response (raw results or AI completion)
            expansion_strategy: Query expansion strategy enum value. If None, no expansion.

        Returns:
            dict: A dictionary containing search results or AI completion
        """
        results = await self.search(
            db=db,
            query=query,
            readable_id=readable_id,
            auth_context=auth_context,
            logger=logger,
            expansion_strategy=expansion_strategy,
        )

        if response_type == ResponseType.RAW:
            return schemas.SearchResponse(
                results=results, response_type=response_type, status=SearchStatus.SUCCESS
            )

        # Check for no results or low-quality results
        quality_response = self._check_result_quality(results)
        if quality_response:
            return quality_response

        # For completion generation, we need full content (not truncated)
        # So fetch results again but with less aggressive cleaning
        raw_results = await self._get_raw_search_results(
            db=db,
            query=query,
            readable_id=readable_id,
            auth_context=auth_context,
            logger=logger,
            expansion_strategy=expansion_strategy,
        )
        context_results = self._clean_search_results(raw_results, for_display=False)

        # Process results and generate completion
        processed_results = self._process_search_results(results)
        completion = await self._generate_ai_completion(query, context_results)

        return schemas.SearchResponse(
            results=processed_results,
            completion=completion,
            response_type=response_type,
            status=SearchStatus.SUCCESS,
        )

    def _check_result_quality(self, results: list[dict]) -> schemas.SearchResponse | None:
        """Check if results are empty or have low quality scores.

        Returns:
            SearchResponse if results are poor quality, None if results are good
        """
        # If no results found, return a more specific message
        if not results:
            return schemas.SearchResponse(
                results=[],
                completion=(
                    "I couldn't find any relevant information for that query. "
                    "Try asking about something in your data collection."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RESULTS,
            )

        # For low-quality results (where scores are low), add this check:
        has_relevant_results = any(result.get("score", 0) > 0.25 for result in results)
        if not has_relevant_results:
            return schemas.SearchResponse(
                results=results,
                completion=(
                    "Your query didn't match anything meaningful in the database. "
                    "Please try a different question related to your data."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RELEVANT_RESULTS,
            )

        return None

    def _process_search_results(self, results: list[dict]) -> list[dict]:
        """Process search results by removing vector data and download URLs.

        Args:
            results: Raw search results

        Returns:
            Processed results with vectors and download URLs removed
        """
        for result in results:
            if isinstance(result, dict) and "payload" in result:
                # Remove vector from payload to avoid sending large data back
                result["payload"].pop("vector", None)
                # Also remove download URLs from payload
                result["payload"].pop("download_url", None)

        return results

    async def _generate_ai_completion(self, query: str, context_results: list[dict]) -> str:
        """Generate AI completion based on search results.

        Args:
            query: The user's search query
            context_results: Processed search results for context

        Returns:
            AI-generated completion text
        """
        # Prepare messages for OpenAI
        messages = [
            {
                "role": "system",
                "content": self.CONTEXT_PROMPT.format(
                    context=str(context_results),
                    additional_instruction=(
                        "If the provided context doesn't contain information to answer "
                        "the query directly, respond with 'I don't have enough information to "
                        "answer that question based on the available data.'"
                    ),
                ),
            },
            {"role": "user", "content": query},
        ]

        # Generate completion
        model = self.DEFAULT_MODEL
        model_settings = self.DEFAULT_MODEL_SETTINGS.copy()

        # Remove streaming setting if present
        model_settings.pop("stream", None)

        try:
            if not self.openai_client:
                return "OpenAI API key not configured. Cannot generate completion."

            response = await self.openai_client.chat.completions.create(
                model=model, messages=messages, **model_settings
            )

            return (
                response.choices[0].message.content
                if response.choices
                else "Unable to generate completion."
            )
        except Exception as e:
            return f"Error generating completion: {str(e)}"

    async def _get_raw_search_results(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        auth_context: AuthContext,
        logger: ContextualLogger,
        expansion_strategy: QueryExpansionStrategy | None = None,
    ) -> list[dict]:
        """Get raw search results without cleaning (internal use only).

        This is used when we need the full content for AI completion generation.
        """
        collection = await crud.collection.get_by_readable_id(db, readable_id, auth_context)
        if not collection:
            raise NotFoundException("Collection not found")

        destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
        if not destination_model:
            raise NotFoundException("Destination not found")

        destination_class = resource_locator.get_destination(destination_model)

        if settings.OPENAI_API_KEY:
            embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)
        else:
            embedding_model = LocalText2Vec(logger=logger)

        # Expand query if strategy is specified
        if expansion_strategy and expansion_strategy != QueryExpansionStrategy.NO_EXPANSION:
            from airweave.core.query_preprocessor import query_preprocessor

            expanded_queries = await query_preprocessor.expand(query, strategy=expansion_strategy)
            vectors = await embedding_model.embed_many(expanded_queries)

            all_results = []
            destination = await destination_class.create(collection_id=collection.id)

            for vector in vectors:
                results = await destination.search(vector)
                all_results.extend(results)

            return self._merge_search_results(all_results)
        else:
            # Original single-query flow
            vector = await embedding_model.embed(query)
            destination = await destination_class.create(collection_id=collection.id)
            return await destination.search(vector)


# Create singleton instance
search_service = SearchService()
