"""Service for managing sync job status."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.sync.pubsub import SyncProgressUpdate
from airweave.schemas.auth import AuthContext


class SyncJobService:
    """Service for managing sync job status updates."""

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        auth_context: AuthContext,
        stats: Optional[SyncProgressUpdate] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details."""
        try:
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(
                    db=db, id=sync_job_id, auth_context=auth_context
                )

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                update_data = {"status": status}

                if stats:
                    update_data["entities_inserted"] = stats.inserted
                    update_data["entities_updated"] = stats.updated
                    update_data["entities_deleted"] = stats.deleted
                    update_data["entities_kept"] = stats.kept
                    update_data["entities_skipped"] = stats.skipped

                    # Use the counts directly - they're already in the right format
                    if hasattr(stats, "entities_encountered"):
                        update_data["entities_encountered"] = stats.entities_encountered

                if started_at:
                    update_data["started_at"] = started_at
                if status == SyncJobStatus.COMPLETED and completed_at:
                    update_data["completed_at"] = completed_at
                elif status == SyncJobStatus.FAILED:
                    if failed_at:
                        update_data["failed_at"] = failed_at or datetime.now()
                    if error:
                        update_data["error"] = error

                await crud.sync_job.update(
                    db=db,
                    db_obj=db_sync_job,
                    obj_in=schemas.SyncJobUpdate(**update_data),
                    auth_context=auth_context,
                )
        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")


# Singleton instance
sync_job_service = SyncJobService()
