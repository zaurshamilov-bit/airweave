"""Schemas for search operations.

Search is the core functionality that makes Airweave powerful - enabling unified
queries across multiple data sources within collections. These schemas define
the search request and response formats for both raw search results and
AI-generated completions.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field
from qdrant_client.http.models import Filter as QdrantFilter


class ResponseType(str, Enum):
    """Response format options for search results."""

    RAW = "raw"
    COMPLETION = "completion"


class QueryExpansionStrategy(str, Enum):
    """Query expansion strategies for search."""

    AUTO = "auto"
    LLM = "llm"
    NO_EXPANSION = "no_expansion"


class SearchStatus(str, Enum):
    """Status indicators for search operation outcomes."""

    SUCCESS = "success"
    NO_RELEVANT_RESULTS = "no_relevant_results"
    NO_RESULTS = "no_results"


class QueryExpansions(BaseModel):
    """Structured output for LLM-based query expansions."""

    alternatives: List[str] = Field(
        description="List of alternative phrasings for the search query",
        min_items=1,
        max_items=10,
    )


class SearchRequest(BaseModel):
    """Comprehensive search request encapsulating all search parameters."""

    # Core search parameters
    query: str = Field(
        ...,
        description="The search query text",
        min_length=1,
        max_length=1000,
        examples=["customer payment issues", "Q4 revenue trends", "support tickets about billing"],
    )

    # Qdrant native filter support
    filter: Optional[QdrantFilter] = Field(
        None, description="Qdrant native filter for metadata-based filtering"
    )

    # Pagination
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")

    limit: Optional[int] = Field(
        20, ge=1, le=100, description="Maximum number of results to return"
    )

    # Search quality parameters
    score_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Minimum similarity score threshold"
    )

    # Result options
    summarize: Optional[bool] = Field(False, description="Whether to summarize results")

    # Response configuration
    response_type: ResponseType = Field(
        ResponseType.RAW, description="Type of response (raw or completion)"
    )

    expansion_strategy: QueryExpansionStrategy = Field(
        QueryExpansionStrategy.AUTO,
        description="Query expansion strategy. Enhances recall by expanding the query with "
        "synonyms, related terms, and other variations, but increases latency.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "customer payment issues",
                    "filter": {
                        "must": [
                            {"key": "source_name", "match": {"value": "Stripe"}},
                            {"key": "created_at", "range": {"gte": "2024-01-01T00:00:00Z"}},
                        ]
                    },
                    "limit": 50,
                    "score_threshold": 0.7,
                    "response_type": "completion",
                }
            ]
        }
    }


class SearchResponse(BaseModel):
    """Comprehensive search response containing results and metadata."""

    results: list[dict] = Field(
        ...,
        description=(
            "Array of search result objects containing the found documents, records, "
            "or data entities."
        ),
    )
    response_type: ResponseType = Field(
        ...,
        description=(
            "Indicates whether results are raw search matches or AI-generated completions "
            "based on the found content."
        ),
    )
    completion: Optional[str] = Field(
        None,
        description=(
            "AI-generated natural language answer when response_type is 'completion'. This "
            "provides natural language answers to your query based on the content found "
            "across your connected data sources."
        ),
    )
    status: SearchStatus = Field(
        ...,
        description=(
            "Status of the search operation indicating the quality and availability of "
            "results:<br/>"
            "• **success**: Search found relevant results matching your query<br/>"
            "• **no_relevant_results**: Search completed but found no sufficiently "
            "relevant matches<br/>"
            "• **no_results**: Search found no results at all, possibly indicating empty "
            "collections or very specific queries"
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "id": "stripe_cust_1234567890",
                            "title": "Customer Payment Record",
                            "content": (
                                "Monthly subscription payment of $99.00 processed successfully for "
                                "customer John Doe (john@company.com). Payment method: Visa ending "
                                "in 4242."
                            ),
                            "source": "stripe",
                            "score": 0.92,
                            "metadata": {
                                "date": "2024-01-15T10:30:00Z",
                                "type": "payment",
                                "amount": 99.00,
                                "currency": "USD",
                            },
                        },
                        {
                            "id": "zendesk_ticket_789",
                            "title": "Billing Question - Subscription Upgrade",
                            "content": (
                                "Customer inquiry about upgrading from Basic to Pro plan. Customer "
                                "mentioned they need advanced analytics features."
                            ),
                            "source": "zendesk",
                            "score": 0.87,
                            "metadata": {
                                "date": "2024-01-14T14:22:00Z",
                                "type": "support_ticket",
                                "status": "resolved",
                                "priority": "medium",
                            },
                        },
                    ],
                    "response_type": "completion",
                    "completion": (
                        "Based on your recent data, customer John Doe successfully processed a $99 "
                        "monthly subscription payment on January 15th. There was also a related "
                        "support ticket from January 14th where a customer inquired about "
                        "upgrading from Basic to Pro plan for advanced analytics features. This "
                        "suggests strong customer engagement with your premium offerings."
                    ),
                    "status": "success",
                }
            ]
        }
    }
