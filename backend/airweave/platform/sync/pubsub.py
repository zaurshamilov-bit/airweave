"""Pubsub for sync jobs using Redis backend."""

import asyncio
from uuid import UUID

from pydantic import BaseModel

from airweave.core.logging import ContextualLogger
from airweave.core.pubsub import core_pubsub


class SyncProgressUpdate(BaseModel):
    """Sync progress update data structure.

    This is sent over the pubsub channel to subscribers
    """

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    entities_encountered: dict[str, int] = {}
    is_complete: bool = False
    is_failed: bool = False


PUBLISH_THRESHOLD = 3


class SyncProgress:
    """Tracks sync progress and automatically publishes updates."""

    def __init__(self, job_id: UUID, logger: ContextualLogger):
        """Initialize the SyncProgress instance.

        Args:
            job_id: The sync job ID
            logger: Contextual logger with sync metadata
        """
        self.job_id = job_id
        self.stats = SyncProgressUpdate()
        self._last_published = 0
        self._publish_threshold = PUBLISH_THRESHOLD
        # CRITICAL FIX: Add async lock to prevent race conditions
        self._lock = asyncio.Lock()
        self.logger = logger
        self._last_status_update = 0
        self._status_update_interval = 50  # Log status every 50 items

    def __getattr__(self, name: str) -> int:
        """Get counter value for any stat."""
        return getattr(self.stats, name)

    async def increment(self, stat_name: str, amount: int = 1) -> None:
        """Increment a counter and trigger update if threshold reached.

        Uses async lock to prevent race conditions from concurrent workers.
        """
        async with self._lock:  # CRITICAL FIX: Synchronize access
            current_value = getattr(self.stats, stat_name, 0)
            setattr(self.stats, stat_name, current_value + amount)

            # Include ALL operations in threshold calculation (including skipped)
            total_ops = sum(
                [
                    self.stats.inserted,
                    self.stats.updated,
                    self.stats.deleted,
                    self.stats.kept,
                    self.stats.skipped,
                ]
            )

            # Check if we should publish
            if total_ops - self._last_published >= self._publish_threshold:
                self.logger.debug(
                    f"Progress threshold reached: {total_ops} total ops, publishing update"
                )
                await self._publish()
                self._last_published = total_ops

            # Check if we should log a status update (every 50 items)
            if total_ops - self._last_status_update >= self._status_update_interval:
                await self._log_status_update(total_ops)
                self._last_status_update = total_ops

    async def _publish(self) -> None:
        """Publish current progress."""
        await core_pubsub.publish("sync_job", self.job_id, self.stats.model_dump())

    async def finalize(self, is_complete: bool = True) -> None:
        """Publish final progress."""
        async with self._lock:  # Ensure finalize is also synchronized
            self.stats.is_complete = is_complete
            self.stats.is_failed = not is_complete

            # Log final status
            total_ops = sum(
                [
                    self.stats.inserted,
                    self.stats.updated,
                    self.stats.deleted,
                    self.stats.kept,
                    self.stats.skipped,
                ]
            )

            if is_complete:
                self.logger.info(
                    f"✅ Sync completed successfully - Total: {total_ops} | "
                    f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
                    f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
                    f"Skipped: {self.stats.skipped}"
                )
            else:
                self.logger.error(
                    f"❌ Sync failed - Progress before failure - Total: {total_ops} | "
                    f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
                    f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
                    f"Skipped: {self.stats.skipped}"
                )

            await self._publish()

    def to_dict(self) -> dict:
        """Convert progress to a dictionary."""
        return self.stats.model_dump()

    async def update_entities_encountered_count(
        self, entities_encountered: dict[str, set[str]]
    ) -> None:
        """Update the entities encountered tracking."""
        async with self._lock:  # Synchronize this as well
            self.stats.entities_encountered = {
                entity_type: len(entity_ids)
                for entity_type, entity_ids in entities_encountered.items()
            }

    async def _log_status_update(self, total_ops: int) -> None:
        """Log a periodic status update.

        Args:
            total_ops: Total operations processed so far
        """
        # Calculate rate if possible
        rate_info = ""
        if hasattr(self, "_start_time"):
            elapsed = asyncio.get_event_loop().time() - self._start_time
            if elapsed > 0:
                rate = total_ops / elapsed
                rate_info = f" | Rate: {rate:.1f} ops/sec"
        else:
            # Set start time on first status update
            self._start_time = asyncio.get_event_loop().time()

        # Log entity type breakdown if available
        entity_info = ""
        if self.stats.entities_encountered:
            entity_summary = ", ".join(
                [
                    f"{entity_type}: {count}"
                    for entity_type, count in self.stats.entities_encountered.items()
                ]
            )
            entity_info = f" | Entities: {entity_summary}"

        self.logger.info(
            f"📊 Sync progress - Total: {total_ops} | "
            f"Inserted: {self.stats.inserted} | Updated: {self.stats.updated} | "
            f"Deleted: {self.stats.deleted} | Kept: {self.stats.kept} | "
            f"Skipped: {self.stats.skipped}{rate_info}{entity_info}"
        )


# No module-level pubsub instance is needed; use core_pubsub directly
