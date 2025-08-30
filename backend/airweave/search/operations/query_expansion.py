"""Query expansion operation.

This operation expands the user's query into multiple variations
to improve recall. It can use different strategies including
LLM-based expansion or simple synonym expansion.
"""

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.schemas.search import QueryExpansions, QueryExpansionStrategy
from airweave.search.operations.base import SearchOperation


class QueryExpansion(SearchOperation):
    """Expands a query into multiple variations.

    This operation takes the original query and generates variations
    that might match relevant documents using different terminology.
    The expanded queries are then embedded and searched in parallel.

    Example:
        Input: "customer payment issues"
        Output: ["customer payment issues", "billing problems",
                 "payment failures", "transaction errors"]
    """

    def __init__(self, strategy: str = "auto", max_expansions: int = 4):
        """Initialize query expansion operation.

        Args:
            strategy: Expansion strategy ("auto", "llm", "none")
            max_expansions: Maximum number of query variations to generate
        """
        self.strategy = strategy
        self.max_expansions = max_expansions
        self._openai_client = None

    @property
    def name(self) -> str:
        """Operation name."""
        return "query_expansion"

    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        """Lazy-load OpenAI client.

        Returns:
            AsyncOpenAI: The OpenAI client. If OPENAI_API_KEY is not set, returns None.
        """
        if self._openai_client is None and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    async def execute(self, context: Dict[str, Any]) -> None:
        """Expand the query into multiple variations.

        Reads from context:
            - query: Original search query
            - config: SearchConfig (for strategy override)
            - logger: For logging

        Writes to context:
            - expanded_queries: List of query variations
        """
        query = context["query"]
        logger = context["logger"]
        config = context["config"]

        # Strategy can be overridden by config
        strategy = (
            config.expansion_strategy if hasattr(config, "expansion_strategy") else self.strategy
        )

        # Convert string strategy to enum if needed
        if isinstance(strategy, str):
            strategy = self._resolve_strategy(strategy)

        logger.info(f"[QueryExpansion] Expanding query using strategy: {strategy}")

        try:
            # Expand based on strategy
            expanded_queries = await self._expand(query, strategy)

            # Limit the number of expansions
            if len(expanded_queries) > self.max_expansions:
                expanded_queries = expanded_queries[: self.max_expansions]
                logger.info(
                    f"[QueryExpansion] Limited expansions from {len(expanded_queries)} "
                    f"to {self.max_expansions}"
                )

            context["expanded_queries"] = expanded_queries
            logger.info(
                f"[QueryExpansion] Expanded query '{query[:50]}...' "
                f"to {len(expanded_queries)} variations"
            )

            if logger.isEnabledFor(10):  # DEBUG level
                logger.debug(f"[QueryExpansion] Variations: {expanded_queries}")

        except Exception as e:
            logger.error(f"[QueryExpansion] Failed: {e}", exc_info=True)
            # Fallback to original query
            context["expanded_queries"] = [query]
            logger.info("[QueryExpansion] Using original query as fallback")

    def _resolve_strategy(self, requested: str | QueryExpansionStrategy) -> QueryExpansionStrategy:
        """Resolve the expansion strategy to use.

        Args:
            requested: The requested strategy (enum or string)

        Returns:
            QueryExpansionStrategy: The resolved strategy enum value
        """
        # Convert string to enum if needed
        if isinstance(requested, str):
            try:
                requested = QueryExpansionStrategy(requested.lower())
            except ValueError:
                # Default to AUTO for invalid values
                requested = QueryExpansionStrategy.AUTO

        # Handle AUTO strategy
        if requested == QueryExpansionStrategy.AUTO:
            if settings.OPENAI_API_KEY:
                return QueryExpansionStrategy.LLM
            return QueryExpansionStrategy.NO_EXPANSION

        return requested

    async def _expand(self, query: str, strategy: QueryExpansionStrategy) -> List[str]:
        """Main expansion entry point.

        Args:
            query: The query to expand
            strategy: The strategy to use

        Returns:
            List of queries with original first
        """
        if strategy == QueryExpansionStrategy.NO_EXPANSION:
            return [query]
        elif strategy == QueryExpansionStrategy.LLM:
            return await self._llm_expand(query)

        # Fallback
        return [query]

    async def _llm_expand(self, query: str) -> List[str]:
        """Use LLM to generate semantically similar search queries.

        Prompts GPT to create alternative phrasings that could retrieve relevant
        passages while maintaining the original search intent.

        Args:
            query: The query to expand

        Returns:
            List of queries with the original query as the first item
        """
        if not self.openai_client:
            return [query]

        try:
            # Generate alternatives using OpenAI
            alternatives = await self._call_openai_for_expansion(query)

            # Process and validate the alternatives
            valid_alternatives = self._validate_alternatives(alternatives, query)

            # Build final result with original query first
            return self._build_expansion_result(query, valid_alternatives)

        except Exception:
            # Log error but don't fail the search
            return [query]

    async def _call_openai_for_expansion(self, query: str) -> list:
        """Call OpenAI API to generate query alternatives.

        Args:
            query: The original search query

        Returns:
            List of alternative queries from OpenAI
        """
        system_message = self._get_expansion_system_prompt()
        user_message = self._get_expansion_user_prompt(query)

        try:
            # Use structured outputs with the parse method
            completion = await self.openai_client.beta.chat.completions.parse(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=200,
                response_format=QueryExpansions,  # Use Pydantic model for structured output
            )

            # Extract parsed result
            parsed_result = completion.choices[0].message.parsed
            if parsed_result:
                return parsed_result.alternatives

            return []

        except Exception:
            return []

    def _get_expansion_system_prompt(self) -> str:
        """Get the system prompt for query expansion."""
        return (
            "You are a search query expansion assistant. Your task is to rewrite search queries "
            "into semantically similar alternatives that might help find relevant information. "
            "Focus on:\n"
            "- Different phrasings of the same concept\n"
            "- Related terms and synonyms\n"
            "- More specific or more general versions\n"
            "Generate diverse alternatives that maintain the original search intent."
        )

    def _get_expansion_user_prompt(self, query: str) -> str:
        """Get the user prompt for query expansion."""
        return (
            f"Generate up to {self.max_expansions} alternative phrasings "
            f"for this search query:\n\n{query}"
        )

    def _validate_alternatives(self, alternatives: list, original_query: str) -> List[str]:
        """Validate and clean the alternatives from OpenAI.

        Args:
            alternatives: Raw alternatives from OpenAI
            original_query: The original query to avoid duplicates

        Returns:
            List of valid, cleaned alternatives
        """
        valid_alternatives = []

        for alt in alternatives:
            if isinstance(alt, str) and alt.strip():
                cleaned = alt.strip()
                # Skip if it's the same as original (case-insensitive)
                if cleaned.lower() != original_query.lower():
                    valid_alternatives.append(cleaned)

        return valid_alternatives

    def _build_expansion_result(
        self, original_query: str, valid_alternatives: List[str]
    ) -> List[str]:
        """Build the final expansion result with original query first.

        Args:
            original_query: The original search query
            valid_alternatives: Validated alternatives

        Returns:
            Final list with original query first, then alternatives
        """
        result = [original_query]

        # Add alternatives up to the limit, avoiding duplicates
        for alt in valid_alternatives[: self.max_expansions]:
            if alt not in result:
                result.append(alt)

        return result
