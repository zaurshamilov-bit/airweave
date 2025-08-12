"""Search operations module.

This module exports all available search operations that can be used
to build search execution plans.
"""

from airweave.search.operations.base import SearchOperation
from airweave.search.operations.completion import CompletionGeneration
from airweave.search.operations.embedding import Embedding
from airweave.search.operations.qdrant_filter import QdrantFilterOperation
from airweave.search.operations.query_expansion import QueryExpansion
from airweave.search.operations.query_interpretation import QueryInterpretation
from airweave.search.operations.reranking import LLMReranking
from airweave.search.operations.vector_search import VectorSearch

__all__ = [
    # Base class
    "SearchOperation",
    # Core operations
    "QueryExpansion",
    "QueryInterpretation",
    "QdrantFilterOperation",
    "Embedding",
    "VectorSearch",
    # Reranking
    "LLMReranking",
    # Completion
    "CompletionGeneration",
]
