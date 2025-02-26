"""Service for data synchronization."""

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.dag_service import dag_service
from app.db.unit_of_work import UnitOfWork
from app.platform.sync.context import SyncContextFactory
from app.platform.sync.orchestrator import sync_orchestrator


class SyncService:
    """Main service for data synchronization."""

    async def create(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        current_user: schemas.User,
        uow: UnitOfWork,
    ) -> schemas.Sync:
        """Create a new sync."""
        sync = await crud.sync.create(db=db, obj_in=sync, current_user=current_user, uow=uow)
        await uow.session.flush()
        await dag_service.create_initial_dag(
            db=db, sync_id=sync.id, current_user=current_user, uow=uow
        )
        return sync

    async def run(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync."""
        sync_context = await SyncContextFactory.create(db, sync, sync_job, dag, current_user)
        return await sync_orchestrator.run(sync_context)
