"""Sync cursor module for tracking sync progress."""

from uuid import UUID


class SyncCursor:
    """Cursor for a sync.

    This class is used to track the progress of a sync.
    """

    def __init__(self, sync_id: UUID):
        """Initialize a sync cursor with the given sync ID."""
        self.sync_id = sync_id
        self.cursor = 0

    def set_cursor(self, cursor: int):
        """Set the cursor position to the given value."""
        self.cursor = cursor

    def get_cursor(self) -> int:
        """Get the current cursor position."""
        return self.cursor
