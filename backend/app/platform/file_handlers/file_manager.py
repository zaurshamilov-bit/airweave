"""Service for managing temporary files."""

import hashlib
import os
from typing import AsyncIterator
from uuid import uuid4

import aiofiles

from app.core.logging import logger
from app.platform.entities._base import BaseEntity, FileEntity


class FileManager:
    """Manages temporary file operations."""

    def __init__(self):
        """Initialize the file manager."""
        self.base_temp_dir = "/tmp/airweave"
        self._ensure_base_dir()

    def _ensure_base_dir(self):
        """Ensure the base temporary directory exists."""
        os.makedirs(self.base_temp_dir, exist_ok=True)

    async def handle_file_entity(
        self,
        stream: AsyncIterator[bytes],
        entity: FileEntity,
        chunk_size: int = 8192,
    ) -> FileEntity:
        """Process a file entity by saving its stream and enriching the entity.

        Args:
            stream: An async iterator yielding file chunks
            entity: The file entity to process
            chunk_size: Size of chunks to process

        Returns:
            The enriched file entity
        """
        if not entity.download_url:
            return entity

        file_uuid = uuid4()
        safe_filename = self._safe_filename(entity.name)
        temp_path = os.path.join(self.base_temp_dir, f"{file_uuid}-{safe_filename}")

        try:
            downloaded_size = 0
            async with aiofiles.open(temp_path, "wb") as f:
                async for chunk in stream:
                    await f.write(chunk)
                    downloaded_size += len(chunk)

                    # Log progress for large files
                    if entity.total_size and entity.total_size > 10 * 1024 * 1024:  # 10MB
                        progress = (downloaded_size / entity.total_size) * 100
                        logger.debug(
                            f"Saving {entity.name}: {progress:.1f}% "
                            f"({downloaded_size}/{entity.total_size} bytes)"
                        )

            # Calculate checksum and update entity
            with open(temp_path, "rb") as f:
                content = f.read()
                entity.checksum = hashlib.sha256(content).hexdigest()
                entity.local_path = temp_path
                entity.file_uuid = file_uuid
                entity.total_size = downloaded_size  # Update with actual size

        except Exception as e:
            logger.error(f"Error saving file {entity.name}: {str(e)}")
            # Clean up partial file if it exists
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return entity

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Create a safe version of a filename."""
        # Replace potentially problematic characters
        safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
        return safe_name.strip()


# Global instance
file_manager = FileManager()


async def handle_file_entity(file_entity: FileEntity, stream: AsyncIterator[bytes]) -> BaseEntity:
    """Utility function to handle a file entity with its stream.

    This is a convenience function that can be used directly in source implementations.

    Args:
        file_entity: The file entity
        stream: The file stream

    Returns:
        The processed entity
    """
    return await file_manager.handle_file_entity(stream, file_entity)
