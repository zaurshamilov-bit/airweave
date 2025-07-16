"""Query preprocessor for search service."""

import logging
from typing import List, Optional

try:
    import nltk
    from nltk.corpus import wordnet

    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    nltk = None
    wordnet = None

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from airweave.core.config import settings
from airweave.schemas.search import QueryExpansionStrategy

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
        self._wordnet = None
        self._nltk_data_checked = False

    @property
    def openai_client(self) -> Optional[AsyncOpenAI]:
        """Lazy-load OpenAI client.

        Returns:
            AsyncOpenAI: The OpenAI client. If OPENAI_API_KEY is not set, returns None.
        """
        if self._openai_client is None and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    @property
    def wordnet_corpus(self):
        """Lazy-load WordNet corpus.

        Returns:
            wordnet: The WordNet corpus module or None if unavailable.
        """
        if self._wordnet is None:
            self._wordnet = self._load_wordnet()
        return self._wordnet

    async def expand(
        self, query: str, strategy: QueryExpansionStrategy | str | None = None
    ) -> List[str]:
        """Main entry point. Returns list of expanded queries (first item is original query).

        Args:
            query (str): The query to expand.
            strategy (QueryExpansionStrategy | str | None): The strategy to use for expansion.
                - QueryExpansionStrategy.AUTO or "auto": Use LLM if available, otherwise synonym
                - QueryExpansionStrategy.LLM or "llm": Use LLM for expansion
                - QueryExpansionStrategy.SYNONYM or "synonym": Use synonym expansion
                - QueryExpansionStrategy.NO_EXPANSION or "no_expansion": No expansion,
                    return original query only
                - None: Defaults to AUTO

        Returns:
            List[str]: A list of queries, with the original query as the first item.
        """
        resolved_strategy = self._resolve_strategy(strategy)

        if resolved_strategy == QueryExpansionStrategy.NO_EXPANSION:
            return [query]
        elif resolved_strategy == QueryExpansionStrategy.SYNONYM:
            return await self._synonym_expand(query)
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
            return QueryExpansionStrategy.SYNONYM

        return requested

    # Synonym / WordNet expansion
    async def _synonym_expand(self, query: str, max_alts: int = 3) -> List[str]:
        """Expand query by replacing words with their WordNet synonyms.

        Identifies nouns/verbs in the query and creates variations by substituting
        them with semantically similar words from WordNet.

        Args:
            query (str): The query to expand.
            max_alts (int): The maximum number of alternatives to generate.

        Returns:
            List[str]: A list of queries, with the original query as the first item.
        """
        # Check if NLTK is available
        if not self.wordnet_corpus:
            return [query]

        tokens = query.split()
        if not tokens:
            return [query]

        # Find words we can expand (nouns and verbs)
        expandable_words = self._find_expandable_words(tokens)
        if not expandable_words:
            return [query]

        # Generate variations by replacing words with synonyms
        variations = self._generate_synonym_variations(query, tokens, expandable_words, max_alts)

        return variations

    def _load_wordnet(self):
        """Load WordNet corpus, downloading if necessary.

        Returns:
            wordnet: The WordNet corpus module or None if unavailable.
        """
        if not NLTK_AVAILABLE:
            logger.warning("NLTK not available for synonym expansion")
            return None

        # Only check/download once
        if not self._nltk_data_checked:
            try:
                nltk.data.find("corpora/wordnet")
            except LookupError:
                try:
                    nltk.download("wordnet", quiet=True)
                    nltk.download("averaged_perceptron_tagger", quiet=True)
                except Exception as e:
                    logger.warning(f"Failed to download WordNet data: {e}")
                    return None
            self._nltk_data_checked = True

        return wordnet

    def _find_expandable_words(self, tokens: List[str]) -> List[tuple[int, str]]:
        """Find nouns and verbs in the query that can be expanded with synonyms.

        Args:
            tokens (List[str]): The tokens to find expandable words in.

        Returns:
            List[tuple[int, str]]: A list of tuples, with index and word of expandable words.
        """
        if not NLTK_AVAILABLE:
            return []

        try:
            pos_tags = nltk.pos_tag(tokens)
        except Exception:
            # If POS tagging fails, assume all words are nouns
            pos_tags = [(token, "NN") for token in tokens]

        expandable = []
        for i, (word, pos) in enumerate(pos_tags):
            # Check if it's a noun (NN*) or verb (VB*)
            if pos.startswith("NN") or pos.startswith("VB"):
                expandable.append((i, word))

        return expandable

    def _get_word_synonyms(self, word: str) -> set[str]:
        """Get synonyms for a word from WordNet.

        Args:
            word (str): The word to get synonyms for.

        Returns:
            set[str]: A set of synonyms for the word.
        """
        if not self.wordnet_corpus:
            return set()

        synonyms = set()
        for syn in self.wordnet_corpus.synsets(word):
            for lemma in syn.lemmas():
                # Get the synonym and clean it up
                synonym = lemma.name().replace("_", " ")
                if synonym.lower() != word.lower():
                    synonyms.add(synonym)
        return synonyms

    def _generate_synonym_variations(
        self,
        original_query: str,
        tokens: List[str],
        expandable_words: List[tuple[int, str]],
        max_alts: int,
    ) -> List[str]:
        """Generate query variations by substituting words with their synonyms.

        Args:
            original_query (str): The original query.
            tokens (List[str]): The tokens to generate variations from.
            expandable_words (List[tuple[int, str]]): The expandable words.
            max_alts (int): The maximum number of alternatives to generate.

        Returns:
            List[str]: A list of queries, with the original query as the first item.
        """
        variations = set()
        variations.add(original_query)  # Always include original

        # Try expanding the first few expandable words
        for idx, word in expandable_words[:2]:  # Limit to first 2 words
            synonyms = self._get_word_synonyms(word)

            # Create variations by replacing the word
            for synonym in list(synonyms)[:max_alts]:
                new_tokens = tokens.copy()
                new_tokens[idx] = synonym
                variations.add(" ".join(new_tokens))

                if len(variations) >= max_alts + 1:
                    break

        # Convert to list, ensuring original is first
        result = [original_query]
        for var in variations:
            if var != original_query:
                result.append(var)
                if len(result) >= max_alts + 1:
                    break

        return result

    # LLM-based expansion
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

        # Define Pydantic model for structured output
        class QueryExpansions(BaseModel):
            alternatives: List[str] = Field(
                description="List of alternative phrasings for the search query",
                min_items=1,
                max_items=max_alts,
            )

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
