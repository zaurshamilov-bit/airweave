"""Module for data synchronization."""

import asyncio
from typing import Any

from app import crud, schemas
from app.core.logging import logger
from app.db.session import get_db_context
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

                # Create a semaphore to limit concurrent tasks
                semaphore = asyncio.Semaphore(MAX_WORKERS)

                # Create async stream and use it as a context manager
                async with AsyncSourceStream(sync_context.source.generate_entities()) as stream:
                    try:
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

                            # Set up proper completion callback with error handling
                            def task_done_callback(completed_task):
                                pending_tasks.discard(completed_task)
                                # Handle any exceptions
                                if not completed_task.cancelled() and completed_task.exception():
                                    entity_id = getattr(
                                        completed_task.entity, "entity_id", "unknown"
                                    )
                                    logger.error(
                                        f"Task for entity {entity_id} failed: "
                                        f"{completed_task.exception()}"
                                    )

                            task.add_done_callback(task_done_callback)

                            # If we have too many pending tasks, wait for some to complete
                            if len(pending_tasks) >= MAX_WORKERS * 2:
                                done, pending = await asyncio.wait(
                                    pending_tasks,
                                    return_when=asyncio.FIRST_COMPLETED,
                                    timeout=0.5,
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

                        # Wait for any remaining tasks with proper error handling
                        if pending_tasks:
                            logger.info(f"Waiting for {len(pending_tasks)} remaining tasks")
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

                    except Exception as e:
                        logger.error(f"Error during sync: {e}")
                        raise
                    finally:
                        # Ensure we finalize progress
                        await sync_context.progress.finalize()

                # Publish final progress
                await sync_context.progress.finalize()
                return sync_context.sync

        except Exception as e:
            logger.error(f"Error during sync: {e}")
            raise

    async def _process_entity_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        entity: Any,
        source_node: Any,
        sync_context: SyncContext,
        db: Any,
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
            return await self._process_entity(entity, source_node, sync_context, db)

    async def _process_entity(
        self, entity: Any, source_node: Any, sync_context: SyncContext, db: Any
    ) -> Any:
        """Process a single entity through the DAG.

        Args:
            entity: Entity to process
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session

        Returns:
            List of processed results
        """
        processed_entities = await sync_context.router.process_entity(source_node.id, entity)
        results = []

        for processed_entity in processed_entities:
            result = await self._handle_entity_action(processed_entity, sync_context, db)
            results.append(result)

        return results

    async def _handle_entity_action(
        self, processed_entity: Any, sync_context: SyncContext, db: Any
    ) -> Any:
        """Handle entity based on its action (insert or update).

        Args:
            processed_entity: The processed entity with action
            sync_context: The sync context
            db: Database session

        Returns:
            The processed entity with db_entity_id set
        """
        if processed_entity.action == "insert":
            return await self._handle_insert(processed_entity, sync_context, db)
        elif processed_entity.action == "update":
            return await self._handle_update(processed_entity, sync_context, db)
        return processed_entity

    async def _handle_insert(
        self, processed_entity: Any, sync_context: SyncContext, db: Any
    ) -> Any:
        """Handle insert action for an entity.

        Args:
            processed_entity: The processed entity
            sync_context: The sync context
            db: Database session

        Returns:
            The processed entity with db_entity_id set
        """
        sync_context.progress.inserted += 1
        # Create new DB entity
        db_entity = await crud.entity.create(
            db=db,
            obj_in=schemas.EntityCreate(
                sync_id=sync_context.sync.id,
                entity_id=processed_entity.entity_id,
                hash=processed_entity.hash,
            ),
            organization_id=sync_context.sync.organization_id,
        )
        processed_entity.db_entity_id = db_entity.id
        return processed_entity

    async def _handle_update(
        self, processed_entity: Any, sync_context: SyncContext, db: Any
    ) -> Any:
        """Handle update action for an entity.

        Args:
            processed_entity: The processed entity
            sync_context: The sync context
            db: Database session

        Returns:
            The processed entity with db_entity_id set
        """
        sync_context.progress.updated += 1
        # Update existing DB entity
        await crud.entity.update(
            db=db,
            db_obj=processed_entity.db_entity,
            obj_in=schemas.EntityUpdate(hash=processed_entity.hash),
        )
        processed_entity.db_entity_id = processed_entity.db_entity.id
        return processed_entity


sync_orchestrator = SyncOrchestrator()
