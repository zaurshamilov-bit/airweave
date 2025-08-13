"""LLM-based reranking operation.

This module contains the LLM reranking operation that uses OpenAI
to reorder search results based on relevance to the original query.
"""

from typing import Any, Dict, List

from airweave.search.operations.base import SearchOperation


class LLMReranking(SearchOperation):
    """Rerank search results using LLM.

    This operation sends the search results and the original query to
    OpenAI and asks the LLM to rerank the results to ensure the most
    relevant results appear at the top.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize LLM reranking.

        Args:
            model: OpenAI model to use for reranking
        """
        self.model = model

    @property
    def name(self) -> str:
        """Operation name."""
        return "llm_reranking"

    @property
    def depends_on(self) -> List[str]:
        """Reranking depends on vector search."""
        return ["vector_search"]

    async def execute(self, context: Dict[str, Any]) -> None:
        """Execute LLM-based reranking.

        Reads from context:
            - raw_results: Initial search results
            - query: Original search query
            - config: SearchConfig
            - logger: For logging
            - openai_api_key: API key for OpenAI

        Writes to context:
            - final_results: Reranked and limited results
        """
        from openai import AsyncOpenAI
        from pydantic import BaseModel, Field

        results = context.get("raw_results", [])
        query = context["query"]
        config = context["config"]
        logger = context["logger"]
        openai_api_key = context.get("openai_api_key")

        if not results:
            context["final_results"] = []
            logger.info(f"[{self.name}] No results to rerank")
            return

        if not openai_api_key:
            # If no API key, just use original results
            context["final_results"] = results[: config.limit]
            logger.warning(f"[{self.name}] No OpenAI API key, using original order")
            return

        logger.info(f"[{self.name}] Reranking {len(results)} results using LLM")

        try:
            # Prepare results for LLM with indices
            results_for_llm = []
            for i, result in enumerate(results[:20]):  # Limit to top 20 for LLM
                payload = result.get("payload", {})
                content = (
                    payload.get("md_content")
                    or payload.get("content")
                    or payload.get("text", "")
                    or payload.get("embeddable_text", "")
                )[:500]  # Truncate content

                results_for_llm.append(
                    {
                        "index": i,
                        "source": payload.get("source_name", "Unknown"),
                        "title": payload.get("title", "Untitled"),
                        "content": content,
                        "score": result.get("score", 0),
                    }
                )

            # Define structured output for reranking
            class RankedResult(BaseModel):
                index: int = Field(description="Original index of the result")
                relevance_score: float = Field(
                    ge=0.0, le=1.0, description="Relevance score from 0 to 1"
                )
                reasoning: str = Field(description="Brief explanation for the ranking")

            class RerankedResults(BaseModel):
                rankings: List[RankedResult] = Field(
                    description="Results ordered by relevance, most relevant first"
                )

            # Create OpenAI client
            client = AsyncOpenAI(api_key=openai_api_key)

            # Create prompt
            system_prompt = (
                "You are a search result reranking expert. Your task is to reorder search "
                "results based on their relevance to the user's query.\n\n"
                "Use the vector similarity score as one helpful signal, but do not rely on it "
                "exclusively.\n"
                "- Prioritize direct topical relevance to the user's query\n"
                "- Prefer higher quality, complete, and specific information over vague or "
                "boilerplate text\n"
                "- Consider source reliability and authoritativeness\n"
                "- When items are equally relevant, the higher vector score should break ties\n\n"
                "Only rerank when it improves relevance. If the initial order already reflects "
                "the best results, keep the order unchanged.\n\n"
                "Return results ordered from most to least relevant."
            )

            user_prompt = f"""Query: {query}

Search Results:
{self._format_results_for_prompt(results_for_llm)}

Please rerank these results from most to least relevant to the query."""

            # Get reranking from LLM
            response = await client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=RerankedResults,
                temperature=0.3,
            )

            if response.choices[0].message.parsed:
                reranked = response.choices[0].message.parsed

                # Reorder results based on LLM ranking
                final_results = []
                for ranked_item in reranked.rankings:
                    if ranked_item.index < len(results):
                        final_results.append(results[ranked_item.index])
                        logger.debug(
                            f"[{self.name}] Ranked position {len(final_results)}: "
                            f"index={ranked_item.index}, score={ranked_item.relevance_score:.2f}, "
                            f"reason={ranked_item.reasoning[:50]}..."
                        )

                # Add any remaining results that weren't ranked
                ranked_indices = {r.index for r in reranked.rankings}
                for i, result in enumerate(results):
                    if i not in ranked_indices and len(final_results) < config.limit:
                        final_results.append(result)

                context["final_results"] = final_results[: config.limit]
                logger.info(
                    f"[{self.name}] Successfully reranked to "
                    f"{len(context['final_results'])} results"
                )
            else:
                # Fallback to original order
                context["final_results"] = results[: config.limit]
                logger.warning(f"[{self.name}] No reranking received, using original order")

        except Exception as e:
            logger.error(f"[{self.name}] Failed: {e}", exc_info=True)
            # Use original results on error
            context["final_results"] = results[: config.limit]

    def _format_results_for_prompt(self, results: List[Dict]) -> str:
        """Format results for the LLM prompt.

        Args:
            results: List of result dictionaries with index, source, title, content

        Returns:
            Formatted string for the prompt
        """
        formatted = []
        for r in results:
            formatted.append(
                f"[{r['index']}] Source: {r['source']}, Title: {r['title']}\n"
                f"Content: {r['content']}\n"
                f"Original Score: {r['score']:.3f}"
            )
        return "\n\n".join(formatted)
