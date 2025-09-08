"""Service for managing sync job status."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.analytics.service import analytics
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.sync.pubsub import SyncProgressUpdate


def map_python_enum_to_database(status: SyncJobStatus) -> str:
    """Map Python enum status to database enum value.

    Python enum uses lowercase: pending, in_progress, completed, failed, cancelled
    Database enum uses uppercase: PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED

    Args:
        status: The SyncJobStatus enum value

    Returns:
        The corresponding uppercase database enum string value
    """
    return status.value.upper()


class SyncJobService:
    """Service for managing sync job status updates."""

    def _build_stats_update_data(self, stats: SyncProgressUpdate) -> Dict[str, Any]:
        """Build update data from stats."""
        update_data = {
            "entities_inserted": stats.inserted,
            "entities_updated": stats.updated,
            "entities_deleted": stats.deleted,
            "entities_kept": stats.kept,
            "entities_skipped": stats.skipped,
        }

        # Use the counts directly - they're already in the right format
        if hasattr(stats, "entities_encountered"):
            update_data["entities_encountered"] = stats.entities_encountered

        return update_data

    def _build_timestamp_update_data(
        self,
        status: SyncJobStatus,
        started_at: Optional[datetime],
        completed_at: Optional[datetime],
        failed_at: Optional[datetime],
        error: Optional[str],
    ) -> Dict[str, Any]:
        """Build timestamp and error update data."""
        update_data = {}

        if started_at:
            update_data["started_at"] = started_at

        if status == SyncJobStatus.COMPLETED and completed_at:
            update_data["completed_at"] = completed_at
        elif status == SyncJobStatus.FAILED:
            if failed_at:
                update_data["failed_at"] = failed_at or utc_now_naive()
            if error:
                update_data["error"] = error

        return update_data

    async def _update_status_in_database(self, db, sync_job_id: UUID, db_status_value: str) -> None:
        """Update status field using raw SQL."""
        from sqlalchemy import text

        # Update status with uppercase value directly
        await db.execute(
            text(
                "UPDATE sync_job SET status = :status, "
                "modified_at = :modified_at WHERE id = :sync_job_id"
            ),
            {
                "status": db_status_value,
                "modified_at": utc_now_naive(),
                "sync_job_id": sync_job_id,
            },
        )

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        ctx: ApiContext,
        stats: Optional[SyncProgressUpdate] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details."""
        try:
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(db=db, id=sync_job_id, ctx=ctx)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                # Map Python enum to database enum value (lowercase to uppercase)
                db_status_value = map_python_enum_to_database(status)
                logger.info(
                    f"Mapping Python enum {status.value} to database value {db_status_value}"
                )

                update_data = {"status": status}

                if stats:
                    stats_data = self._build_stats_update_data(stats)
                    update_data.update(stats_data)

                timestamp_data = self._build_timestamp_update_data(
                    status, started_at, completed_at, failed_at, error
                )
                update_data.update(timestamp_data)

                # Update status using raw SQL
                await self._update_status_in_database(db, sync_job_id, db_status_value)

                # Update other fields using the normal ORM
                # (excluding status which we already updated)
                update_data.pop("status")
                if update_data:
                    await crud.sync_job.update(
                        db=db,
                        db_obj=db_sync_job,
                        obj_in=schemas.SyncJobUpdate(**update_data),
                        ctx=ctx,
                    )

                await db.commit()
                logger.info(
                    f"Successfully updated sync job {sync_job_id} status to {db_status_value}"
                )

                # Track analytics for sync completion
                if status == SyncJobStatus.COMPLETED and stats:
                    await self._track_sync_completion(sync_job_id, db_sync_job.sync_id, stats, ctx)

        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")

    async def _track_sync_completion(
        self, sync_job_id: UUID, sync_id: UUID, stats: SyncProgressUpdate, ctx: ApiContext
    ) -> None:
        """Track analytics for sync completion with entity counts per sync and entity type."""
        try:
            # Calculate total entities synced
            total_entities = (
                stats.inserted + stats.updated + stats.deleted + stats.kept + stats.skipped
            )

            # Track sync completion event with sync_id
            analytics.track_event(
                event_name="sync_completed",
                distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
                properties={
                    "sync_job_id": str(sync_job_id),
                    "sync_id": str(sync_id),
                    "total_entities": total_entities,
                    "entities_inserted": stats.inserted,
                    "entities_updated": stats.updated,
                    "entities_deleted": stats.deleted,
                    "entities_kept": stats.kept,
                    "entities_skipped": stats.skipped,
                    "organization_name": getattr(ctx.organization, "name", "unknown"),
                },
                groups={"organization": str(ctx.organization.id)},
            )

            # Track individual entity type counts for detailed analysis
            if hasattr(stats, "entities_encountered") and stats.entities_encountered:
                for entity_type, entity_count in stats.entities_encountered.items():
                    user_id = str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}"
                    analytics.track_event(
                        event_name="entities_synced_by_type",
                        distinct_id=user_id,
                        properties={
                            "sync_job_id": str(sync_job_id),
                            "sync_id": str(sync_id),
                            "entity_type": entity_type,
                            "entity_count": entity_count,
                            "organization_name": getattr(ctx.organization, "name", "unknown"),
                        },
                        groups={"organization": str(ctx.organization.id)},
                    )

            logger.info(f"Tracked sync completion analytics for job {sync_job_id} (sync {sync_id})")

        except Exception as e:
            logger.error(f"Failed to track sync completion analytics: {e}")


# Singleton instance
sync_job_service = SyncJobService()
