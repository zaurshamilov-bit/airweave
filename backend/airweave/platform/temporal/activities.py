"""Temporal activities for Airweave."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity


# Import inside the activity to avoid issues with Temporal's sandboxing
@activity.defn
async def run_sync_activity(
    sync_dict: Dict[str, Any],
    sync_job_dict: Dict[str, Any],
    sync_dag_dict: Dict[str, Any],
    collection_dict: Dict[str, Any],
    source_connection_dict: Dict[str, Any],
    user_dict: Dict[str, Any],
    access_token: Optional[str] = None,
) -> None:
    """Activity to run a sync job.

    This activity wraps the existing sync_service.run method.

    Args:
        sync_dict: The sync configuration as dict
        sync_job_dict: The sync job as dict
        sync_dag_dict: The sync DAG as dict
        collection_dict: The collection as dict
        source_connection_dict: The source connection as dict
        user_dict: The current user as dict
        access_token: Optional access token
    """
    # Import here to avoid Temporal sandboxing issues
    from airweave import schemas
    from airweave.core.sync_service import sync_service

    # Convert dicts back to Pydantic models
    sync = schemas.Sync(**sync_dict)
    sync_job = schemas.SyncJob(**sync_job_dict)
    sync_dag = schemas.SyncDag(**sync_dag_dict)
    collection = schemas.Collection(**collection_dict)
    source_connection = schemas.SourceConnection(**source_connection_dict)
    user = schemas.User(**user_dict)

    activity.logger.info(f"Starting sync activity for job {sync_job.id}")

    # Start a background task to send heartbeats
    heartbeat_task = None
    try:
        # Create a flag to stop heartbeating when done
        should_heartbeat = True

        async def send_heartbeats():
            """Send regular heartbeats to Temporal."""
            heartbeat_count = 0
            while should_heartbeat:
                try:
                    # Check if cancellation was requested
                    if activity.is_cancelled():
                        activity.logger.info("Activity cancellation detected via heartbeat")
                        break

                    # Send heartbeat with progress info
                    heartbeat_count += 1
                    activity.heartbeat(f"Sync in progress, heartbeat #{heartbeat_count}")

                    # Wait 30 seconds before next heartbeat
                    await asyncio.sleep(30)
                except Exception as e:
                    activity.logger.error(f"Error sending heartbeat: {e}")
                    break

        # Start heartbeating in background
        heartbeat_task = asyncio.create_task(send_heartbeats())

        # Run the actual sync
        await sync_service.run(
            sync=sync,
            sync_job=sync_job,
            dag=sync_dag,
            collection=collection,
            source_connection=source_connection,
            current_user=user,
            access_token=access_token,
        )
        activity.logger.info(f"Completed sync activity for job {sync_job.id}")

    except Exception as e:
        activity.logger.error(f"Failed sync activity for job {sync_job.id}: {e}")
        raise
    finally:
        # Stop heartbeating
        should_heartbeat = False
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass


@activity.defn
async def update_sync_job_status_activity(
    sync_job_id: str,
    status: str,
    user_dict: Dict[str, Any],
    error: Optional[str] = None,
    failed_at: Optional[str] = None,
) -> None:
    """Activity to update sync job status.

    This activity is used to update the sync job status when errors occur
    or when the workflow is cancelled.

    Args:
        sync_job_id: The sync job ID
        status: The new status (e.g., "FAILED", "CANCELLED")
        user_dict: The current user as dict
        error: Optional error message
        failed_at: Optional timestamp when the job failed
    """
    # Import here to avoid Temporal sandboxing issues
    from airweave import schemas
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service

    # Convert user dict back to Pydantic model
    user = schemas.User(**user_dict)

    # Convert string status to enum
    status_enum = SyncJobStatus[status]

    # Convert failed_at string to datetime if provided
    failed_at_dt = datetime.fromisoformat(failed_at) if failed_at else None

    activity.logger.info(f"Updating sync job {sync_job_id} status to {status}")

    try:
        await sync_job_service.update_status(
            sync_job_id=UUID(sync_job_id),
            status=status_enum,
            current_user=user,
            error=error,
            failed_at=failed_at_dt,
        )
        activity.logger.info(f"Successfully updated sync job {sync_job_id} status to {status}")
    except Exception as e:
        activity.logger.error(f"Failed to update sync job {sync_job_id} status: {e}")
        raise
