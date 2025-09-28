"""
Async test module for Search functionality.

Tests collection search functionality including:
- RAW search response with results and scores
- COMPLETION search response with AI-generated answers
- Advanced search features
"""

import pytest
import httpx
import asyncio
import json


class TestSearch:
    """Test suite for search functionality.

    Uses a module-scoped Stripe source connection that's loaded once and shared
    across all tests in this module for efficiency.
    """

    @pytest.mark.asyncio
    async def test_basic_search_raw(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test RAW search response using Stripe data."""
        search_query = "Are there any open invoices"

        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": search_query, "response_type": "raw"},
            timeout=90,
        )

        assert response.status_code == 200, f"Search failed: {response.text}"

        raw_results = response.json()
        assert "results" in raw_results
        assert "response_type" in raw_results
        assert "status" in raw_results
        assert raw_results["response_type"] == "raw"

        results_list = raw_results.get("results", [])
        status = raw_results.get("status", "")

        if status == "success" and len(results_list) > 0:
            # Validate result structure
            first_result = results_list[0]
            assert "payload" in first_result
            assert "score" in first_result

    @pytest.mark.asyncio
    async def test_search_completion(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test COMPLETION search response using Stripe data."""
        search_query = "Are there any open invoices"

        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": search_query, "response_type": "completion"},
            timeout=90,
        )

        assert response.status_code == 200

        completion_results = response.json()
        assert "response_type" in completion_results
        assert "status" in completion_results
        assert completion_results["response_type"] == "completion"

        if completion_results["status"] == "success":
            assert "completion" in completion_results
            assert completion_results["completion"]  # Should have content

    @pytest.mark.asyncio
    async def test_query_expansion_auto(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test AUTO query expansion with Stripe data."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "invoice", "response_type": "raw", "expansion_strategy": "auto"},
        )

        assert response.status_code == 200
        results = response.json()
        assert results["status"] in ["success", "no_results", "no_relevant_results"]

    @pytest.mark.asyncio
    async def test_query_interpretation(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test natural language query interpretation with Stripe data."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={
                "query": "find invoices from last month",
                "response_type": "raw",
                "enable_query_interpretation": True,
            },
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    @pytest.mark.asyncio
    async def test_reranking(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test LLM reranking with Stripe data."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={
                "query": "important invoices",
                "response_type": "raw",
                "enable_reranking": True,
            },
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    @pytest.mark.asyncio
    async def test_recency_bias(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test recency bias in search with Stripe data."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "recent activity", "response_type": "raw", "recency_bias": 0.8},
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    @pytest.mark.asyncio
    async def test_search_methods(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test different search methods with Stripe data."""
        methods = ["hybrid", "neural", "keyword"]

        for method in methods:
            response = await api_client.get(
                f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
                params={
                    "query": "payment OR invoice",
                    "response_type": "raw",
                    "search_method": method,
                },
                timeout=90,
            )

            assert response.status_code == 200
            results = response.json()
            assert "status" in results

    @pytest.mark.asyncio
    async def test_pagination(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search pagination with Stripe data."""
        # First page
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "stripe", "response_type": "raw", "limit": 5, "offset": 0},
        )

        assert response.status_code == 200
        first_page = response.json()

        # Second page
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "stripe", "response_type": "raw", "limit": 5, "offset": 5},
        )

        assert response.status_code == 200
        second_page = response.json()

        # Results should be different if we have enough data
        if first_page.get("results") and second_page.get("results"):
            first_ids = [r.get("id") for r in first_page["results"] if r.get("id")]
            second_ids = [r.get("id") for r in second_page["results"] if r.get("id")]
            # Check no overlap
            assert not set(first_ids).intersection(set(second_ids))

    @pytest.mark.asyncio
    async def test_empty_query(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test handling of empty query with Stripe collection."""
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "", "response_type": "raw"},
        )

        # Should return 422 for empty query
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_post_method(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search via POST method with Stripe data."""
        search_payload = {
            "query": "payment processing",
            "response_type": "completion",
            "expansion_strategy": "llm",
            "enable_reranking": True,
            "recency_bias": 0.5,
            "limit": 10,
        }

        response = await api_client.post(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            json=search_payload,
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()
        assert results["response_type"] == "completion"
        assert "status" in results

    @pytest.mark.asyncio
    async def test_search_with_synced_data(
        self, api_client: httpx.AsyncClient, module_source_connection_stripe: dict
    ):
        """Test search with already synced Stripe data.

        Since module_source_connection_stripe syncs on creation and waits for completion,
        we should have data available for searching.
        """
        # Search the already synced data
        response = await api_client.get(
            f"/collections/{module_source_connection_stripe['readable_collection_id']}/search",
            params={"query": "invoice OR payment OR customer", "response_type": "raw"},
            timeout=90,
        )

        assert response.status_code == 200
        results = response.json()

        # Should have some results from the initial sync
        if results["status"] == "success":
            assert len(results.get("results", [])) > 0, "Expected results from synced Stripe data"
