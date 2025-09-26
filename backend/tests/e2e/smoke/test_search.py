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


@pytest.mark.asyncio
class TestSearch:
    """Test suite for search functionality."""

    async def test_basic_search_raw(self, api_client: httpx.AsyncClient, collection: dict):
        """Test RAW search response."""
        search_query = "Are there any open invoices"

        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": search_query, "response_type": "raw"},
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

    async def test_search_completion(self, api_client: httpx.AsyncClient, collection: dict):
        """Test COMPLETION search response."""
        search_query = "Are there any open invoices"

        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": search_query, "response_type": "completion"},
        )

        assert response.status_code == 200

        completion_results = response.json()
        assert "response_type" in completion_results
        assert "status" in completion_results
        assert completion_results["response_type"] == "completion"

        if completion_results["status"] == "success":
            assert "completion" in completion_results
            assert completion_results["completion"]  # Should have content

    async def test_query_expansion_auto(self, api_client: httpx.AsyncClient, collection: dict):
        """Test AUTO query expansion."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "invoice", "response_type": "raw", "expansion_strategy": "auto"},
        )

        assert response.status_code == 200
        results = response.json()
        assert results["status"] in ["success", "no_results", "no_relevant_results"]

    async def test_query_interpretation(self, api_client: httpx.AsyncClient, collection: dict):
        """Test natural language query interpretation."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={
                "query": "find invoices from last month",
                "response_type": "raw",
                "enable_query_interpretation": True,
            },
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    async def test_reranking(self, api_client: httpx.AsyncClient, collection: dict):
        """Test LLM reranking."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={
                "query": "important invoices",
                "response_type": "raw",
                "enable_reranking": True,
            },
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    async def test_recency_bias(self, api_client: httpx.AsyncClient, collection: dict):
        """Test recency bias in search."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "recent activity", "response_type": "raw", "recency_bias": 0.8},
        )

        assert response.status_code == 200
        results = response.json()
        assert "status" in results

    async def test_search_methods(self, api_client: httpx.AsyncClient, collection: dict):
        """Test different search methods."""
        methods = ["hybrid", "neural", "keyword"]

        for method in methods:
            response = await api_client.get(
                f"/collections/{collection['readable_id']}/search",
                params={"query": "test query", "response_type": "raw", "search_method": method},
            )

            assert response.status_code == 200
            results = response.json()
            assert "status" in results

    async def test_score_threshold(self, api_client: httpx.AsyncClient, collection: dict):
        """Test score threshold filtering."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "test", "response_type": "raw", "score_threshold": 0.7},
        )

        assert response.status_code == 200
        results = response.json()

        if results["status"] == "success" and results.get("results"):
            # All results should have score >= 0.7
            for result in results["results"]:
                assert result["score"] >= 0.7

    async def test_pagination(self, api_client: httpx.AsyncClient, collection: dict):
        """Test search pagination."""
        # First page
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "test", "response_type": "raw", "limit": 5, "offset": 0},
        )

        assert response.status_code == 200
        first_page = response.json()

        # Second page
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "test", "response_type": "raw", "limit": 5, "offset": 5},
        )

        assert response.status_code == 200
        second_page = response.json()

        # Results should be different if we have enough data
        if first_page.get("results") and second_page.get("results"):
            first_ids = [r.get("id") for r in first_page["results"] if r.get("id")]
            second_ids = [r.get("id") for r in second_page["results"] if r.get("id")]
            # Check no overlap
            assert not set(first_ids).intersection(set(second_ids))

    async def test_empty_query(self, api_client: httpx.AsyncClient, collection: dict):
        """Test handling of empty query."""
        response = await api_client.get(
            f"/collections/{collection['readable_id']}/search",
            params={"query": "", "response_type": "raw"},
        )

        # Should return 422 for empty query
        assert response.status_code == 422

    async def test_search_post_method(self, api_client: httpx.AsyncClient, collection: dict):
        """Test search via POST method."""
        search_payload = {
            "query": "test query",
            "response_type": "completion",
            "expansion_strategy": "llm",
            "enable_reranking": True,
            "recency_bias": 0.5,
            "limit": 10,
        }

        response = await api_client.post(
            f"/collections/{collection['readable_id']}/search", json=search_payload
        )

        assert response.status_code == 200
        results = response.json()
        assert results["response_type"] == "completion"
        assert "status" in results

    @pytest.mark.slow
    async def test_search_after_sync(
        self, api_client: httpx.AsyncClient, source_connection: dict, config
    ):
        """Test search after data sync completes."""
        # Trigger a sync
        response = await api_client.post(f"/source-connections/{source_connection['id']}/run")

        if response.status_code == 200:
            job = response.json()

            # Wait for sync to complete (simplified - in real test would poll)
            await asyncio.sleep(10)

            # Now search the synced data
            response = await api_client.get(
                f"/collections/{source_connection['readable_collection_id']}/search",
                params={"query": "invoice OR payment OR customer", "response_type": "raw"},
            )

            assert response.status_code == 200
            results = response.json()

            # Should have some results after sync
            if results["status"] == "success":
                assert len(results.get("results", [])) > 0
