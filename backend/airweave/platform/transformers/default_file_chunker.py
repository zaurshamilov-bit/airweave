"""Default file transformer using Chonkie for improved semantic chunking."""

import os

from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules, SemanticChunker

from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import ChunkEntity, FileEntity, ParentEntity
from airweave.platform.file_handling.conversion.factory import document_converter
from airweave.platform.transformers.utils import MAX_CHUNK_SIZE, count_tokens

# Module-level shared chunker
_shared_semantic_chunker = None


def get_recursive_chunker():
    """Create a RecursiveChunker for markdown with custom rules."""
    # Use a very large value to focus on structure rather than size
    structure_based_size = 1000000  # Effectively unlimited

    # Custom markdown chunking rules
    custom_rules = RecursiveRules(
        [
            RecursiveLevel(
                delimiters=["\n# "],
                include_delim="next",  # Include the delimiter in the next chunk
            ),
            RecursiveLevel(delimiters=["\n## "], include_delim="next"),
            RecursiveLevel(delimiters=["\n### "], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n- ", "\n* ", "\n1. "], include_delim="next"),
            RecursiveLevel(delimiters=["```"], include_delim="both"),
            RecursiveLevel(delimiters=[". ", "? ", "! "], include_delim="prev"),
        ]
    )

    return RecursiveChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=structure_based_size,
        rules=custom_rules,
        min_characters_per_chunk=100,
    )


def get_shared_semantic_chunker(max_chunk_size: int = MAX_CHUNK_SIZE):
    """Get or create a shared semantic chunker."""
    global _shared_semantic_chunker
    if _shared_semantic_chunker is None or _shared_semantic_chunker.chunk_size != max_chunk_size:
        _shared_semantic_chunker = SemanticChunker(
            embedding_model="text-embedding-ada-002",
            chunk_size=max_chunk_size,
            threshold=0.5,
            mode="window",
            min_sentences=1,
            similarity_window=2,
        )
    return _shared_semantic_chunker


async def _process_file_content(file: FileEntity) -> str:
    """Process file content and convert to text if needed."""
    if not file.local_path:
        logger.error(f"File {file.name} has no local path")
        return ""

    # Check if the file is already markdown
    _, extension = os.path.splitext(file.local_path)
    extension = extension.lower()

    if extension == ".md":
        # File is already markdown, read it directly
        logger.info(f"File {file.name} is already markdown, reading directly")
        with open(file.local_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        # Convert file to markdown using the document converter
        result = await document_converter.convert(file.local_path)
        if not result or not result.text_content:
            logger.warning(f"No content extracted from file {file.name}")
            return ""
        return result.text_content


def _chunk_text_content(text_content: str) -> list[str]:
    """Chunk text content using recursive and semantic chunkers."""
    # Step 1: Initial chunking with RecursiveChunker
    recursive_chunker = get_recursive_chunker()
    initial_chunks = recursive_chunker.chunk(text_content)

    # Step 2: Apply semantic chunking if any chunks are still too large
    final_chunk_texts = []
    semantic_chunker = None

    for chunk in initial_chunks:
        if chunk.token_count <= MAX_CHUNK_SIZE:
            final_chunk_texts.append(chunk.text)
        else:
            # Use shared semantic chunker
            if not semantic_chunker:
                semantic_chunker = get_shared_semantic_chunker(MAX_CHUNK_SIZE)

            # Apply semantic chunking to the large chunk
            semantic_chunks = semantic_chunker.chunk(chunk.text)
            final_chunk_texts.extend([sc.text for sc in semantic_chunks])

    return final_chunk_texts


@transformer(name="File Chunker")
async def file_chunker(file: FileEntity) -> list[ParentEntity | ChunkEntity]:
    """Default file chunker that converts files to markdown chunks using Chonkie.

    This transformer:
    1. Takes a FileEntity as input
    2. Converts the file to markdown using AsyncMarkItDown (or reads directly if already markdown)
    3. Uses Chonkie for intelligent chunking with a two-step approach:
       - First uses RecursiveChunker with markdown rules
       - Then applies semantic chunking if chunks are too large
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

    try:
        text_content = await _process_file_content(file)

        if not text_content or not text_content.strip():
            logger.warning(f"No text content found in file {file.name}")
            return []

        final_chunk_texts = _chunk_text_content(text_content)

        # Create parent entity for the file using all fields from original entity
        file_data = file.model_dump()
        file_data.update(
            {
                "number_of_chunks": len(final_chunk_texts),
            }
        )
        parent = FileParentClass(**file_data)
        produced_entities.append(parent)

        for i, chunk_text in enumerate(final_chunk_texts):
            if not chunk_text.strip():
                continue

            chunk = FileChunkClass(
                name=f"{file.name} - Chunk {i + 1}",
                entity_id=file.entity_id,
                sync_id=file.sync_id,
                parent_entity_id=parent.entity_id,
                parent_db_entity_id=parent.db_entity_id,
                md_content=chunk_text,
                md_type="text",
                md_position=i,
                md_parent_title=file.name,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(final_chunk_texts),
                },
            )
            produced_entities.append(chunk)

    except Exception as e:
        logger.error(f"Error processing file {file.name}: {str(e)}")
        raise e

    return produced_entities
