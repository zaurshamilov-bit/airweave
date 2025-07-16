"""Schemas for search operations.

Search is the core functionality that makes Airweave powerful - enabling unified
queries across multiple data sources within collections. These schemas define
the search request and response formats for both raw search results and
AI-generated completions.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """Response format options for search results."""

    RAW = "raw"
    COMPLETION = "completion"


class QueryExpansionStrategy(str, Enum):
    """Query expansion strategies for search."""

    AUTO = "auto"  # Automatically select best available strategy (try LLM, then synonym, then none)
    LLM = "llm"  # Use LLM for semantic query expansion
    SYNONYM = "synonym"  # Use WordNet synonym query expansion
    NO_EXPANSION = "no_expansion"  # No query expansion, use original query only


class SearchStatus(str, Enum):
    """Status indicators for search operation outcomes."""

    SUCCESS = "success"
    NO_RELEVANT_RESULTS = "no_relevant_results"
    NO_RESULTS = "no_results"


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
