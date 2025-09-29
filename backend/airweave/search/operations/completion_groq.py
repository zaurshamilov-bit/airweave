"""AI completion generation operation.

This operation generates natural language answers from search
results using large language models.
"""

from typing import Any, Dict, List, Optional

from groq import AsyncGroq

from airweave.core.config import settings
from airweave.search.operations.base import SearchOperation

# Default prompt for completion generation
CONTEXT_PROMPT = """You are an AI assistant that synthesizes an accurate, helpful answer from
retrieved context. Your job is to:
1) Read the provided context snippets
2) Weigh their relevance using the provided similarity Score (higher = more relevant)
3) Compose a clear, well-structured answer that cites only the sources you actually used

Important retrieval note:
- The context is produced by a hybrid keyword + vector (semantic) search.
- High similarity means "related", but it does NOT guarantee that an item satisfies
  the user's constraints. You must verify constraints explicitly using evidence in
  the snippet's fields/content.

When the user asks to FIND/LIST/SHOW entities with constraints:
- Recognize find/list intent. Prefer list-mode when the query includes terms like
  "find", "list", "show", "who are", "which people", or specifies role/company/location
  constraints.
- If the intent is ambiguous but the query specifies entity attributes (role, company, location,
  skills, etc.), default to list-mode and apply strict constraint checking.
- Return as many matching items as possible from the provided context; do not summarize to a few.
- Apply strict, conservative constraint checking (AND semantics for all constraints):
  - Accept an item only if evidence for each constraint is explicit and unambiguous in the snippet
    (e.g., role/title, employer type, and location are clearly stated).
  - Exclude false positives and loose associations.
  - If evidence is missing or ambiguous for any constraint, exclude the item rather than guessing.
- Output format for such queries:
  - Bullet list with one line per matching item.
  - Include a minimal identifying label (e.g., name/title) and a short justification citing the
    decisive evidence (role/company/location, etc.). Add an inline source reference [[entity_id]].
  - Do not cap the number of items; list all matches present in the provided context.
  - Start with a line like: "Matches found: N" where N is the number of items you list.

For general explanatory/text questions (summaries, how-tos, overviews):
- Synthesize a concise, direct answer using the most relevant snippets.

IMPORTANT: When you use information from the context, you MUST reference the source using
the format [[entity_id]] immediately after the information. These references will be rendered
as clickable links in the interface. Only reference sources you actually used in your answer.
If you're not sure or didn't use a source, don't reference it.

DO NOT include "Answer" or any similar header at the beginning of your response. Start directly
with the content of your answer.

Always format your responses in proper markdown:
- For tables, use proper markdown table syntax:
  | Column 1 | Column 2 |
  |----------|----------|
  | Value 1  | Value 2  |
- Use headers sparingly for complex information (## for sections, ### for subsections)
- Format code with ```language blocks
- Use **bold** for emphasis and *italic* for subtle emphasis
- Use bullet points (- or •) or numbered lists (1. 2. 3.) for lists
- Source references using [[entity_id]] format inline with the text

Here's the context with entity IDs:
{context}

Remember to:
1. Start your response directly with the answer, no introductory headers
2. Be concise and direct
3. Use proper markdown table syntax when presenting tabular data
4. Include source references [[entity_id]] inline where you use the information
5. Prefer higher-Score results when sources conflict
6. If listing sources at the end, use a "Sources:" section with bullet points

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
        self,
        default_model: str = "openai/gpt-oss-120b",
        max_results_context: int = 100,
        max_tokens: int = 10000,
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

    async def execute(self, context: Dict[str, Any]) -> None:  # noqa: C901 - controlled complexity
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
        import time

        start_time = time.time()

        # Get results - prefer final_results if reranking ran
        results = context.get("final_results", context.get("raw_results", []))
        query = context["query"]
        config = context["config"]
        logger = context["logger"]
        groq_api_key = getattr(settings, "GROQ_API_KEY", None)

        logger.debug(f"[CompletionGeneration] Started at {time.time() - start_time:.2f}s")

        if not results:
            context["completion"] = "No results found for your query."
            logger.debug("[CompletionGeneration] No results to generate completion from")
            return

        if not groq_api_key:
            # Fail-fast policy: completion requires GROQ_API_KEY
            raise RuntimeError("CompletionGeneration requires GROQ_API_KEY but none is configured")

        # Limit results for context to avoid token limits
        results_for_context = results[: self.max_results_context]
        model = (
            config.completion_model if hasattr(config, "completion_model") else self.default_model
        )

        logger.debug(
            f"[CompletionGeneration] Generating completion from {len(results_for_context)} results "
            f"using model {model}"
        )

        try:
            # Initialize Groq client (reads GROQ_API_KEY from environment)
            client_init_time = time.time()
            client = AsyncGroq()
            logger.debug(
                f"[CompletionGeneration] Groq client initialized in "
                f"{(time.time() - client_init_time) * 1000:.2f}ms"
            )

            # Format results for context with large token budget (≈120k)
            format_start = time.time()
            formatted_context, chosen_count = self._format_results_with_budget(
                results_for_context, query
            )
            format_time = (time.time() - format_start) * 1000

            total_results = len(results_for_context)
            context_chars = len(formatted_context)
            logger.debug(
                f"[CompletionGeneration] Formatted {chosen_count}/{total_results} "
                f"results in {format_time:.2f}ms. "
                f"Context length: {context_chars} chars"
            )

            # Prepare messages (shared for streaming and non-streaming)
            messages = [
                {"role": "system", "content": CONTEXT_PROMPT.format(context=formatted_context)},
                {"role": "user", "content": query},
            ]

            # Calculate approximate token count (rough estimate)
            estimated_tokens = (
                self._estimate_tokens(CONTEXT_PROMPT)
                + self._estimate_tokens(query)
                + self._estimate_tokens(formatted_context)
            )
            logger.debug(
                f"[CompletionGeneration] Estimated input tokens: ~{estimated_tokens:.0f} "
                "(budget ≈120k)"
            )

            # Streaming or non-streaming completion
            request_id: Optional[str] = context.get("request_id")
            api_start = time.time()
            logger.debug(f"[CompletionGeneration] Calling Groq API with model {model}...")

            if request_id:
                emitter = context.get("emit")
                if callable(emitter):
                    await emitter("completion_start", {"model": model}, op_name=self.name)

                full_text_parts: List[str] = []
                stream = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_completion_tokens=self.max_tokens,
                    top_p=1,
                    stream=True,
                )
                async for chunk in stream:  # type: ignore
                    try:
                        delta = chunk.choices[0].delta.content  # type: ignore[attr-defined]
                    except Exception:
                        delta = None
                    if isinstance(delta, str) and delta:
                        full_text_parts.append(delta)
                        emitter = context.get("emit")
                        if callable(emitter):
                            try:
                                await emitter(
                                    "completion_delta", {"text": delta}, op_name=self.name
                                )
                            except Exception:
                                pass

                final_text = "".join(full_text_parts)
                context["completion"] = final_text
                emitter = context.get("emit")
                if callable(emitter):
                    await emitter("completion_done", {"text": final_text}, op_name=self.name)
                api_time = (time.time() - api_start) * 1000
                logger.debug(f"[CompletionGeneration] Groq streaming completed in {api_time:.2f}ms")
            else:
                # Use Groq Chat Completions for non-streaming
                try:
                    logger.debug(
                        f"[CompletionGeneration] input: {model} {messages} {self.max_tokens}"
                    )
                    chat_response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_completion_tokens=self.max_tokens,
                    )

                    api_time = (time.time() - api_start) * 1000
                    logger.debug(
                        f"[CompletionGeneration] Groq Chat API call completed in {api_time:.2f}ms"
                    )

                    text: Optional[str] = None
                    try:
                        if getattr(chat_response, "choices", None):
                            msg = chat_response.choices[0].message
                            text = getattr(msg, "content", None)
                    except Exception:
                        text = None

                    if text and isinstance(text, str) and text.strip():
                        context["completion"] = text
                        total_time = (time.time() - start_time) * 1000
                        logger.debug(
                            f"[CompletionGeneration] Successfully generated completion. "
                            f"Total time: {total_time:.2f}ms (API: {api_time:.2f}ms, "
                            f"formatting: {format_time:.2f}ms)"
                        )
                    else:
                        context["completion"] = (
                            "Unable to generate completion from the search results."
                        )
                        logger.debug(
                            "[CompletionGeneration] Chat Completions returned empty content"
                        )
                        try:
                            logger.debug(f"[CompletionGeneration] Response: {chat_response}")
                        except Exception:
                            pass
                except Exception as resp_err:
                    logger.error(
                        f"[CompletionGeneration] Chat Completions failed: {resp_err}",
                        exc_info=True,
                    )
                    raise

        except Exception as e:
            logger.error(f"[CompletionGeneration] Failed: {e}", exc_info=True)
            # Propagate to fail the search per policy
            raise

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

    def _format_results_with_budget(self, results: List[Dict], query: str) -> tuple[str, int]:
        """Format results while respecting a large token budget (~120k).

        This mirrors the budgeting approach used in reranking to avoid exceeding
        the context window while still maximizing useful context sent to the LLM.

        Args:
            results: Search results to format
            query: Original user query (counted toward token budget)

        Returns:
            A tuple of (formatted_context, chosen_count)
        """
        if not results:
            return "No search results available.", 0

        MAX_CONTEXT_TOKENS = 120_000
        SAFETY_TOKENS = 2_000

        separator = "\n\n---\n\n"

        static_tokens = self._estimate_tokens(CONTEXT_PROMPT) + self._estimate_tokens(query)
        running_tokens = static_tokens

        chosen_parts: List[str] = []
        chosen_count = 0

        for i, result in enumerate(results, 1):
            part = self._format_single_result(i, result)
            need_tokens = self._estimate_tokens(part)
            sep_tokens = self._estimate_tokens(separator) if i > 1 else 0
            if running_tokens + need_tokens + sep_tokens + SAFETY_TOKENS <= MAX_CONTEXT_TOKENS:
                if i > 1:
                    chosen_parts.append(separator)
                chosen_parts.append(part)
                running_tokens += need_tokens + sep_tokens
                chosen_count += 1
            else:
                break

        if not chosen_parts:
            # Always include at least the first result if available and fits with safety
            first_part = self._format_single_result(1, results[0])
            if (
                static_tokens + self._estimate_tokens(first_part) + SAFETY_TOKENS
                <= MAX_CONTEXT_TOKENS
            ):
                return first_part, 1
            return "No search results available within token budget.", 0

        return "".join(chosen_parts), chosen_count

    def _estimate_tokens(self, text: str) -> int:
        """Roughly estimate token count from text length.

        Uses a 4 chars ≈ 1 token heuristic consistent with other modules.
        """
        try:
            return int(len(text) / 4)
        except Exception:
            try:
                return int(float(len(text)) / 4)
            except Exception:
                return len(text) // 4

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
        # Prefer embeddable_text; otherwise fall back to md_content; otherwise to other fields.
        # Avoid duplication when both exist.
        embeddable_text = payload.get("embeddable_text", "").strip()
        if embeddable_text:
            parts.append(f"**Embeddable Text:**\n{embeddable_text}")
            return

        md_content = payload.get("md_content", "").strip()
        if md_content:
            parts.append(f"**Content:**\n{md_content}")
            return

        content = payload.get("content") or payload.get("text") or payload.get("description", "")
        if content:
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
