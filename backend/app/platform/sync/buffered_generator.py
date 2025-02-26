"""Module for data synchronization."""

import asyncio
from typing import AsyncGenerator, Generic, List, TypeVar

from app.core.logging import logger
from app.platform.entities._base import BaseEntity

T = TypeVar("T", bound=BaseEntity)


class BufferedStreamGenerator(Generic[T]):
    """Buffers an async generator into chunks.

    Continues to generate items in the background, while consumer is using the buffer.
    """

    def __init__(
        self,
        source_generator: AsyncGenerator[T, None],
        chunk_size: int = 100,
        max_buffer_chunks: int = 10,
    ):
        """Initialize the buffered stream generator.

        Args:
            source_generator: The source async generator
            chunk_size: Number of items to yield in each chunk
            max_buffer_chunks: Maximum number of chunks to buffer
                (max_buffer = chunk_size * max_buffer_chunks)
        """
        self.source_generator = source_generator
        self.chunk_size = chunk_size
        self.max_buffer_size = chunk_size * max_buffer_chunks
        self.buffer: List[T] = []
        self.buffer_lock = asyncio.Lock()
        self.producer_task = None
        self.is_producing = True
        self.is_source_exhausted = False

    async def _producer(self):
        """Background task that fills the buffer from the source generator."""
        try:
            async for item in self.source_generator:
                async with self.buffer_lock:
                    # Wait if buffer is full
                    while len(self.buffer) >= self.max_buffer_size and self.is_producing:
                        await asyncio.sleep(0.1)

                    if not self.is_producing:
                        logger.info("Producer stopped")
                        break

                    self.buffer.append(item)

            self.is_source_exhausted = True
            logger.info("Source generator exhausted")
        except Exception as e:
            logger.error(f"Error in producer: {e}")
            raise e

    async def start(self):
        """Start the background producer task."""
        self.producer_task = asyncio.create_task(self._producer())

    async def stop(self):
        """Stop the producer and clean up resources."""
        self.is_producing = False
        if self.producer_task:
            await self.producer_task

    async def get_chunks(self) -> AsyncGenerator[List[T], None]:
        """Get chunks of items from the buffer."""
        if not self.producer_task:
            await self.start()

        while True:
            chunk = []

            # Get items from buffer up to chunk_size
            async with self.buffer_lock:
                items_to_take = min(self.chunk_size, len(self.buffer))
                if items_to_take > 0:
                    chunk = self.buffer[:items_to_take]
                    self.buffer = self.buffer[items_to_take:]

            # If we got items, yield them
            if chunk:
                yield chunk
            # If no items and source is exhausted, we're done
            elif self.is_source_exhausted and not self.buffer:
                break
            # Otherwise wait a bit for buffer to fill
            else:
                await asyncio.sleep(0.1)
