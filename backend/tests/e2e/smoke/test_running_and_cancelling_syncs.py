"""
Async test module for running and cancelling sync jobs.

Tests comprehensive sync job lifecycle including state transitions,
concurrent run prevention, and cancellation scenarios.
"""

import pytest
import httpx
import asyncio
from typing import Dict, Optional


class TestRunningAndCancellingSyncs:
    """Test suite for sync job lifecycle management."""

    async def _wait_for_job_status(
        self,
        api_client: httpx.AsyncClient,
        conn_id: str,
        job_id: str,
        expected_status: str,
        timeout: int = 30,
    ) -> Optional[Dict]:
        """Wait for a job to reach a specific status.

        Args:
            api_client: HTTP client
            conn_id: Source connection ID
            job_id: Job ID to monitor
            expected_status: Status to wait for
            timeout: Maximum wait time in seconds

        Returns:
            Job dict if status reached, None if timeout
        """
        elapsed = 0
        poll_interval = 2

        while elapsed < timeout:
            response = await api_client.get(f"/source-connections/{conn_id}/jobs")
            if response.status_code == 200:
                jobs = response.json()
                job = next((j for j in jobs if j["id"] == job_id), None)
                if job and job["status"] == expected_status:
                    return job

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        return None

    # ============= BASIC RUNNING TESTS =============

    @pytest.mark.asyncio
    async def test_run_sync_job(self, api_client: httpx.AsyncClient, source_connection_fast: Dict):
        """Test basic sync job execution."""
        conn_id = source_connection_fast["id"]

        # Trigger a sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200

        job = response.json()
        assert "id" in job
        assert job["status"] in ["pending", "running"]

        # Wait a bit and check status
        await asyncio.sleep(3)

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200

        connection = response.json()
        assert connection["sync"]["last_job"]["id"] == job["id"]

    @pytest.mark.asyncio
    async def test_cannot_run_while_already_running(
        self, api_client: httpx.AsyncClient, source_connection_medium: Dict
    ):
        """Test that starting a new sync while one is running is prevented."""
        conn_id = source_connection_medium["id"]

        # Start first sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        first_job = response.json()

        # Wait for it to start running
        await asyncio.sleep(2)

        # Try to start second sync - should fail
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 400

        error = response.json()
        assert (
            "already running" in error["detail"].lower()
            or "already pending" in error["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_can_run_after_completion(
        self, api_client: httpx.AsyncClient, source_connection_fast: Dict
    ):
        """Test that a new sync can be started after previous one completes."""
        conn_id = source_connection_fast["id"]

        # Run first sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        first_job = response.json()

        # Wait for completion (fast source should complete quickly)
        completed = await self._wait_for_job_status(
            api_client, conn_id, first_job["id"], "completed", timeout=30
        )
        assert completed is not None, "First job should complete"

        # Now run second sync - should succeed
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        second_job = response.json()

        assert second_job["id"] != first_job["id"]

    # ============= CANCELLATION TESTS =============

    @pytest.mark.asyncio
    async def test_cancel_running_sync_job(
        self, api_client: httpx.AsyncClient, source_connection_medium: Dict
    ):
        """Test cancelling an in-progress sync job."""
        conn_id = source_connection_medium["id"]

        # Trigger a sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200

        job = response.json()
        job_id = job["id"]

        # Wait for sync to start running
        await asyncio.sleep(2)

        # Cancel the sync job
        response = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        assert response.status_code == 200

        # Check immediate status - should be cancelling
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        assert response.status_code == 200

        jobs = response.json()
        our_job = next((j for j in jobs if j["id"] == job_id), None)
        assert our_job is not None
        assert our_job["status"] == "cancelling"

        # Wait for cancellation to complete
        cancelled = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=20
        )
        assert cancelled is not None, "Job should be cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_non_existent_job(self, api_client: httpx.AsyncClient):
        """Test cancelling a non-existent job returns 404."""
        fake_job_id = "00000000-0000-0000-0000-000000000000"
        fake_conn_id = "00000000-0000-0000-0000-000000000001"

        response = await api_client.post(
            f"/source-connections/{fake_conn_id}/jobs/{fake_job_id}/cancel"
        )

        # Should return 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_job(
        self, api_client: httpx.AsyncClient, source_connection_fast: Dict
    ):
        """Test that cancelling an already completed job is rejected."""
        conn_id = source_connection_fast["id"]

        # Run sync to completion
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait for completion
        completed = await self._wait_for_job_status(
            api_client, conn_id, job_id, "completed", timeout=30
        )
        assert completed is not None, "Job should complete"
        assert completed["entities_inserted"] >= 0

        # Try to cancel completed job - should fail
        response = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        assert response.status_code == 400

        error = response.json()
        assert (
            "already completed" in error["detail"].lower()
            or "cannot cancel" in error["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_cannot_cancel_if_nothing_running(
        self, api_client: httpx.AsyncClient, source_connection_fast: Dict
    ):
        """Test that cancellation fails when no job is running."""
        conn_id = source_connection_fast["id"]

        # Try to cancel without any job running
        fake_job_id = "00000000-0000-0000-0000-000000000000"
        response = await api_client.post(f"/source-connections/{conn_id}/jobs/{fake_job_id}/cancel")

        # Should return 404 since job doesn't exist
        assert response.status_code == 404

    # ============= STATE TRANSITION TESTS =============

    @pytest.mark.asyncio
    async def test_cannot_run_while_in_cancelling_state(
        self, api_client: httpx.AsyncClient, source_connection_medium: Dict
    ):
        """Test that new sync cannot start while another is being cancelled."""
        conn_id = source_connection_medium["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait for it to start
        await asyncio.sleep(2)

        # Cancel it
        response = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        assert response.status_code == 200

        # Immediately try to start new sync while cancelling
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 400

        error = response.json()
        # The error message format is "Cannot start new sync: a sync job is already {status}"
        # where status can be "running", "pending", or "cancelling"
        error_detail = error["detail"].lower()
        assert "a sync job is already" in error_detail and (
            "running" in error_detail or "cancelling" in error_detail or "pending" in error_detail
        )

        # Wait for cancellation to complete
        await self._wait_for_job_status(api_client, conn_id, job_id, "cancelled", timeout=20)

        # Now should be able to run
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_job_state_transitions(
        self, api_client: httpx.AsyncClient, source_connection_fast: Dict
    ):
        """Test that job goes through expected state transitions."""
        conn_id = source_connection_fast["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Should start as pending
        assert job["status"] == "pending"

        # Wait and check for running state
        await asyncio.sleep(2)
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        jobs = response.json()
        job = next((j for j in jobs if j["id"] == job_id), None)

        assert job is not None
        assert job["status"] in [
            "pending",
            "running",
            "completed",
        ]  # Fast source might already complete

        # Wait for completion
        completed = await self._wait_for_job_status(
            api_client, conn_id, job_id, "completed", timeout=30
        )
        assert completed is not None
        assert completed["status"] == "completed"
        assert "started_at" in completed
        assert "completed_at" in completed

    # ============= CONCURRENT OPERATIONS TESTS =============

    @pytest.mark.asyncio
    async def test_multiple_cancel_requests(
        self, api_client: httpx.AsyncClient, source_connection_medium: Dict
    ):
        """Test that multiple cancel requests for same job are handled gracefully."""
        conn_id = source_connection_medium["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait for it to start
        await asyncio.sleep(2)

        # Send multiple cancel requests
        response1 = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        response2 = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        response3 = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")

        # First should succeed
        assert response1.status_code == 200

        # Others should either succeed (idempotent) or return appropriate error
        assert response2.status_code in [200, 400]
        assert response3.status_code in [200, 400]

    # ============= TEMPORAL-SPECIFIC TESTS =============

    @pytest.mark.requires_temporal
    @pytest.mark.asyncio
    async def test_cancel_temporal_workflow(
        self, api_client: httpx.AsyncClient, source_connection_medium: Dict, config
    ):
        """Test that cancellation properly cancels Temporal workflow."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = source_connection_medium["id"]

        # Start sync
        response = await api_client.post(f"/source-connections/{conn_id}/run")
        assert response.status_code == 200
        job = response.json()
        job_id = job["id"]

        # Wait for workflow to start
        await asyncio.sleep(3)

        # Cancel via API
        response = await api_client.post(f"/source-connections/{conn_id}/jobs/{job_id}/cancel")
        assert response.status_code == 200

        # Check Temporal workflow status (would need Temporal client integration)
        # For now, just verify job status changes
        cancelled = await self._wait_for_job_status(
            api_client, conn_id, job_id, "cancelled", timeout=20
        )
        assert cancelled is not None
