"""AI completion generation operation.

This operation generates natural language answers from search
results using large language models.
"""

from typing import Any, Dict, List

from airweave.search.operations.base import SearchOperation

# Default prompt for completion generation
CONTEXT_PROMPT = """You are an AI assistant that synthesizes an accurate, helpful answer from
retrieved context. Your job is to:
1) Read the provided context snippets
2) Weigh their relevance using the provided similarity Score (higher = more relevant)
3) Compose a clear, well-structured answer that cites only the sources you actually used

IMPORTANT: When you use information from the context, you MUST reference the source using
the format [[entity_id]] immediately after the information. Only reference sources you
actually use in your answer. If you're not sure or didn't use a source, don't reference it.

Always format your responses in proper markdown, including:
- Using proper headers (# ## ###)
- Formatting code blocks with ```language
- Using tables with | header | header |
- Using bullet points and numbered lists
- Using **bold** and *italic* where appropriate
- Source references using [[entity_id]] format

Here's the context with entity IDs:
{context}

Remember to:
1. Be helpful, clear, and accurate
2. Maintain a professional tone
3. Format ALL responses in proper markdown
4. Use tables when presenting structured data
5. Use code blocks with proper language tags
6. **Prefer higher-Score results when sources conflict or when selecting evidence**
7. **Reference sources using [[entity_id]] when you use information from them**
8. Only reference sources that you actually used to formulate your answer

If the provided context doesn't contain information to answer the query directly,
respond with 'I don't have enough information to answer that question based on the
available data.'"""


class CompletionGeneration(SearchOperation):
    """Generates AI completions from search results.

    This operation takes the search results and generates a natural
    language answer to the user's query. It formats the results as
    context for the LLM and generates a coherent response.

    The completion considers the original query and synthesizes
    information from multiple search results into a single answer.
    """

    def __init__(
        self, default_model: str = "gpt-4o", max_results_context: int = 10, max_tokens: int = 1000
    ):
        """Initialize completion generation.

        Args:
            default_model: Default OpenAI model to use
            max_results_context: Maximum number of results to include in context
            max_tokens: Maximum tokens for the completion
        """
        self.default_model = default_model
        self.max_results_context = max_results_context
        self.max_tokens = max_tokens

    @property
    def name(self) -> str:
        """Operation name."""
        return "completion"

    @property
    def depends_on(self) -> List[str]:
        """Depends on search results (either raw or reranked)."""
        # We check at runtime which results are available
        return ["vector_search", "reranking"]

    async def execute(self, context: Dict[str, Any]) -> None:
        """Generate AI completion from results.

        Reads from context:
            - query: Original user query
            - final_results or raw_results: Search results
            - config: SearchConfig for model selection
            - openai_api_key: API key for OpenAI
            - logger: For logging

        Writes to context:
            - completion: Generated natural language answer
        """
        from openai import AsyncOpenAI

        # Get results - prefer final_results if reranking ran
        results = context.get("final_results", context.get("raw_results", []))
        query = context["query"]
        config = context["config"]
        logger = context["logger"]
        openai_api_key = context.get("openai_api_key")

        if not results:
            context["completion"] = "No results found for your query."
            logger.info("[CompletionGeneration] No results to generate completion from")
            return

        if not openai_api_key:
            context["completion"] = "OpenAI API key not configured. Cannot generate completion."
            logger.warning("[CompletionGeneration] No OpenAI API key available")
            return

        # Limit results for context to avoid token limits
        results_for_context = results[: self.max_results_context]
        model = (
            config.completion_model if hasattr(config, "completion_model") else self.default_model
        )

        logger.info(
            f"[CompletionGeneration] Generating completion from {len(results_for_context)} results "
            f"using model {model}"
        )

        try:
            # Initialize OpenAI client
            client = AsyncOpenAI(api_key=openai_api_key)

            # Format results for context
            formatted_context = self._format_results(results_for_context)

            # Prepare messages
            messages = [
                {"role": "system", "content": CONTEXT_PROMPT.format(context=formatted_context)},
                {"role": "user", "content": query},
            ]

            # Generate completion
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=self.max_tokens,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )

            # Extract completion text
            if response.choices and response.choices[0].message.content:
                context["completion"] = response.choices[0].message.content
                logger.info("[CompletionGeneration] Successfully generated completion")
            else:
                context["completion"] = "Unable to generate completion from the search results."
                logger.warning("[CompletionGeneration] OpenAI returned empty completion")

        except Exception as e:
            logger.error(f"[CompletionGeneration] Failed: {e}", exc_info=True)
            context["completion"] = f"Error generating completion: {str(e)}"

    def _format_results(self, results: List[Dict]) -> str:
        """Format search results for LLM context.

        Creates a readable summary of search results that the LLM
        can use to generate its answer, including entity IDs for referencing.

        Args:
            results: Search results to format

        Returns:
            Formatted string for LLM context with entity IDs
        """
        if not results:
            return "No search results available."

        formatted_parts = []
        for i, result in enumerate(results, 1):
            formatted_part = self._format_single_result(i, result)
            formatted_parts.append(formatted_part)

        return "\n\n---\n\n".join(formatted_parts)

    def _format_single_result(self, index: int, result: Dict) -> str:
        """Format a single search result.

        Args:
            index: Result index (1-based)
            result: Single search result

        Returns:
            Formatted string for this result
        """
        # Extract payload and score
        payload, score = self._extract_payload_and_score(result)

        # Get entity_id
        entity_id = self._extract_entity_id(payload, index)

        # Build formatted entry
        parts = [f"### Result {index} - Entity ID: [[{entity_id}]] (Score: {score:.3f})"]

        # Add optional fields
        self._add_field_if_exists(parts, payload, "source_name", "Source")
        self._add_field_if_exists(parts, payload, "title", "Title")
        self._add_content_field(parts, payload)
        self._add_metadata_field(parts, payload)
        self._add_field_if_exists(parts, payload, "created_at", "Created")

        return "\n".join(parts)

    def _extract_payload_and_score(self, result: Dict) -> tuple:
        """Extract payload and score from result."""
        if isinstance(result, dict) and "payload" in result:
            return result["payload"], result.get("score", 0)
        return result, 0

    def _extract_entity_id(self, payload: Dict, index: int) -> str:
        """Extract entity ID from payload."""
        return (
            payload.get("entity_id") or payload.get("id") or payload.get("_id") or f"result_{index}"
        )

    def _add_field_if_exists(self, parts: List[str], payload: Dict, field: str, label: str):
        """Add a field to parts if it exists in payload."""
        if field in payload:
            parts.append(f"**{label}:** {payload[field]}")

    def _add_content_field(self, parts: List[str], payload: Dict):
        """Add content field to parts."""
        content = (
            payload.get("embeddable_text")  # Add this first
            or payload.get("md_content")
            or payload.get("content")
            or payload.get("text")
            or payload.get("description", "")
        )

        if content:
            # Truncate very long content
            if len(content) > 1000:
                content = content[:1000] + "..."
            parts.append(f"**Content:**\n{content}")

    def _add_metadata_field(self, parts: List[str], payload: Dict):
        """Add metadata field to parts."""
        if "metadata" in payload and isinstance(payload["metadata"], dict):
            metadata_items = []
            for key, value in payload["metadata"].items():
                if key not in ["content", "text", "description"]:  # Avoid duplicates
                    metadata_items.append(f"- {key}: {value}")

            if metadata_items:
                parts.append("**Metadata:**\n" + "\n".join(metadata_items[:5]))
