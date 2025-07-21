"""Query preprocessor for search service."""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

from airweave.core.config import settings
from airweave.schemas.search import QueryExpansions, QueryExpansionStrategy

logger = logging.getLogger(__name__)


class QueryPreprocessor:
    """Expand or rewrite a user query before embedding.

    Usage:
        preprocessor = QueryPreprocessor()
        queries = await preprocessor.expand("foo bar", strategy="llm")
    """

    def __init__(self) -> None:
        """Initialize resources."""
        self._openai_client = None

    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        """Lazy-load OpenAI client.

        Returns:
            AsyncOpenAI: The OpenAI client. If OPENAI_API_KEY is not set, returns None.
        """
        if self._openai_client is None and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    async def expand(
        self, query: str, strategy: QueryExpansionStrategy | str | None = None
    ) -> List[str]:
        """Main entry point. Returns list of expanded queries (first item is original query).

        Args:
            query (str): The query to expand.
            strategy (QueryExpansionStrategy | str | None): The strategy to use for expansion.
                - QueryExpansionStrategy.AUTO or "auto": Expand if LLM is available
                - QueryExpansionStrategy.LLM or "llm": Use LLM for expansion
                - QueryExpansionStrategy.NO_EXPANSION or "no_expansion": Return original query only
                - None: Defaults to AUTO

        Returns:
            List[str]: A list of queries, with the original query as the first item.
        """
        resolved_strategy = self._resolve_strategy(strategy)

        if resolved_strategy == QueryExpansionStrategy.NO_EXPANSION:
            return [query]
        elif resolved_strategy == QueryExpansionStrategy.LLM:
            return await self._llm_expand(query)

        # Fallback (shouldn't happen with proper resolution)
        return [query]

    def _resolve_strategy(
        self, requested: QueryExpansionStrategy | str | None
    ) -> QueryExpansionStrategy:
        """Resolve the expansion strategy to use.

        Args:
            requested: The requested strategy (enum, string, or None)

        Returns:
            QueryExpansionStrategy: The resolved strategy enum value
        """
        # Convert string to enum if needed
        if isinstance(requested, str):
            try:
                requested = QueryExpansionStrategy(requested.lower())
            except ValueError:
                logger.warning(f"Invalid expansion strategy '{requested}', defaulting to AUTO")
                requested = QueryExpansionStrategy.AUTO

        # None means AUTO
        if requested is None:
            requested = QueryExpansionStrategy.AUTO

        # Handle AUTO strategy
        if requested == QueryExpansionStrategy.AUTO:
            if settings.OPENAI_API_KEY:
                return QueryExpansionStrategy.LLM
            return QueryExpansionStrategy.NO_EXPANSION

        return requested

    async def _llm_expand(self, query: str, max_alts: int = 4) -> List[str]:
        """Use LLM to generate semantically similar search queries.

        Prompts GPT to create alternative phrasings that could retrieve relevant
        passages while maintaining the original search intent.

        Args:
            query (str): The query to expand.
            max_alts (int): The maximum number of alternatives to generate.

        Returns:
            List[str]: A list of queries, with the original query as the first item.
        """
        if not self.openai_client:
            logger.warning("OpenAI client not available for LLM expansion")
            return [query]

        try:
            # Generate alternatives using OpenAI
            alternatives = await self._call_openai_for_expansion(query, max_alts)

            # Process and validate the alternatives
            valid_alternatives = self._validate_alternatives(alternatives, query)

            # Build final result with original query first
            return self._build_expansion_result(query, valid_alternatives, max_alts)

        except Exception as e:
            logger.error(f"LLM expansion failed: {e}")
            return [query]

    async def _call_openai_for_expansion(self, query: str, max_alts: int) -> list:
        """Call OpenAI API to generate query alternatives.

        Args:
            query: The original search query
            max_alts: Maximum number of alternatives to request

        Returns:
            List of alternative queries from OpenAI
        """
        system_message = self._get_expansion_system_prompt()
        user_message = self._get_expansion_user_prompt(query, max_alts)

        try:
            # Use structured outputs with the parse method
            completion = await self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.7,
                max_tokens=200,
                response_format=QueryExpansions,  # Use Pydantic model for structured output
            )

            # Extract parsed result
            parsed_result = completion.choices[0].message.parsed
            if parsed_result:
                return parsed_result.alternatives

            logger.warning("No parsed result from structured output")
            return []

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
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

    def _get_expansion_user_prompt(self, query: str, max_alts: int) -> str:
        """Get the user prompt for query expansion."""
        return f"Generate up to {max_alts} alternative phrasings for this search query:\n\n{query}"

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
        self, original_query: str, valid_alternatives: List[str], max_alts: int
    ) -> List[str]:
        """Build the final expansion result with original query first.

        Args:
            original_query: The original search query
            valid_alternatives: Validated alternatives
            max_alts: Maximum number of alternatives to include

        Returns:
            Final list with original query first, then alternatives
        """
        result = [original_query]

        # Add alternatives up to the limit, avoiding duplicates
        for alt in valid_alternatives[:max_alts]:
            if alt not in result:
                result.append(alt)

        logger.info(f"LLM expanded '{original_query}' to {len(result)} variants")
        return result


# Singleton instance
query_preprocessor = QueryPreprocessor()
