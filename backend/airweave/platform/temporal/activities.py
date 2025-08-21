"""Temporal activities for Airweave."""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import CancelledError as ActivityCancelledError


async def _send_heartbeats(should_heartbeat_flag: dict) -> bool:
    """Send regular heartbeats to Temporal."""
    cancellation_requested = False
    heartbeat_count = 0
    while should_heartbeat_flag["value"]:
        try:
            # Check if cancellation was requested
            if activity.is_cancelled():
                activity.logger.info("Activity cancellation detected via heartbeat")
                cancellation_requested = True
                break

            # Send heartbeat with progress info
            heartbeat_count += 1
            activity.heartbeat(f"Sync in progress, heartbeat #{heartbeat_count}")

            # Wait 30 seconds before next heartbeat
            await asyncio.sleep(30)
        except Exception as e:
            activity.logger.error(f"Error sending heartbeat: {e}")
            break
    return cancellation_requested


async def _run_sync_task(
    sync,
    sync_job,
    sync_dag,
    collection,
    source_connection,
    ctx,
    access_token,
    force_full_sync=False,
):
    """Run the actual sync service."""
    from airweave.core.sync_service import sync_service

    return await sync_service.run(
        sync=sync,
        sync_job=sync_job,
        dag=sync_dag,
        collection=collection,
        source_connection=source_connection,
        ctx=ctx,
        access_token=access_token,
        force_full_sync=force_full_sync,
    )


async def _wait_for_sync_completion(sync_task, heartbeat_task, should_heartbeat_flag, sync_job):
    """Wait for sync completion or handle cancellation."""
    # Wait for sync to complete or cancellation
    while not sync_task.done():
        # Check for cancellation every second
        try:
            await asyncio.wait_for(asyncio.shield(sync_task), timeout=1.0)
        except asyncio.TimeoutError:
            # Check if we should cancel
            cancellation_requested = False
            if heartbeat_task.done():
                try:
                    cancellation_requested = await heartbeat_task
                except Exception:
                    pass

            if cancellation_requested or activity.is_cancelled():
                activity.logger.info("Cancelling sync task due to activity cancellation")
                sync_task.cancel()
                try:
                    await sync_task
                except asyncio.CancelledError:
                    activity.logger.info("Sync task cancelled successfully")
                    raise ActivityCancelledError("Activity was cancelled by user") from None
            # Otherwise continue waiting
            continue

    # If we get here, sync completed normally
    activity.logger.info(f"Completed sync activity for job {sync_job.id}")


async def _cleanup_tasks(heartbeat_task, sync_task, should_heartbeat_flag):
    """Clean up background tasks."""
    # Stop heartbeating
    should_heartbeat_flag["value"] = False
    if heartbeat_task and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    # Cancel sync task if still running
    if sync_task and not sync_task.done():
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


