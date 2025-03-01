"""Default file transformer."""

from app.core.logging import logger
from app.platform.decorators import transformer
from app.platform.entities._base import ChunkEntity, FileEntity, ParentEntity
from app.platform.file_handling.async_markitdown import markitdown


@transformer(name="File Chunker")
async def file_chunker(file: FileEntity) -> list[ParentEntity | ChunkEntity]:
    """Default file chunker that converts files to markdown chunks.

    This transformer:
    1. Takes a FileEntity as input
    2. Converts the file to markdown using AsyncMarkItDown
    3. Splits the markdown into logical chunks
    4. Yields each chunk as a ChunkEntity

    Args:
        file: The FileEntity to process

    Returns:
        list[ParentEntity | ChunkEntity]: The processed chunks
    """
    file_class = type(file)
    produced_entities = []

    # Get the specific parent/child models for this file entity type
    FileParentClass, FileChunkClass = file_class.create_parent_chunk_models()

    if not file.local_path:
        logger.error(f"File {file.name} has no local path")
        return

    try:
        # Convert file to markdown
        result = await markitdown.convert(file.local_path)

        if not result or not result.text_content:
            logger.warning(f"No content extracted from file {file.name}")
            return

        # Split content into chunks and yield as child entities
        chunks = _split_into_chunks(result.text_content)

        # Create parent entity for the file using all fields from original entity
        file_data = file.model_dump()
        file_data.update(
            {
                "number_of_chunks": len(chunks),
            }
        )
        parent = FileParentClass(**file_data)
        produced_entities.append(parent)

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            chunk = FileChunkClass(
                name=f"{file.name} - Chunk {i + 1}",
                parent_entity_id=parent.entity_id,
                parent_db_entity_id=parent.db_entity_id,
                md_content=chunk,
                md_type="text",
                md_position=i,
                md_parent_title=file.name,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )
            produced_entities.append(chunk)

    except Exception as e:
        logger.error(f"Error processing file {file.name}: {str(e)}")
        raise e

    return produced_entities


def _split_by_headers(content: str, max_chunk_size: int) -> list[str]:
    """Split content by headers and size limits."""
    chunks = []
    current_chunk = []
    current_size = 0

    for line in content.split("\n"):
        if (line.startswith("#") and current_size > 0) or current_size >= max_chunk_size:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(line)
        current_size += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks


def _split_into_chunks(content: str, max_chunk_size: int = 5000) -> list[str]:
    """Split markdown content into logical chunks."""
    chunks = _split_by_headers(content, max_chunk_size)
    final_chunks = []

    for chunk in chunks:
        if len(chunk) <= max_chunk_size:
            final_chunks.append(chunk)
            continue

        # Split oversized chunks by paragraphs
        paragraphs = chunk.split("\n\n")
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            if current_size + len(para) > max_chunk_size and current_chunk:
                final_chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(para)
            current_size += len(para) + 2

        if current_chunk:
            final_chunks.append("\n\n".join(current_chunk))

    return final_chunks
