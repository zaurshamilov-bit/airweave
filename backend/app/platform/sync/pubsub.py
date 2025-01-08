"""Pubsub for sync jobs."""

import asyncio

from pydantic import BaseModel


class SyncProgressUpdate(BaseModel):
    """Sync progress update data structure."""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    already_sync: int = 0


class SyncPubSub:
    """Keeps track of sync job updates and allows subscribers.

    Allows subscribers to receive updates via a queue-based approach.
    """

    def __init__(self) -> None:
        """Initialize the SyncPubSub instance."""
        self.listeners: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, job_id: str, updates: SyncProgressUpdate) -> None:
        """Called by the sync run method to publish updates."""
        if job_id not in self.listeners:
            return

        for queue in self.listeners[job_id]:
            await queue.put(updates)

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        """Called by an SSE endpoint to subscribe to updates for a sync job ID."""
        queue: asyncio.Queue = asyncio.Queue()
        self.listeners.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Remove an existing subscriber's queue once SSE connection closes."""
        if job_id in self.listeners:
            if queue in self.listeners[job_id]:
                self.listeners[job_id].remove(queue)
            if not self.listeners[job_id]:
                del self.listeners[job_id]


# Create a global instance for the entire app
sync_pubsub = SyncPubSub()