# Import inside the activity to avoid issues with Temporal's sandboxing
@activity.defn
async def run_sync_activity(
    sync_dict: Dict[str, Any],
    sync_job_dict: Dict[str, Any],
    sync_dag_dict: Dict[str, Any],
    collection_dict: Dict[str, Any],
    source_connection_dict: Dict[str, Any],
    ctx_dict: Dict[str, Any],
    access_token: Optional[str] = None,
    force_full_sync: bool = False,
) -> None:
    """Activity to run a sync job.

    This activity wraps the existing sync_service.run method.

    Args:
        sync_dict: The sync configuration as dict
        sync_job_dict: The sync job as dict
        sync_dag_dict: The sync DAG as dict
        collection_dict: The collection as dict
        source_connection_dict: The source connection as dict
        ctx_dict: The API context as dict
        access_token: Optional access token
        force_full_sync: If True, forces a full sync with orphaned entity deletion
    """
    # Import here to avoid Temporal sandboxing issues
    from airweave import schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator

    # Convert dicts back to Pydantic models
    sync = schemas.Sync(**sync_dict)
    sync_job = schemas.SyncJob(**sync_job_dict)
    sync_dag = schemas.SyncDag(**sync_dag_dict)
    collection = schemas.Collection(**collection_dict)
    source_connection = schemas.SourceConnection(**source_connection_dict)

    # Reconstruct user if present
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    # Reconstruct organization from the dictionary
    organization = schemas.Organization(**ctx_dict["organization"])

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=LoggerConfigurator.configure_logger(
            "airweave.temporal.activity",
            dimensions={
                "sync_job_id": str(sync_job.id),
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        ),
    )

    activity.logger.info(f"Starting sync activity for job {sync_job.id}")

    # Start background tasks
    heartbeat_task = None
    sync_task = None
    should_heartbeat_flag = {"value": True}

    try:
        # Import here to avoid Temporal sandboxing issues

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(_send_heartbeats(should_heartbeat_flag))

        # Start the sync
        sync_task = asyncio.create_task(
            _run_sync_task(
                sync,
                sync_job,
                sync_dag,
                collection,
                source_connection,
                ctx,
                access_token,
                force_full_sync,
            )
        )

        await _wait_for_sync_completion(sync_task, heartbeat_task, should_heartbeat_flag, sync_job)

    except ActivityCancelledError:
        activity.logger.info(f"Sync activity cancelled for job {sync_job.id}")
        raise
    except asyncio.CancelledError:
        activity.logger.info(f"Sync activity cancelled (asyncio) for job {sync_job.id}")
        raise ActivityCancelledError("Activity was cancelled") from None
    except Exception as e:
        activity.logger.error(f"Failed sync activity for job {sync_job.id}: {e}")
        raise
    finally:
        await _cleanup_tasks(heartbeat_task, sync_task, should_heartbeat_flag)


@activity.defn
async def create_sync_job_activity(
    sync_id: str,
    ctx_dict: Dict[str, Any],
    force_full_sync: bool = False,
) -> Dict[str, Any]:
    """Create a new sync job for the given sync.

    This activity creates a new sync job in the database, checking first
    if there's already a running job for this sync.

    Args:
        sync_id: The sync ID to create a job for
        ctx_dict: The API context as dict
        force_full_sync: If True (daily cleanup), wait for running jobs to complete

    Returns:
        The created sync job as a dict

    Raises:
        Exception: If a sync job is already running and force_full_sync is False
    """
    from uuid import UUID

    from airweave import crud, schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator
    from airweave.db.session import get_db_context

    # Reconstruct organization and user from the dictionary
    organization = schemas.Organization(**ctx_dict["organization"])
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=LoggerConfigurator.configure_logger(
            "airweave.temporal.activity.create_sync_job",
            dimensions={
                "sync_id": sync_id,
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        ),
    )

    activity.logger.info(
        f"Creating sync job for sync {sync_id} (force_full_sync={force_full_sync})"
    )

    async with get_db_context() as db:
        # Check if there's already a running sync job for this sync
        running_jobs = await crud.sync_job.get_all_by_sync_id(
            db=db,
            sync_id=UUID(sync_id),
            status=["PENDING", "IN_PROGRESS"],  # Database enum uses uppercase, no CREATED status
        )

        if running_jobs:
            if force_full_sync:
                # For daily cleanup, wait for running jobs to complete
                activity.logger.info(
                    f"🔄 Daily cleanup sync for {sync_id}: "
                    f"Found {len(running_jobs)} running job(s). "
                    f"Waiting for them to complete before starting cleanup..."
                )

                # Wait for running jobs to complete (check every 30 seconds)
                import asyncio

                max_wait_time = 60 * 60  # 1 hour max wait
                wait_interval = 30  # Check every 30 seconds
                total_waited = 0

                while total_waited < max_wait_time:
                    # Send heartbeat to prevent timeout
                    activity.heartbeat(f"Waiting for running jobs to complete ({total_waited}s)")

                    # Wait before checking again
                    await asyncio.sleep(wait_interval)
                    total_waited += wait_interval

                    # Check if jobs are still running
                    async with get_db_context() as check_db:
                        still_running = await crud.sync_job.get_all_by_sync_id(
                            db=check_db,
                            sync_id=UUID(sync_id),
                            status=["PENDING", "IN_PROGRESS"],
                        )

                        if not still_running:
                            activity.logger.info(
                                f"✅ Running jobs completed. "
                                f"Proceeding with cleanup sync for {sync_id}"
                            )
                            break
                else:
                    # Timeout reached
                    activity.logger.error(
                        f"❌ Timeout waiting for running jobs to complete for sync {sync_id}. "
                        f"Skipping cleanup sync."
                    )
                    raise Exception(
                        f"Timeout waiting for running jobs to complete after {max_wait_time}s"
                    )
            else:
                # For regular incremental syncs, skip if job is running
                activity.logger.warning(
                    f"Sync {sync_id} already has {len(running_jobs)} running jobs. "
                    f"Skipping new job creation."
                )
                raise Exception(
                    f"Sync {sync_id} already has a running job. "
                    f"Skipping this scheduled run to avoid conflicts."
                )

        # Create the new sync job
        sync_job_in = schemas.SyncJobCreate(sync_id=UUID(sync_id))
        sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, ctx=ctx)

        # Access the ID before commit to avoid lazy loading issues
        sync_job_id = sync_job.id

        await db.commit()

        # Refresh the object to ensure all attributes are loaded
        await db.refresh(sync_job)

        activity.logger.info(f"Created sync job {sync_job_id} for sync {sync_id}")

        # Convert to dict for return
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)
        return sync_job_schema.model_dump(mode="json")


