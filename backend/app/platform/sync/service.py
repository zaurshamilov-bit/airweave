"""Module for data synchronization."""

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.dag_service import dag_service
from app.db.unit_of_work import UnitOfWork
from app.platform.sync.context import SyncContextFactory


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
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        current_user: schemas.User,
    ) -> schemas.Sync:
        """Run a sync with the new DAG-based routing."""
        async with AsyncSession() as db:
            # Create sync context with all necessary components
            sync_context = await SyncContextFactory.create(
                db=db,
                sync=sync,
                sync_job=sync_job,
                dag=dag,
                current_user=current_user,
            )

            # Get source node from DAG
            source_node = sync_context.dag.get_source_node()

            # Stream and process entities
            async for entity in sync_context.source.generate_entities():
                async for result in sync_context.router.process_entity(source_node, entity):
                    # Update progress based on action
                    if result.action == "insert":
                        sync_context.progress.inserted += 1
                        # Create new DB entity
                        db_entity = await crud.entity.create(
                            db=db,
                            obj_in=schemas.EntityCreate(
                                sync_id=sync.id,
                                entity_id=result.entity.entity_id,
                                hash=result.entity.hash,
                            ),
                            organization_id=sync.organization_id,
                        )
                        result.entity.db_entity_id = db_entity.id

                    elif result.action == "update":
                        sync_context.progress.updated += 1
                        # Update existing DB entity
                        await crud.entity.update(
                            db=db,
                            db_obj=result.db_entity,
                            obj_in=schemas.EntityUpdate(hash=result.entity.hash),
                        )
                        result.entity.db_entity_id = result.db_entity.id

            # Publish final progress
            await sync_context.progress.finalize()
            return sync


sync_service = SyncService()
