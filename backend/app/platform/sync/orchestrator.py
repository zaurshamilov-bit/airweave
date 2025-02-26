"""Module for data synchronization."""

import asyncio
from typing import Any, List

from app import crud, schemas
from app.core.logging import logger
from app.db.session import get_db_context
from app.platform.sync.buffered_generator import BufferedStreamGenerator
from app.platform.sync.context import SyncContext


class SyncOrchestrator:
    """Main service for data synchronization."""

    async def run(
        self,
        sync_context: SyncContext,
        max_workers: int = 5,
    ) -> schemas.Sync:
        """Run a sync with the new DAG-based routing.

        Args:
            sync_context: The sync context
            max_workers: Maximum number of concurrent workers
        """
        try:
            async with get_db_context() as db:
                # Get source node from DAG
                source_node = sync_context.dag.get_source_node()

                # Create a semaphore to limit concurrent tasks
                semaphore = asyncio.Semaphore(max_workers)

                # Create buffered stream generator
                buffered_stream = BufferedStreamGenerator(sync_context.source.generate_entities())

                # Start the producer
                await buffered_stream.start()

                try:
                    # Process chunks in parallel with controlled concurrency
                    async for chunk in buffered_stream.get_chunks():
                        async with semaphore:
                            await self._process_chunk(chunk, source_node, sync_context, db)
                finally:
                    # Ensure we stop the producer
                    await buffered_stream.stop()
                    await sync_context.progress.finalize()

                # Publish final progress
                await sync_context.progress.finalize()
                return sync_context.sync
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            raise e

    async def _process_chunk(
        self, entities: List[Any], source_node: Any, sync_context: SyncContext, db: Any
    ) -> List[Any]:
        """Process a chunk of entities in parallel.

        Args:
            entities: List of entities to process
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session

        Returns:
            List of processed results
        """
        tasks = []
        for entity in entities:
            tasks.append(self._process_entity(entity, source_node, sync_context, db))
        return await asyncio.gather(*tasks)

    async def _process_entity(
        self, entity: Any, source_node: Any, sync_context: SyncContext, db: Any
    ) -> List[Any]:
        """Process a single entity through the DAG.

        Args:
            entity: Entity to process
            source_node: The source node from the DAG
            sync_context: The sync context
            db: Database session

        Returns:
            List of processed results
        """
        processed_entities = await sync_context.router.process_entity(source_node, entity)
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
