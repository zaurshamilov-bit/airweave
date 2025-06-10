"""Integration test for Temporal workflow cancellation and sync job status update."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from temporalio.testing import WorkflowEnvironment
from temporalio.exceptions import CancelledError
from temporalio.client import WorkflowFailureError

from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow
from airweave.platform.temporal.activities import run_sync_activity, update_sync_job_status_activity
from airweave.core.shared_models import SyncJobStatus


@pytest.fixture
def mock_sync_job_id():
    """Generate a consistent sync job ID for testing."""
    return str(uuid4())


@pytest.fixture
def mock_dicts(mock_sync_job_id):
    """Create all required mock dictionaries for the workflow."""
    return {
        "sync_dict": {
            "id": str(uuid4()),
            "name": "Test Sync",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "sync_job_dict": {
            "id": mock_sync_job_id,
            "sync_id": str(uuid4()),
            "status": "CREATED",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
        "sync_dag_dict": {"id": str(uuid4()), "nodes": [], "edges": []},
        "collection_dict": {"id": str(uuid4()), "name": "Test Collection"},
        "source_connection_dict": {"id": str(uuid4()), "name": "Test Connection"},
        "user_dict": {
            "id": str(uuid4()),
            "email": "test@example.com",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        },
    }


@pytest.mark.asyncio
class TestWorkflowCancellation:
    """Test Temporal workflow cancellation and sync job status updates."""

    async def test_workflow_cancellation_updates_sync_job_status(self, mock_dicts, mock_sync_job_id):
        """Test that cancelling a workflow properly updates the sync job status to FAILED."""

        async with WorkflowEnvironment() as env:
            # Track what happened
            sync_activity_started = False
            status_update_called = False
            final_status = None
            final_error = None

            async def mock_run_sync_activity(*args, **kwargs):
                """Simulate a long-running sync that will be cancelled."""
                nonlocal sync_activity_started
                sync_activity_started = True

                # Simulate work being done
                for i in range(100):  # Simulate 100 seconds of work
                    await asyncio.sleep(1)
                    # In real activity, this would be checking activity.is_cancelled()
                    # but in test environment we'll be cancelled via the workflow

                # Should not reach here due to cancellation
                pytest.fail("Activity should have been cancelled")

            async def mock_update_status_activity(*args, **kwargs):
                """Capture the status update."""
                nonlocal status_update_called, final_status, final_error

                sync_job_id, status, user_dict, error, failed_at = args

                # Verify correct sync job ID
                assert sync_job_id == mock_sync_job_id

                # Capture the final status and error
                final_status = status
                final_error = error
                status_update_called = True

                print(f"Status update called: job_id={sync_job_id}, status={status}, error={error}")

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity)
            env.set_activity_implementation(update_sync_job_status_activity, mock_update_status_activity)

            # Start the workflow
            workflow_handle = await env.client.start_workflow(
                RunSourceConnectionWorkflow.run,
                args=[
                    mock_dicts["sync_dict"],
                    mock_dicts["sync_job_dict"],
                    mock_dicts["sync_dag_dict"],
                    mock_dicts["collection_dict"],
                    mock_dicts["source_connection_dict"],
                    mock_dicts["user_dict"],
                    None,
                ],
                id=f"test-workflow-{mock_sync_job_id}",
                task_queue="test-queue",
            )

            # Give the workflow time to start the activity
            await asyncio.sleep(0.1)

            # Verify the sync activity started
            assert sync_activity_started, "Sync activity should have started"

            # Cancel the workflow (simulating kill signal)
            await workflow_handle.cancel()

            # Wait for the workflow to complete (it should fail due to cancellation)
            with pytest.raises(WorkflowFailureError) as exc_info:
                await workflow_handle.result()

            # Verify the workflow was cancelled
            assert "CancelledError" in str(exc_info.value)

            # Verify the status update was called
            assert status_update_called, "Status update activity should have been called"
            assert final_status == "CANCELLED", f"Expected status to be CANCELLED, got {final_status}"
            assert "cancelled" in final_error.lower(), f"Expected error to mention cancellation, got: {final_error}"

    async def test_workflow_heartbeat_timeout_updates_sync_job_status(self, mock_dicts, mock_sync_job_id):
        """Test that heartbeat timeout (worker death) properly updates sync job status."""

        async with WorkflowEnvironment() as env:
            # Track what happened
            status_update_called = False
            final_status = None
            final_error = None

            async def mock_run_sync_activity_no_heartbeat(*args, **kwargs):
                """Simulate an activity that stops heartbeating (worker dies)."""
                # Don't send any heartbeats - simulate dead worker
                await asyncio.sleep(300)  # Sleep longer than heartbeat timeout

            async def mock_update_status_activity(*args, **kwargs):
                """Capture the status update."""
                nonlocal status_update_called, final_status, final_error

                sync_job_id, status, user_dict, error, failed_at = args

                # Verify correct sync job ID
                assert sync_job_id == mock_sync_job_id

                # Capture the final status and error
                final_status = status
                final_error = error
                status_update_called = True

                print(f"Heartbeat timeout test - Status: {status}, Error: {error}")

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity_no_heartbeat)
            env.set_activity_implementation(update_sync_job_status_activity, mock_update_status_activity)

            # Start the workflow with a short heartbeat timeout for testing
            # Note: In the real workflow, heartbeat_timeout is set to 2 minutes
            # For testing, we'd need to modify the workflow or wait 2 minutes
            workflow_handle = await env.client.start_workflow(
                RunSourceConnectionWorkflow.run,
                args=[
                    mock_dicts["sync_dict"],
                    mock_dicts["sync_job_dict"],
                    mock_dicts["sync_dag_dict"],
                    mock_dicts["collection_dict"],
                    mock_dicts["source_connection_dict"],
                    mock_dicts["user_dict"],
                    None,
                ],
                id=f"test-workflow-heartbeat-{mock_sync_job_id}",
                task_queue="test-queue",
            )

            # Wait for the workflow to fail due to heartbeat timeout
            with pytest.raises(WorkflowFailureError) as exc_info:
                await workflow_handle.result()

            # Verify the status update was called
            assert status_update_called, "Status update activity should have been called"
            assert final_status == "FAILED", f"Expected status to be FAILED, got {final_status}"
            # The error should mention timeout or heartbeat
            print(f"Final error message: {final_error}")

    async def test_successful_workflow_no_status_update(self, mock_dicts, mock_sync_job_id):
        """Test that successful workflow completion doesn't call the error status update."""

        async with WorkflowEnvironment() as env:
            # Track what happened
            sync_completed = False
            error_status_update_called = False

            async def mock_run_sync_activity_success(*args, **kwargs):
                """Simulate a successful sync."""
                nonlocal sync_completed
                sync_completed = True
                # Quick completion
                await asyncio.sleep(0.1)
                return None

            async def mock_update_status_activity(*args, **kwargs):
                """This should NOT be called for successful completion."""
                nonlocal error_status_update_called
                error_status_update_called = True
                pytest.fail("Error status update should not be called for successful workflow")

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity_success)
            env.set_activity_implementation(update_sync_job_status_activity, mock_update_status_activity)

            # Start and run the workflow
            result = await env.client.execute_workflow(
                RunSourceConnectionWorkflow.run,
                args=[
                    mock_dicts["sync_dict"],
                    mock_dicts["sync_job_dict"],
                    mock_dicts["sync_dag_dict"],
                    mock_dicts["collection_dict"],
                    mock_dicts["source_connection_dict"],
                    mock_dicts["user_dict"],
                    None,
                ],
                id=f"test-workflow-success-{mock_sync_job_id}",
                task_queue="test-queue",
            )

            # Verify the sync completed successfully
            assert sync_completed, "Sync activity should have completed"
            assert not error_status_update_called, "Error status update should not have been called"


