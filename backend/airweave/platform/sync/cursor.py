"""Sync cursor module for tracking sync progress."""

from uuid import UUID


class SyncCursor:
    """Cursor for a sync.

    This class is used to track the progress of a sync.
    """

    def __init__(
        self, sync_id: UUID, cursor_data: dict | None = None, cursor_field: str | None = None
    ):
        """Initialize a sync cursor with the given sync ID.

        Args:
            sync_id: The ID of the sync
            cursor_data: The stored cursor data from previous syncs
            cursor_field: The field name to use as cursor (e.g., 'updated_at')
        """
        self.sync_id = sync_id
        self.cursor_data = cursor_data or {}
        self.cursor_field = cursor_field
