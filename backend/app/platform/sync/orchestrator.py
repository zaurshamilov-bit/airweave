"""Module for data synchronization."""

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.core.logging import logger
from app.db.session import get_db_context
from app.platform.entities._base import BaseEntity, DestinationAction
from app.platform.sync.context import SyncContext
from app.platform.sync.stream import AsyncSourceStream

MAX_WORKERS: int = 5


class SyncOrchestrator:
    """Main service for data synchronization."""

    async def run(self, sync_context: SyncContext) -> schemas.Sync:
        """Run a sync with full async processing.

        Args:
            sync_context: The sync context
        """
        try:
            async with get_db_context() as db:
                # Get source node from DAG
                source_node = sync_context.dag.get_source_node()

                # Process entities through the stream
                await self._process_entity_stream(source_node, sync_context, db)

                # Finalize and return sync
                await sync_context.progress.finalize()
                return sync_context.sync

        except Exception as e:
            logger.error(f"Error during sync: {e}")
            raise

    async def _process_entity_stream(
        self, source_node: schemas.DagNode, sync_context: SyncContext, db: AsyncSession
    ) -> None:
        """Process the stream of entities coming from the source.

        Args:
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session
        """
        # Create a semaphore to limit concurrent tasks
        semaphore = asyncio.Semaphore(MAX_WORKERS)

        # Create async stream and use it as a context manager
        async with AsyncSourceStream(sync_context.source.generate_entities()) as stream:
            try:
                # Process entities with controlled concurrency
                await self._process_stream_with_concurrency(
                    stream, semaphore, source_node, sync_context, db
                )
            except Exception as e:
                logger.error(f"Error during sync: {e}")
                raise
            finally:
                # Ensure we finalize progress
                await sync_context.progress.finalize()

    async def _process_stream_with_concurrency(
        self,
        stream: AsyncSourceStream,
        semaphore: asyncio.Semaphore,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Process the entity stream with controlled concurrency.

        Args:
            stream: The async source stream
            semaphore: Semaphore to control concurrency
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session
        """
        # Process entities as they come in, with controlled concurrency
        pending_tasks = set()

        # Process entities as they come in from the stream
        async for entity in stream.get_entities():
            # Create task for this entity
            task = asyncio.create_task(
                self._process_entity_with_semaphore(
                    semaphore, entity, source_node, sync_context, db
                )
            )
            # Store the original entity with the task for error reporting
            task.entity = entity
            pending_tasks.add(task)

            task.add_done_callback(lambda t: self._handle_task_completion(t, pending_tasks))

            # If we have too many pending tasks, wait for some to complete
            if len(pending_tasks) >= MAX_WORKERS * 2:
                await self._wait_for_tasks(pending_tasks, asyncio.FIRST_COMPLETED, 0.5)

        # Wait for any remaining tasks with proper error handling
        if pending_tasks:
            logger.info(f"Waiting for {len(pending_tasks)} remaining tasks")
            await self._wait_for_all_pending_tasks(pending_tasks)

    def _handle_task_completion(self, completed_task: asyncio.Task, pending_tasks: set) -> None:
        """Handle task completion and remove it from pending tasks.

        Args:
            completed_task: The completed task
            pending_tasks: Set of pending tasks
        """
        pending_tasks.discard(completed_task)
        # Handle any exceptions
        if not completed_task.cancelled() and completed_task.exception():
            entity_id = getattr(completed_task.entity, "entity_id", "unknown")
            logger.error(f"Task for entity {entity_id} failed: " f"{completed_task.exception()}")

    async def _wait_for_tasks(
        self, pending_tasks: set, return_when: asyncio.Future, timeout: float
    ) -> None:
        """Wait for tasks to complete with error handling.

        Args:
            pending_tasks: Set of pending tasks
            return_when: Wait policy (e.g., FIRST_COMPLETED)
            timeout: Maximum time to wait
        """
        done, _ = await asyncio.wait(
            pending_tasks,
            return_when=return_when,
            timeout=timeout,
        )

        # Process completed tasks and handle errors
        for completed_task in done:
            try:
                await completed_task
            except Exception as e:
                entity_id = getattr(
                    getattr(completed_task, "entity", None),
                    "entity_id",
                    "unknown",
                )
                logger.error(f"Entity {entity_id} processing error: {e}")
                # Re-raise critical exceptions
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise

    async def _wait_for_all_pending_tasks(self, pending_tasks: set) -> None:
        """Wait for all pending tasks to complete.

        Args:
            pending_tasks: Set of pending tasks
        """
        while pending_tasks:
            wait_tasks = list(pending_tasks)[: MAX_WORKERS * 2]
            done, pending_tasks_remaining = await asyncio.wait(
                wait_tasks,
                return_when=asyncio.ALL_COMPLETED,
                timeout=10,
            )

            # Update pending tasks
            for task in wait_tasks:
                pending_tasks.discard(task)

            # Add back any tasks that didn't complete
            pending_tasks.update(pending_tasks_remaining)

            # Check for exceptions
            for completed_task in done:
                try:
                    await completed_task
                except Exception as e:
                    entity_id = getattr(
                        getattr(completed_task, "entity", None),
                        "entity_id",
                        "unknown",
                    )
                    logger.error(f"Entity {entity_id} processing error: {e}")
                    # Re-raise critical exceptions
                    if isinstance(e, (KeyboardInterrupt, SystemExit)):
                        raise

    async def _process_entity_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        entity: BaseEntity,
        source_node: schemas.DagNode,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> Any:
        """Process a single entity with semaphore control.

        Args:
            semaphore: Semaphore to control concurrency
            entity: Entity to process
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session

        Returns:
            Processed result
        """
        async with semaphore:
            # First determine the entity action (without processing through DAG)
            db_entity, action = await self._determine_entity_action(entity, sync_context, db)

            # If the action is KEEP, we can skip further processing
            if action == DestinationAction.KEEP:
                return [], action

            # Process the entity through the DAG
            processed_entities = await sync_context.router.process_entity(source_node.id, entity)

            # Persist the processed entities
            for processed_entity in processed_entities:
                await self._persist_entity(processed_entity, db_entity, action, sync_context, db)

            return processed_entities, action

    async def _determine_entity_action(
        self, entity: BaseEntity, sync_context: SyncContext, db: AsyncSession
    ) -> tuple[Any, DestinationAction]:
        """Determine what action should be taken for an entity.

        Args:
            entity: Entity to check
            sync_context: The sync context
            db: Database session

        Returns:
            Tuple of (database entity if exists, action to take)
        """
        # Check if the entity already exists in the database
        db_entity = await crud.entity.get_by_entity_and_sync_id(
            db=db, entity_id=entity.entity_id, sync_id=sync_context.sync.id
        )

        if db_entity:
            # Check if the entity has been updated
            if db_entity.hash != entity.hash:
                # Entity has been updated, so we need to update it
                action = DestinationAction.UPDATE
            else:
                # Entity is the same, so we keep it
                action = DestinationAction.KEEP
        else:
            # Entity does not exist in the database, so we need to insert it
            action = DestinationAction.INSERT

        return db_entity, action

    async def _persist_entity(
        self,
        processed_entity: BaseEntity,
        db_entity: Any,
        action: DestinationAction,
        sync_context: SyncContext,
        db: AsyncSession,
    ) -> None:
        """Persist the entity to the database and destination.

        Args:
            processed_entity: The processed entity
            db_entity: Existing database entity if any
            action: The action to take (INSERT, UPDATE, KEEP)
            sync_context: The sync context
            db: Database session
        """
        # Update the entity with its action
        processed_entity.action = action.value.lower()

        if action == DestinationAction.INSERT:
            # Insert into database
            new_db_entity = await crud.entity.create(
                db=db,
                obj_in=schemas.EntityCreate(
                    sync_id=sync_context.sync.id,
                    entity_id=processed_entity.entity_id,
                    hash=processed_entity.hash,
                ),
                organization_id=sync_context.sync.organization_id,
            )
            processed_entity.db_entity_id = new_db_entity.id
            sync_context.progress.inserted += 1

            # Insert into destination if available
            if hasattr(sync_context, "destination") and sync_context.destination:
                await sync_context.destination.insert(processed_entity)

        elif action == DestinationAction.UPDATE:
            # Update in database
            await crud.entity.update(
                db=db,
                db_obj=db_entity,
                obj_in=schemas.EntityUpdate(hash=processed_entity.hash),
            )
            processed_entity.db_entity_id = db_entity.id
            sync_context.progress.updated += 1

            # Update in destination if available
            if hasattr(sync_context, "destination") and sync_context.destination:
                # For destinations, an update is usually delete + insert
                await sync_context.destination.delete(db_entity.id)
                await sync_context.destination.insert(processed_entity)

        # For KEEP action, we don't need to do anything


sync_orchestrator = SyncOrchestrator()
