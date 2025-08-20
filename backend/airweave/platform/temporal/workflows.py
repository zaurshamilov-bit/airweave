"""Temporal workflows for Airweave."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, CancelledError

from airweave.platform.utils.error_utils import get_error_message


@workflow.defn
class RunSourceConnectionWorkflow:
    """Workflow for running a source connection sync."""

    async def _update_job_status(
        self,
        sync_job_id: str,
        status: str,
        ctx_dict: Dict[str, Any],
        error_message: Optional[str] = None,
    ) -> None:
        """Helper method to update sync job status."""
        from airweave.platform.temporal.activities import update_sync_job_status_activity

        try:
            await workflow.execute_activity(
                update_sync_job_status_activity,
                args=[
                    sync_job_id,
                    status,
                    ctx_dict,
                    error_message,
                    workflow.now().replace(tzinfo=None).isoformat(),
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                ),
            )
            workflow.logger.info(
                f"Successfully updated sync job {sync_job_id} status to {status.upper()}"
            )
        except Exception as e:
            workflow.logger.error(f"Failed to update sync job status: {e}")

    async def _create_sync_job_if_needed(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],
        ctx_dict: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Create sync job for scheduled runs or return existing one."""
        from airweave.platform.temporal.activities import create_sync_job_activity

        # If no sync_job_dict provided (scheduled run), create a new sync job
        if sync_job_dict is None:
            sync_id = sync_dict.get("id")
            try:
                workflow.logger.info(f"Creating new sync job for scheduled run of sync {sync_id}")
                sync_job_dict = await workflow.execute_activity(
                    create_sync_job_activity,
                    args=[sync_id, ctx_dict],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,  # Don't retry if job already exists
                        initial_interval=timedelta(seconds=1),
                    ),
                )
                workflow.logger.info(
                    f"Created sync job {sync_job_dict.get('id')} for sync {sync_id}"
                )
            except Exception as e:
                # If we can't create a sync job (e.g., one is already running), skip this run
                workflow.logger.warning(f"Skipping scheduled run for sync {sync_id}: {str(e)}")
                return None  # Signal to exit gracefully
        return sync_job_dict

    @workflow.run
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],  # Made optional for scheduled runs
        sync_dag_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        source_connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
    ) -> None:
        """Run the source connection sync workflow.

        Args:
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict (optional for scheduled runs)
            sync_dag_dict: The sync DAG as dict
            collection_dict: The collection as dict
            source_connection_dict: The source connection as dict
            ctx_dict: The authentication context as dict
            access_token: Optional access token
        """
        from airweave.platform.temporal.activities import run_sync_activity

        # Create sync job if needed (for scheduled runs)
        sync_job_dict = await self._create_sync_job_if_needed(sync_dict, sync_job_dict, ctx_dict)
        if sync_job_dict is None:
            return  # Exit gracefully if we couldn't create a job

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
                    ctx_dict,
                    access_token,
                ],
                start_to_close_timeout=timedelta(days=7),
                heartbeat_timeout=timedelta(minutes=10),  # Fail if no heartbeat for 10 minutes
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
            await self._update_job_status(sync_job_id, "cancelled", ctx_dict, error_message)

            # Re-raise the original error
            raise

        except ActivityError as e:
            # Check if the cause is a CancelledError - handle as cancellation
            if hasattr(e, "cause") and isinstance(e.cause, CancelledError):
                error_message = "Workflow was cancelled"
                workflow.logger.error(f"Sync job {sync_job_id} was cancelled (via ActivityError)")

                # Update sync job status to CANCELLED
                await self._update_job_status(sync_job_id, "cancelled", ctx_dict, error_message)

                # Re-raise the original error
                raise
            else:
                # Handle other ActivityErrors as failures
                # Extract the real error message
                if hasattr(e, "cause") and e.cause:
                    error_message = get_error_message(e.cause)
                else:
                    error_message = get_error_message(e)

                workflow.logger.error(f"Sync job {sync_job_id} failed: {error_message}")

                # Update sync job with the real error
                await self._update_job_status(sync_job_id, "failed", ctx_dict, error_message)

                # Re-raise the original error
                raise

        except Exception as e:
            # Handle any other errors (generic exceptions)
            error_message = get_error_message(e)
            workflow.logger.error(f"Sync job {sync_job_id} failed: {error_message}")

            # Update sync job status to FAILED
            await self._update_job_status(sync_job_id, "failed", ctx_dict, error_message)

            # Re-raise the original error
            raise
