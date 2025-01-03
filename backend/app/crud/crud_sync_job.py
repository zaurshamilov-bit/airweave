"""CRUD operations for sync jobs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud._base import CRUDBase
from app.models.sync_job import SyncJob
from app.schemas.sync_job import SyncJobCreate, SyncJobUpdate


class CRUDSyncJob(CRUDBase[SyncJob, SyncJobCreate, SyncJobUpdate]):
    """CRUD operations for sync jobs."""

    async def get_all_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> list[SyncJob]:
        """Get all jobs for a specific sync."""
        stmt = select(SyncJob).where(SyncJob.sync_id == sync_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_latest_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> SyncJob | None:
        """Get the most recent job for a specific sync."""
        stmt = select(SyncJob).where(
            SyncJob.sync_id == sync_id
        ).order_by(SyncJob.created_at.desc())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


sync_job = CRUDSyncJob(SyncJob)
