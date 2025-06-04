"""Worker pool implementation for controlling async concurrency."""

import asyncio
from typing import Any, Callable

from airweave.core.logging import logger


class AsyncWorkerPool:
    """Manages a pool of workers with controlled concurrency.

    This class limits how many async tasks can run at once using a semaphore,
    preventing system overload when processing many items in parallel.
    """

    def __init__(self, max_workers: int = 100):
        """Initialize worker pool with concurrency control.

        Args:
            max_workers: Maximum number of tasks allowed to run concurrently
        """
        self.semaphore = asyncio.Semaphore(max_workers)
        self.pending_tasks = set()
        self.max_workers = max_workers

    async def submit(self, coro: Callable, *args, **kwargs) -> asyncio.Task:
        """Submit a coroutine to be executed by the worker pool.

        Creates a task, adds it to our tracking set, and returns it.
        Tasks run with controlled concurrency through the semaphore.
        """
        task = asyncio.create_task(self._run_with_semaphore(coro, *args, **kwargs))
        self.pending_tasks.add(task)
        task.add_done_callback(self._handle_task_completion)
        return task

    async def _run_with_semaphore(self, coro: Callable, *args, **kwargs) -> Any:
        """Run a coroutine with semaphore control.

        Acquires a semaphore before running the coroutine, limiting concurrency.
        Semaphore is automatically released when coroutine completes.
        """
        async with self.semaphore:
            return await coro(*args, **kwargs)

    def _handle_task_completion(self, task: asyncio.Task) -> None:
        """Handle task completion and clean up."""
        self.pending_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error(f"Task failed: {task.exception()}")

    async def wait_for_batch(self, timeout: float = 0.5) -> None:
        """Wait for some tasks to complete, processing them as they finish."""
        if not self.pending_tasks:
            return

        # Wait for the first few tasks to complete, not ALL of them
        done, _ = await asyncio.wait(
            self.pending_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout
        )

        # Tasks are already completed and removed by callback, no need to process them again
        # The callback handles cleanup automatically

    async def wait_for_completion(self) -> None:
        """Wait for all tasks to complete, processing results as they finish."""
        while self.pending_tasks:
            # Process tasks as they complete instead of waiting for ALL to complete
            done, _ = await asyncio.wait(
                self.pending_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=1.0
            )

            # Tasks are already completed and removed by callback, no need to process them again
            # The callback handles cleanup and error logging automatically
