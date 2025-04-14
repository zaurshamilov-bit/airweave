"""Module for data synchronization with improved architecture."""

import asyncio
from datetime import datetime
from typing import List, Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity, DestinationAction
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.stream import AsyncSourceStream


# Worker Pool Pattern
class AsyncWorkerPool:
    """Manages a pool of workers with controlled concurrency."""

    def __init__(self, max_workers: int = 20):
        """Initialize worker pool with concurrency control."""
        self.semaphore = asyncio.Semaphore(max_workers)
        self.pending_tasks = set()
        self.max_workers = max_workers

    async def submit(self, coro, *args, **kwargs) -> asyncio.Task:
        """Submit a coroutine to be executed by the worker pool."""
        task = asyncio.create_task(self._run_with_semaphore(coro, *args, **kwargs))
        self.pending_tasks.add(task)
        task.add_done_callback(self._handle_task_completion)
        return task

    async def _run_with_semaphore(self, coro, *args, **kwargs):
        """Run a coroutine with semaphore control."""
        async with self.semaphore:
            return await coro(*args, **kwargs)

    def _handle_task_completion(self, task: asyncio.Task) -> None:
        """Handle task completion and clean up."""
        self.pending_tasks.discard(task)
        if not task.cancelled() and task.exception():
            logger.error(f"Task failed: {task.exception()}")

    async def wait_for_batch(self, timeout: float = 0.5) -> None:
        """Wait for some tasks to complete."""
        if not self.pending_tasks:
            return
        done, _ = await asyncio.wait(
            self.pending_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout
        )
        for task in done:
            try:
                await task
            except Exception as e:
                logger.error(f"Error in worker task: {e}")

    async def wait_for_completion(self) -> None:
        """Wait for all tasks to complete."""
        while self.pending_tasks:
            # Process in batches to avoid memory issues with large task sets
            current_batch = list(self.pending_tasks)[: self.max_workers * 2]
            if not current_batch:
                break

            done, _ = await asyncio.wait(
                current_batch, return_when=asyncio.ALL_COMPLETED, timeout=10
            )

            # Check for exceptions
            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(f"Task error during completion: {e}")