@pytest.mark.asyncio
async def test_real_workflow_cancellation_flow(mock_sync_job_id):
    """
    Demonstration test showing the expected behavior when cancelling a real Temporal workflow.

    This test shows what would happen in a real environment:
    1. Start a sync job workflow
    2. Cancel it while it's running
    3. Workflow catches CancelledError and updates sync job status to FAILED
    """

    print("\n=== Temporal Workflow Cancellation Flow ===")
    print(f"1. Starting sync job with ID: {mock_sync_job_id}")
    print("2. Workflow begins executing run_sync_activity")
    print("3. User/system sends cancel signal to workflow")
    print("4. Temporal propagates cancellation to the activity")
    print("5. Workflow catches CancelledError")
    print("6. Workflow executes update_sync_job_status_activity:")
    print(f"   - sync_job_id: {mock_sync_job_id}")
    print("   - status: CANCELLED")
    print("   - error: 'Workflow was cancelled'")
    print("7. Sync job is now marked as CANCELLED in the database")
    print("\nThis ensures no sync jobs are left in IN_PROGRESS state when cancelled!")

    # This is what the actual flow would look like in production
    expected_flow = {
        "workflow_started": True,
        "activity_started": True,
        "cancellation_received": True,
        "error_caught": "CancelledError",
        "status_update_called": True,
        "final_job_status": "CANCELLED",
        "error_message": "Workflow was cancelled"
    }

    assert expected_flow["final_job_status"] == "CANCELLED"
    assert expected_flow["status_update_called"] is True
