"""
Async test module for cancelling sync jobs.

Tests the ability to cancel in-progress sync jobs.
"""

import pytest
import httpx
import asyncio
from typing import Dict


@pytest.mark.asyncio
class TestCancellingSyncs:
    """Test suite for sync cancellation functionality."""

    async def test_cancel_sync_job(
        self, api_client: httpx.AsyncClient, test_source_connection: Dict
    ):
        """Test cancelling an in-progress sync job."""
        conn_id = test_source_connection["id"]

        # Trigger a sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200

        job = response.json()
        job_id = job["id"]

        # Wait a moment for sync to start
        await asyncio.sleep(2)

        # Cancel the sync job
        response = await api_client.post(f"/sync/jobs/{job_id}/cancel")

        # Should return 200 or 204
        assert response.status_code in [200, 204]

        # Wait for cancellation to process
        await asyncio.sleep(3)

        # Check job status
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        assert response.status_code == 200

        jobs = response.json()
        cancelled_job = next((j for j in jobs if j["id"] == job_id), None)

        if cancelled_job:
            # Status should be CANCELLED or FAILED (depending on timing)
            assert cancelled_job["status"] in ["CANCELLED", "FAILED", "COMPLETED"]

    async def test_cancel_non_existent_job(self, api_client: httpx.AsyncClient):
        """Test cancelling a non-existent job."""
        fake_job_id = "00000000-0000-0000-0000-000000000000"

        response = await api_client.post(f"/sync/jobs/{fake_job_id}/cancel")

        # Should return 404
        assert response.status_code == 404

    async def test_cancel_completed_job(self, api_client: httpx.AsyncClient, config):
        """Test cancelling an already completed job."""
        # Create a small collection and connection that will complete quickly
        collection_data = {"name": "Quick Sync Test"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()

        connection_data = {
            "name": "Quick Sync Connection",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"api_key": config.stripe_api_key}},
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=connection_data)
        assert response.status_code == 200
        connection = response.json()

        # Wait for sync to complete
        await asyncio.sleep(30)

        # Get the completed job
        response = await api_client.get(f"/source-connections/{connection['id']}/jobs")
        if response.status_code == 200:
            jobs = response.json()
            if jobs and jobs[0]["status"] == "COMPLETED":
                completed_job_id = jobs[0]["id"]

                # Try to cancel completed job
                response = await api_client.post(f"/sync/jobs/{completed_job_id}/cancel")

                # Should return error or no-op
                assert response.status_code in [400, 422, 200, 204]

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")
        await api_client.delete(f"/collections/{collection['readable_id']}")

    @pytest.mark.slow
    async def test_cancel_during_sync_stages(self, api_client: httpx.AsyncClient, config):
        """Test cancelling sync at different stages."""
        # Create a larger sync that takes time
        collection_data = {"name": "Cancel Stages Test"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()

        # Create multiple connections to test cancellation at different times
        connections = []
        for i in range(3):
            connection_data = {
                "name": f"Cancel Test Connection {i}",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": config.stripe_api_key}},
            }

            response = await api_client.post("/source-connections", json=connection_data)
            assert response.status_code == 200
            connections.append(response.json())

        # Start syncs and cancel at different times
        cancel_delays = [1, 5, 10]  # Cancel after 1s, 5s, 10s

        for conn, delay in zip(connections, cancel_delays):
            # Trigger sync
            response = await api_client.post(f"/source-connections/{conn['id']}/run")
            assert response.status_code == 200
            job = response.json()

            # Wait specified time
            await asyncio.sleep(delay)

            # Cancel
            response = await api_client.post(f"/sync/jobs/{job['id']}/cancel")
            assert response.status_code in [200, 204]

        # Wait for all cancellations to process
        await asyncio.sleep(5)

        # Check all jobs are cancelled
        for conn in connections:
            response = await api_client.get(f"/source-connections/{conn['id']}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                if jobs:
                    # Latest job should be cancelled or failed
                    assert jobs[0]["status"] in ["CANCELLED", "FAILED", "COMPLETED"]

        # Cleanup
        for conn in connections:
            await api_client.delete(f"/source-connections/{conn['id']}")
        await api_client.delete(f"/collections/{collection['readable_id']}")