# Pipeline Pattern
class EntityProcessor:
    """Processes entities through a pipeline of stages."""

    async def process(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Process an entity through the complete pipeline."""
        # Stage 1: Enrich entity with metadata
        enriched_entity = await self.enrich(entity, sync_context)

        # Stage 2: Determine action for entity
        db_entity, action = await self.determine_action(enriched_entity, sync_context, db)

        # Stage 3: Skip further processing if KEEP
        if action == DestinationAction.KEEP:
            await sync_context.progress.increment("kept", 1)
            return []

        # Stage 4: Process entity through DAG
        processed_entities = await self.transform(enriched_entity, source_node, sync_context, db)

        # Stage 5: Persist entities based on action
        await self.persist(enriched_entity, processed_entities, db_entity, action, sync_context, db)

        return processed_entities

    async def enrich(self, entity: BaseEntity, sync_context: SyncContext) -> BaseEntity:
        """Enrich entity with sync metadata."""
        entity.source_name = sync_context.source._name
        entity.sync_id = sync_context.sync.id
        entity.sync_job_id = sync_context.sync_job.id
        entity.sync_metadata = sync_context.sync.sync_metadata

        if sync_context.sync.white_label_id:
            entity.white_label_user_identifier = sync_context.sync.white_label_user_identifier
            entity.white_label_id = sync_context.sync.white_label_id
            entity.white_label_name = sync_context.white_label.name

        return entity

    async def determine_action(
        self, entity: BaseEntity, sync_context: SyncContext, db: AsyncSession
    ) -> tuple[schemas.Entity, DestinationAction]:
        """Determine what action to take for an entity."""
        db_entity = await crud.entity.get_by_entity_and_sync_id(
            db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
        )

        if db_entity:
            if db_entity.hash != entity.hash():
                action = DestinationAction.UPDATE
            else:
                action = DestinationAction.KEEP
        else:
            action = DestinationAction.INSERT

        return db_entity, action

    async def transform(
        self,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> List[BaseEntity]:
        """Transform entity through DAG routing."""
        return await sync_context.router.process_entity(
            db=db,
            producer_id=source_node.id,
            entity=entity,
        )

    async def persist(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        action: DestinationAction,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Persist entities to destinations based on action."""
        # Get appropriate action handler
        handler = EntityActionHandler.get_handler(action)
        await handler.handle(parent_entity, processed_entities, db_entity, sync_context, db)


# State Pattern
class EntityActionHandler(Protocol):
    """Protocol for entity action handlers."""

    async def handle(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: Optional[schemas.Entity],
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle entity action."""
        ...


class KeepHandler:
    """Handler for KEEP action."""

    async def handle(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle KEEP action."""
        await sync_context.progress.increment(kept=1)


class InsertHandler:
    """Handler for INSERT action."""

    async def handle(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: Optional[schemas.Entity],
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle INSERT action."""
        if len(processed_entities) == 0:
            raise ValueError("No processed entities to persist")

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Insert into database
        new_db_entity = await crud.entity.create(
            db=db,
            obj_in=schemas.EntityCreate(
                sync_job_id=sync_context.sync_job.id,
                sync_id=sync_context.sync.id,
                entity_id=parent_entity.entity_id,
                hash=parent_entity.hash(),
            ),
            organization_id=sync_context.sync.organization_id,
        )
        parent_entity.db_entity_id = new_db_entity.id

        # Insert to destinations
        for destination in sync_context.destinations:
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("inserted", 1)


class UpdateHandler:
    """Handler for UPDATE action."""

    async def handle(
        self,
        parent_entity: BaseEntity,
        processed_entities: List[BaseEntity],
        db_entity: schemas.Entity,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Handle UPDATE action."""
        if len(processed_entities) == 0:
            raise ValueError("No processed entities to persist")

        # Prepare entities with parent reference
        for processed_entity in processed_entities:
            if (
                not hasattr(processed_entity, "parent_entity_id")
                or not processed_entity.parent_entity_id
            ):
                processed_entity.parent_entity_id = parent_entity.entity_id

        # Update hash in database
        await crud.entity.update(
            db=db,
            db_obj=db_entity,
            obj_in=schemas.EntityUpdate(hash=parent_entity.hash()),
        )
        parent_entity.db_entity_id = db_entity.id

        # Update in destinations (delete then insert)
        for destination in sync_context.destinations:
            await destination.bulk_delete_by_parent_id(
                parent_entity.entity_id, sync_context.sync.id
            )
            await destination.bulk_insert(processed_entities)

        await sync_context.progress.increment("updated", 1)


class EntityActionHandler:
    """Factory for entity action handlers."""

    @classmethod
    def get_handler(cls, action: DestinationAction) -> EntityActionHandler:
        """Get the appropriate handler for an action."""
        handlers = {
            DestinationAction.INSERT: InsertHandler(),
            DestinationAction.UPDATE: UpdateHandler(),
            DestinationAction.KEEP: KeepHandler(),
        }
        return handlers[action]


# Refactored Orchestrator
class SyncOrchestrator:
    """Main service for data synchronization with improved architecture."""

    def __init__(self):
        """Initialize the sync orchestrator."""
        self.worker_pool = AsyncWorkerPool(max_workers=20)
        self.entity_processor = EntityProcessor()

    async def run(self, sync_context: SyncContext) -> schemas.Sync:
        """Run a sync with full async processing."""
        try:
            # Get source node from DAG
            source_node = sync_context.dag.get_source_node()

            # Process entity stream
            await self._process_entity_stream(source_node, sync_context)

            # Update job status
            await self._update_sync_job_status(
                sync_context=sync_context,
                status=SyncJobStatus.COMPLETED,
                completed_at=datetime.now(),
            )

            return sync_context.sync

        except Exception as e:
            logger.error(f"Error during sync: {e}")

            # Update job status
            await self._update_sync_job_status(
                sync_context=sync_context,
                status=SyncJobStatus.FAILED,
                error=str(e),
                failed_at=datetime.now(),
            )
            raise

    async def _process_entity_stream(
        self, source_node: schemas.DagNode, sync_context: SyncContext
    ) -> None:
        """Process stream of entities from source."""
        error_occurred = False

        # Use the stream as a context manager
        async with AsyncSourceStream(sync_context.source.generate_entities()) as stream:
            try:
                # Process entities as they come
                async for entity in stream.get_entities():
                    # Submit each entity for processing in the worker pool
                    task = await self.worker_pool.submit(
                        self._process_single_entity,
                        entity=entity,
                        source_node=source_node,
                        sync_context=sync_context,
                    )

                    # Save entity for error reporting
                    task.entity = entity

                    # If we have too many pending tasks, wait for some to complete
                    if len(self.worker_pool.pending_tasks) >= self.worker_pool.max_workers * 2:
                        await self.worker_pool.wait_for_batch(timeout=0.5)

                # Wait for all remaining tasks
                await self.worker_pool.wait_for_completion()

            except Exception as e:
                logger.error(f"Error during entity stream processing: {e}")
                error_occurred = True
                raise
            finally:
                # Finalize progress
                await sync_context.progress.finalize(is_complete=not error_occurred)

    async def _process_single_entity(
        self, entity: BaseEntity, source_node: schemas.DagNode, sync_context: SyncContext
    ) -> None:
        """Process a single entity through the pipeline."""
        # Create a new database session for this task
        async with get_db_context() as db:
            # Process the entity through the pipeline
            await self.entity_processor.process(
                entity=entity, source_node=source_node, sync_context=sync_context, db=db
            )

    async def _update_sync_job_status(
        self,
        sync_context: SyncContext,
        status: SyncJobStatus,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with progress statistics."""
        try:
            async with get_db_context() as db:
                # Get DB model for sync job
                db_sync_job = await crud.sync_job.get(db=db, id=sync_context.sync_job.id)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_context.sync_job.id} not found")
                    return

                # Base update data
                update_data = {
                    "status": status,
                    "stats": sync_context.progress.to_dict(),
                    "records_processed": sync_context.progress.stats.inserted,
                    "records_updated": sync_context.progress.stats.updated,
                    "records_deleted": sync_context.progress.stats.deleted,
                }

                # Add status-specific fields
                if status == SyncJobStatus.COMPLETED and completed_at:
                    update_data["completed_at"] = completed_at
                elif status == SyncJobStatus.FAILED:
                    if failed_at:
                        update_data["failed_at"] = failed_at
                    if error:
                        update_data["error"] = error

                # Update sync job
                await crud.sync_job.update(
                    db=db,
                    db_obj=db_sync_job,
                    obj_in=schemas.SyncJobUpdate(**update_data),
                    current_user=sync_context.current_user,
                )
        except Exception as e:
            # Log but don't raise
            logger.error(f"Failed to update sync job status: {e}")


# Singleton instance
sync_orchestrator = SyncOrchestrator()