@activity.defn
async def update_sync_job_status_activity(
    sync_job_id: str,
    status: str,
    ctx_dict: Dict[str, Any],
    error: Optional[str] = None,
    failed_at: Optional[str] = None,
) -> None:
    """Activity to update sync job status.

    This activity is used to update the sync job status when errors occur
    or when the workflow is cancelled.

    Args:
        sync_job_id: The sync job ID
        status: The new status string (e.g., "failed", "cancelled")
        ctx_dict: The current authentication context as dict
        error: Optional error message
        failed_at: Optional timestamp when the job failed
    """
    # Import here to avoid Temporal sandboxing issues
    from airweave import schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service

    # Reconstruct user if present
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    # Reconstruct organization from the dictionary
    organization = schemas.Organization(**ctx_dict["organization"])

    # Reconstruct ApiContext with a new logger
    logger = LoggerConfigurator.configure_logger(
        "airweave.temporal.activity",
        dimensions={
            "sync_job_id": sync_job_id,
            "organization_id": str(organization.id),
            "organization_name": organization.name,
        },
    )

    # Reconstruct user if present
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=logger,
    )

    # Convert string status to SyncJobStatus enum
    # Handle both lowercase (Python enum values) and uppercase (database values)
    try:
        # First try direct enum value match (lowercase Python enum values)
        status_enum = SyncJobStatus(status.lower())
    except ValueError:
        # Fallback: try to find enum by attribute name
        try:
            status_upper = status.upper()
            if hasattr(SyncJobStatus, status_upper):
                status_enum = getattr(SyncJobStatus, status_upper)
            else:
                activity.logger.error(f"Invalid status: {status}")
                raise ValueError(f"Invalid sync job status: {status}") from None
        except ValueError:
            activity.logger.error(f"Invalid status: {status}")
            raise ValueError(f"Invalid sync job status: {status}") from None

    # Convert failed_at string to datetime if provided
    failed_at_dt = datetime.fromisoformat(failed_at) if failed_at else None

    activity.logger.info(f"Updating sync job {sync_job_id} status to {status_enum.name}")

    try:
        await sync_job_service.update_status(
            sync_job_id=UUID(sync_job_id),
            status=status_enum,
            ctx=ctx,
            error=error,
            failed_at=failed_at_dt,
        )
        activity.logger.info(
            f"Successfully updated sync job {sync_job_id} status to {status_enum.name}"
        )
    except Exception as e:
        activity.logger.error(f"Failed to update sync job {sync_job_id} status: {e}")
        raise
