"""Tests for Temporal workflow error handling."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from temporalio import workflow
from temporalio.exceptions import CancelledError
from temporalio.testing import WorkflowEnvironment

from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow
from airweave.platform.temporal.activities import run_sync_activity, update_sync_job_status_activity


@pytest.fixture
def mock_sync_dict():
    """Create a mock sync dictionary."""
    return {
        "id": str(uuid4()),
        "name": "Test Sync",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_sync_job_dict():
    """Create a mock sync job dictionary."""
    return {
        "id": str(uuid4()),
        "sync_id": str(uuid4()),
        "status": "CREATED",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_user_dict():
    """Create a mock user dictionary."""
    return {
        "id": str(uuid4()),
        "email": "test@example.com",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_dicts(mock_sync_dict, mock_sync_job_dict, mock_user_dict):
    """Create all required mock dictionaries."""
    return {
        "sync_dict": mock_sync_dict,
        "sync_job_dict": mock_sync_job_dict,
        "sync_dag_dict": {"id": str(uuid4()), "nodes": [], "edges": []},
        "collection_dict": {"id": str(uuid4()), "name": "Test Collection"},
        "source_connection_dict": {"id": str(uuid4()), "name": "Test Connection"},
        "user_dict": mock_user_dict,
    }


@pytest.mark.asyncio
class TestTemporalErrorHandling:
    """Test error handling in Temporal workflows."""

    async def test_workflow_handles_activity_failure(self, mock_dicts):
        """Test that workflow handles activity failures and updates sync job status."""
        async with WorkflowEnvironment() as env:
            # Mock the activities
            run_sync_error = Exception("Sync activity failed")

            async def mock_run_sync_activity(*args, **kwargs):
                raise run_sync_error

            async def mock_update_status_activity(*args, **kwargs):
                # Verify the correct parameters are passed
                sync_job_id, status, user_dict, error, failed_at = args
                assert sync_job_id == mock_dicts["sync_job_dict"]["id"]
                assert status == "FAILED"
                assert error == str(run_sync_error)
                assert failed_at is not None
                # failed_at should be an ISO format string from workflow.now()
                # Just verify it can be parsed
                datetime.fromisoformat(failed_at)

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity)
            env.set_activity_implementation(
                update_sync_job_status_activity, mock_update_status_activity
            )

            # Run the workflow and expect it to raise
            with pytest.raises(Exception) as exc_info:
                await env.client.execute_workflow(
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
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

            assert str(exc_info.value) == str(run_sync_error)

    async def test_workflow_handles_cancellation(self, mock_dicts):
        """Test that workflow handles cancellation and updates sync job status."""
        async with WorkflowEnvironment() as env:
            # Mock the activities
            async def mock_run_sync_activity(*args, **kwargs):
                # Simulate a long-running activity that gets cancelled
                raise CancelledError("Activity was cancelled")

            status_updated = False

            async def mock_update_status_activity(*args, **kwargs):
                nonlocal status_updated
                # Verify the correct parameters are passed
                sync_job_id, status, user_dict, error, failed_at = args
                assert sync_job_id == mock_dicts["sync_job_dict"]["id"]
                assert status == "CANCELLED"
                assert "cancelled" in error.lower()
                assert failed_at is not None
                # failed_at should be an ISO format string from workflow.now()
                datetime.fromisoformat(failed_at)
                status_updated = True

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity)
            env.set_activity_implementation(
                update_sync_job_status_activity, mock_update_status_activity
            )

            # Run the workflow and expect it to raise CancelledError
            with pytest.raises(CancelledError):
                await env.client.execute_workflow(
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
                    id=f"test-workflow-{uuid4()}",
                    task_queue="test-queue",
                )

            # Verify that the status update activity was called
            assert status_updated, "Status update activity should have been called"

    async def test_workflow_success_no_status_update(self, mock_dicts):
        """Test that workflow doesn't update status on successful completion."""
        async with WorkflowEnvironment() as env:
            # Mock the activities
            async def mock_run_sync_activity_success(*args, **kwargs):
                # Successful completion
                return None

            status_updated = False

            async def mock_update_status_activity(*args, **kwargs):
                nonlocal status_updated
                status_updated = True
                # This should not be called on success
                pytest.fail("Status update should not be called on success")

            # Register mocked activities
            env.set_activity_implementation(run_sync_activity, mock_run_sync_activity_success)
            env.set_activity_implementation(
                update_sync_job_status_activity, mock_update_status_activity
            )

            # Run the workflow - should complete successfully
            await env.client.execute_workflow(
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
                id=f"test-workflow-{uuid4()}",
                task_queue="test-queue",
            )

            # Verify that the status update activity was NOT called
            assert not status_updated, "Status update activity should not be called on success"
