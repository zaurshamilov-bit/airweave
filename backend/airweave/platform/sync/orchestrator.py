"""Module for data synchronization with improved architecture."""

import asyncio
from datetime import datetime

from airweave import schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


# Refactored Orchestrator
class SyncOrchestrator:
    """Main service for data synchronization with improved architecture."""

    def __init__(
        self,
        entity_processor: EntityProcessor,
        worker_pool: AsyncWorkerPool,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator with provided components.

        Args:
            entity_processor: The entity processor to use
            worker_pool: The worker pool to use
            sync_context: The sync context with all required resources
        """
        self.worker_pool = worker_pool
        self.entity_processor = entity_processor
        self.sync_context = sync_context

    async def run(self) -> schemas.Sync:
        """Run a sync with full async processing."""
        try:
            self.sync_context.logger.info(
                f"Starting sync job {self.sync_context.sync_job.id} for sync "
                f"{self.sync_context.sync.id}"
            )

            # Mark job as started
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.IN_PROGRESS,
                current_user=self.sync_context.current_user,
                started_at=datetime.now(),
            )

            # Get source node from DAG
            source_node = self.sync_context.dag.get_source_node()

            # Process entity stream
            await self._process_entity_stream(source_node)

            # Use sync_job_service to update job status
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.COMPLETED,
                current_user=self.sync_context.current_user,
                completed_at=datetime.now(),
                stats=(
                    self.sync_context.progress.stats
                    if hasattr(self.sync_context.progress, "stats")
                    else None
                ),
            )

            self.sync_context.logger.info(
                f"Completed sync job {self.sync_context.sync_job.id} successfully"
            )
            return self.sync_context.sync

        except Exception as e:
            self.sync_context.logger.error(f"Error during sync: {e}")

            # Use sync_job_service to update job status
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.FAILED,
                current_user=self.sync_context.current_user,
                error=str(e),
                failed_at=datetime.now(),
                stats=(
                    self.sync_context.progress.stats
                    if hasattr(self.sync_context.progress, "stats")
                    else None
                ),
            )

            raise

    async def _process_entity_stream(self, source_node) -> None:
        """Process stream of entities from source with buffering for true parallelism."""
        self.sync_context.logger.info(
            f"Starting entity stream processing from source {self.sync_context.source._name}"
        )

        # Create entity buffer for producer/consumer pattern
        entity_buffer = asyncio.Queue(maxsize=50)
        producer_error_ref = {"error": None}

        # Create tasks
        producer_task = asyncio.create_task(self._run_producer(entity_buffer, producer_error_ref))

        num_consumers = min(10, self.worker_pool.max_workers // 10)
        consumer_tasks = [
            asyncio.create_task(self._run_consumer(entity_buffer, source_node))
            for _ in range(num_consumers)
        ]

        logger.info(f"🚀 ORCHESTRATOR_START Started 1 producer and {num_consumers} consumers")

        # Run and handle errors
        error_occurred = await self._wait_for_tasks(
            producer_task, consumer_tasks, producer_error_ref
        )

        # Finalize progress
        await self.sync_context.progress.finalize(is_complete=not error_occurred)

    async def _run_producer(self, entity_buffer: asyncio.Queue, error_ref: dict) -> None:
        """Producer task that fills the entity buffer."""
        try:
            async with AsyncSourceStream(
                self.sync_context.source.generate_entities(), logger=self.sync_context.logger
            ) as stream:
                async for entity in stream.get_entities():
                    logger.info(
                        f"📨 PRODUCER_ENTITY_RECEIVED Entity: {entity.entity_id} "
                        f"(type: {type(entity).__name__})"
                    )
                    await entity_buffer.put(entity)
                    logger.info(
                        f"📥 PRODUCER_BUFFERED Entity {entity.entity_id} "
                        f"(buffer size: {entity_buffer.qsize()})"
                    )
        except Exception as e:
            error_ref["error"] = e
            self.sync_context.logger.error(f"Error in producer: {e}")
            raise
        finally:
            await entity_buffer.put(None)
            logger.info("🏁 PRODUCER_COMPLETE Producer finished")

    async def _run_consumer(self, entity_buffer: asyncio.Queue, source_node) -> None:
        """Consumer task that processes entities from the buffer."""
        while True:
            entity = await entity_buffer.get()

            if entity is None:
                await entity_buffer.put(None)  # Put back for other consumers
                break

            logger.info(
                f"📤 CONSUMER_PROCESSING Entity: {entity.entity_id} "
                f"(buffer size: {entity_buffer.qsize()})"
            )

            if getattr(entity, "should_skip", False):
                logger.info(f"⏭️  CONSUMER_SKIP Entity: {entity.entity_id}")
                await self.sync_context.progress.increment("skipped")
                continue

            # Submit for processing
            await self._submit_entity_with_throttling(entity, source_node)

    async def _submit_entity_with_throttling(self, entity, source_node) -> None:
        """Submit entity to worker pool with throttling."""
        logger.info(
            f"📤 CONSUMER_SUBMIT Submitting entity {entity.entity_id} "
            f"to worker pool (pending: {len(self.worker_pool.pending_tasks)})"
        )

        await self.worker_pool.submit(
            self._process_single_entity,
            entity=entity,
            source_node=source_node,
        )

        # Check throttling
        current_pending = len(self.worker_pool.pending_tasks)
        if current_pending >= self.worker_pool.max_workers * 0.8:
            logger.info(
                f"🚦 CONSUMER_THROTTLE High pending tasks ({current_pending}), slowing consumption"
            )
            await self.worker_pool.wait_for_batch(timeout=0.1)

    async def _wait_for_tasks(self, producer_task, consumer_tasks, producer_error_ref) -> bool:
        """Wait for tasks and handle errors."""
        error_occurred = False

        try:
            await asyncio.gather(*consumer_tasks)
            await producer_task

            if producer_error_ref["error"]:
                raise producer_error_ref["error"]

            await self.worker_pool.wait_for_completion()
            self.sync_context.logger.info("All entity processing tasks completed.")

        except Exception as e:
            self.sync_context.logger.error(f"Error during entity stream processing: {e}")
            error_occurred = True
            raise
        finally:
            producer_task.cancel()
            for task in consumer_tasks:
                task.cancel()

        return error_occurred

    async def _process_single_entity(self, entity: BaseEntity, source_node) -> None:
        """Process a single entity through the pipeline."""
        # Create a new database session scope for this task
        async with get_db_context() as db:
            # Process the entity through the pipeline

            # No try-catch needed here anymore - entity_processor handles all errors gracefully
            await self.entity_processor.process(
                entity=entity, source_node=source_node, sync_context=self.sync_context, db=db
            )
