"""Default file transformer."""

from typing import AsyncGenerator

from app.core.logging import logger
from app.platform.decorators import transformer
from app.platform.entities._base import ChildEntity, FileEntity, ParentEntity
from app.platform.file_handlers.file_converter import file_converter


@transformer(name="File Chunker", short_name="file_chunker")
async def file_chunker(file: FileEntity) -> AsyncGenerator[ParentEntity | ChildEntity, None]:
    """Default file chunker that converts files to markdown chunks.

    This transformer:
    1. Takes a FileEntity as input
    2. Converts the file to markdown using MarkItDown
    3. Splits the markdown into logical chunks
    4. Yields each chunk as a ChunkEntity
    """
    if not file.local_path:
        # If no local path, just yield the file entity as is
        logger.error(f"File {file.name} has no local path")
        return

    # Convert file to markdown chunks
    md = await file_converter.convert_to_markdown(file.local_path)
    yield md
