"""Pubsub for sync jobs."""

import asyncio
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SyncProgressUpdate(BaseModel):
    """Sync progress update data structure."""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    already_sync: int = 0
    is_complete: bool = False  # Add completion flag


class SyncJobTopic:
    """Represents an active sync job's message stream."""

    def __init__(self, job_id: UUID):
        """Initialize topic."""
        self.job_id = job_id
        self.queues: list[asyncio.Queue] = []
        self.latest_update: Optional[SyncProgressUpdate] = None

    async def publish(self, update: SyncProgressUpdate) -> None:
        """Publish an update to all subscribers."""
        self.latest_update = update
        for queue in self.queues:
            await queue.put(update)

    async def add_subscriber(self) -> asyncio.Queue:
        """Add a new subscriber and send them the latest update if available."""
        queue = asyncio.Queue()
        self.queues.append(queue)
        if self.latest_update:
            await queue.put(self.latest_update)
        return queue

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber."""
        if queue in self.queues:
            self.queues.remove(queue)


class SyncPubSub:
    """Manages sync job topics and their subscribers."""

    def __init__(self) -> None:
        """Initialize the SyncPubSub instance."""
        self.topics: dict[UUID, SyncJobTopic] = {}

    def create_topic(self, job_id: UUID) -> None:
        """Create a new topic for a sync job. Called when sync starts."""
        if job_id not in self.topics:
            self.topics[job_id] = SyncJobTopic(job_id)

    def remove_topic(self, job_id: UUID) -> None:
        """Remove a topic when sync is complete."""
        if job_id in self.topics:
            del self.topics[job_id]

    async def publish(self, job_id: UUID, update: SyncProgressUpdate) -> None:
        """Publish an update to a specific job topic."""
        if job_id in self.topics:
            await self.topics[job_id].publish(update)
            # If the update indicates completion, schedule topic removal
            if update.is_complete:
                self.remove_topic(job_id)

    async def subscribe(self, job_id: UUID) -> Optional[asyncio.Queue]:
        """Subscribe to a job's updates if the topic exists."""
        if job_id in self.topics:
            return await self.topics[job_id].add_subscriber()
        return None

    def unsubscribe(self, job_id: UUID, queue: asyncio.Queue) -> None:
        """Remove a subscriber from a topic."""
        if job_id in self.topics:
            self.topics[job_id].remove_subscriber(queue)


# Create a global instance for the entire app
sync_pubsub = SyncPubSub()
