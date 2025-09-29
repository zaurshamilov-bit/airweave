"""Search operations module with dynamic provider selection.

This module exports operation classes, selecting implementations based on
available API keys at import time. Defaults favor OpenAI to keep the
open-source experience seamless without paid keys.

Selection policy:
- Reranking: Cohere → Groq → OpenAI
- Other ops (expansion, interpretation, completion): Groq → OpenAI
"""

from airweave.core.config import settings
from airweave.search.operations.base import SearchOperation

# Always-available operations
from airweave.search.operations.embedding import Embedding
from airweave.search.operations.qdrant_filter import QdrantFilterOperation
from airweave.search.operations.recency_bias import RecencyBias
from airweave.search.operations.vector_search import VectorSearch

# Feature flags based on env
_HAS_GROQ = bool(getattr(settings, "GROQ_API_KEY", None))
_HAS_COHERE = bool(getattr(settings, "COHERE_API_KEY", None))

# Completion: prefer Groq, otherwise OpenAI
if _HAS_GROQ:
    from airweave.search.operations.completion_groq import CompletionGeneration  # type: ignore
else:
    from airweave.search.operations.completion import CompletionGeneration  # type: ignore

# Query Expansion: prefer Groq, otherwise OpenAI
if _HAS_GROQ:
    from airweave.search.operations.query_expansion_groq import QueryExpansion  # type: ignore
else:
    from airweave.search.operations.query_expansion import QueryExpansion  # type: ignore

# Query Interpretation: prefer Groq, otherwise OpenAI
if _HAS_GROQ:
    from airweave.search.operations.query_interpretation_groq import (
        QueryInterpretation,
    )  # type: ignore
else:
    from airweave.search.operations.query_interpretation import (
        QueryInterpretation,
    )  # type: ignore

# Reranking: prefer Cohere, else Groq, else OpenAI
if _HAS_COHERE:
    from airweave.search.operations.reranking_cohere import LLMReranking  # type: ignore
elif _HAS_GROQ:
    from airweave.search.operations.reranking_groq import LLMReranking  # type: ignore
else:
    from airweave.search.operations.reranking import LLMReranking  # type: ignore

__all__ = [
    # Base class
    "SearchOperation",
    # Core operations
    "QueryExpansion",
    "QueryInterpretation",
    "QdrantFilterOperation",
    "Embedding",
    "VectorSearch",
    "RecencyBias",
    # Reranking
    "LLMReranking",
    # Completion
    "CompletionGeneration",
]
