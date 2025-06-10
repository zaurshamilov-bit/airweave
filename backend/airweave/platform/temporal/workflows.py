"""Temporal workflows for Airweave."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import CancelledError


@workflow.defn
class RunSourceConnectionWorkflow:
    """Workflow for running a source connection sync."""

    @workflow.run
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        sync_dag_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        source_connection_dict: Dict[str, Any],
        user_dict: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> None:
        """Run the source connection sync workflow.

        Args:
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict
            sync_dag_dict: The sync DAG as dict
            collection_dict: The collection as dict
            source_connection_dict: The source connection as dict
            user_dict: The current user as dict
            access_token: Optional access token
        """
        # Import inside the workflow to avoid issues
        from airweave.platform.temporal.activities import (
            run_sync_activity,
            update_sync_job_status_activity,
        )

        sync_job_id = sync_job_dict.get("id")
        error_message = None

        try:
            # Execute the sync activity
            await workflow.execute_activity(
                run_sync_activity,
                args=[
                    sync_dict,
                    sync_job_dict,
                    sync_dag_dict,
                    collection_dict,
                    source_connection_dict,
                    user_dict,
                    access_token,
                ],
                start_to_close_timeout=timedelta(hours=1),  # 1 hour timeout for sync
                heartbeat_timeout=timedelta(minutes=2),  # Fail if no heartbeat for 2 minutes
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=1,
                ),
            )

        except CancelledError:
            # Handle workflow cancellation (e.g., from kill command)
            error_message = "Workflow was cancelled"
            workflow.logger.error(f"Sync job {sync_job_id} was cancelled")

            # Update sync job status to CANCELLED
            await workflow.execute_activity(
                update_sync_job_status_activity,
                args=[
                    sync_job_id,
                    "CANCELLED",  # Use CANCELLED status instead of FAILED
                    user_dict,
                    error_message,
                    workflow.now().isoformat(),  # Use workflow.now() for deterministic time
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )
            raise

        except Exception as e:
            # Handle any other errors (including heartbeat timeout)
            error_message = str(e)
            workflow.logger.error(f"Sync job {sync_job_id} failed: {error_message}")

            # Update sync job status to FAILED
            await workflow.execute_activity(
                update_sync_job_status_activity,
                args=[
                    sync_job_id,
                    "FAILED",
                    user_dict,
                    error_message,
                    workflow.now().isoformat(),  # Use workflow.now() for deterministic time
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )
            raise
