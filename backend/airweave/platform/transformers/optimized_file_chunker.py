"""Optimized file chunker with faster semantic chunking."""

import asyncio
import os
from typing import List

from chonkie import RecursiveChunker, TokenChunker

from airweave.core.logging import ContextualLogger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import ChunkEntity, FileEntity, ParentEntity
from airweave.platform.file_handling.conversion.factory import document_converter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.transformers.utils import count_tokens

# Create optimized chunkers at module level
_token_chunker = None
_recursive_chunker = None

# OpenAI's actual limit
OPENAI_TOKEN_LIMIT = 8191
# Initial chunk size - we'll start large and re-chunk if needed
INITIAL_CHUNK_SIZE = 7500
# Minimum chunk size to avoid infinite recursion
MIN_CHUNK_SIZE = 500


def get_token_chunker(chunk_size: int):
    """Get or create a token chunker with specified size."""
    global _token_chunker
    if _token_chunker is None or _token_chunker.chunk_size != chunk_size:
        _token_chunker = TokenChunker(
            tokenizer_or_token_counter=count_tokens,
            chunk_size=chunk_size,
            chunk_overlap=100,  # Small overlap for context
        )
    return _token_chunker


def get_recursive_chunker(chunk_size: int):
    """Get or create a recursive chunker with specified size."""
    from chonkie import RecursiveLevel, RecursiveRules

    # Simpler rules for faster processing
    rules = RecursiveRules(
        [
            RecursiveLevel(delimiters=["\n\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n"], include_delim="next"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
        ]
    )

    return RecursiveChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=chunk_size,
        rules=rules,
        min_characters_per_chunk=100,
    )


def calculate_entity_token_size(entity: ChunkEntity) -> int:
    """Calculate the actual token size when entity is serialized for embedding.

    This mimics what happens when the entity is sent to OpenAI:
    The entity is converted to a storage dict and then to string.
    """
    # Get the storage dict (what actually gets sent)
    storage_dict = entity.to_storage_dict()
    # Convert to string (same as what happens before embedding)
    entity_string = str(storage_dict)
    # Count tokens
    return count_tokens(entity_string)


async def _process_file_content(
    file: FileEntity, entity_context: str, logger: ContextualLogger
) -> str:
    """Process file content and convert to text if needed."""
    if not file.local_path:
        logger.error(f"📂 CHUNKER_NO_PATH [{entity_context}] File has no local path")
        return ""

    _, extension = os.path.splitext(file.local_path)
    extension = extension.lower()

    if extension == ".md":
        logger.debug(f"📑 CHUNKER_READ_MD [{entity_context}] Reading markdown file directly")
        import aiofiles

        async with aiofiles.open(file.local_path, "r", encoding="utf-8") as f:
            content = await f.read()
        logger.debug(f"📖 CHUNKER_READ_DONE [{entity_context}] Read {len(content)} characters")
        return content
    else:
        logger.debug(f"🔄 CHUNKER_CONVERT [{entity_context}] Converting file to markdown")
        result = await document_converter.convert(file.local_path)
        if not result or not result.text_content:
            logger.warning(f"🚫 CHUNKER_CONVERT_EMPTY [{entity_context}] No content extracted")
            return ""
        logger.debug(
            f"✅ CHUNKER_CONVERT_DONE [{entity_context}] "
            f"Converted to {len(result.text_content)} characters"
        )
        return result.text_content


async def _chunk_text_adaptive(
    text_content: str,
    entity_context: str,
    logger: ContextualLogger,
    chunk_size: int = INITIAL_CHUNK_SIZE,
) -> List[str]:
    """Adaptively chunk text, starting with a target size."""
    logger.debug(
        f"🔧 CHUNKER_ADAPTIVE_START [{entity_context}] "
        f"Starting chunking with target size {chunk_size}"
    )

    # Clean problematic content first
    text_content = _clean_problematic_content(text_content, entity_context, logger)

    # Try recursive chunking first
    recursive_chunker = get_recursive_chunker(chunk_size)

    def _chunk_recursive(text: str):
        try:
            chunks = recursive_chunker.chunk(text)
            return [(chunk.text, chunk.token_count) for chunk in chunks]
        except Exception as e:
            logger.warning(
                f"⚠️  CHUNKER_RECURSIVE_FAIL [{entity_context}] Recursive chunking failed: {str(e)}"
            )
            return None

    chunk_result = await run_in_thread_pool(_chunk_recursive, text_content)

    if chunk_result is None:
        # Fallback to simple token chunking
        logger.debug(f"🔄 CHUNKER_FALLBACK [{entity_context}] Using token chunker as fallback")
        token_chunker = get_token_chunker(chunk_size)

        def _chunk_tokens(text: str):
            chunks = token_chunker.chunk(text)
            return [(chunk.text, chunk.token_count) for chunk in chunks]

        chunk_result = await run_in_thread_pool(_chunk_tokens, text_content)

    # Extract just the text
    final_chunks = [text for text, _ in chunk_result]

    logger.debug(f"📦 CHUNKER_ADAPTIVE_DONE [{entity_context}] Created {len(final_chunks)} chunks")
    return final_chunks


def _clean_problematic_content(text: str, entity_context: str, logger: ContextualLogger) -> str:
    """Remove base64 images and other content that inflates token count."""
    import re

    original_length = len(text)

    # Remove base64 image data but keep image references
    base64_pattern = r"!\[([^\]]*)\]\(data:image/[^;]+;base64,([^\)]+)\)"
    text = re.sub(base64_pattern, lambda m: f"[{m.group(1) or 'Image'}]", text)

    # Also handle HTML img tags with base64 data
    html_base64_pattern = r'<img[^>]+src="data:image/[^;]+;base64,([^"]+)"[^>]*>'
    text = re.sub(html_base64_pattern, "[Embedded Image]", text)

    cleaned_length = len(text)
    if cleaned_length < original_length:
        removed_chars = original_length - cleaned_length
        logger.debug(
            f"🧹 CHUNKER_CLEANED [{entity_context}] Removed {removed_chars:,} characters "
            f"of embedded data ({original_length:,} -> {cleaned_length:,} chars)"
        )

    return text


def _create_chunk_metadata(file: FileEntity, i: int, total_chunks: int) -> dict:
    """Create metadata for a chunk."""
    chunk_metadata = {
        "chunk_index": i,
        "total_chunks": total_chunks,
    }

    if hasattr(file, "original_url") and file.original_url:
        chunk_metadata.update(
            {
                "original_url": file.original_url,
                "web_title": getattr(file, "web_title", None),
                "web_description": getattr(file, "web_description", None),
                "crawl_metadata": getattr(file, "crawl_metadata", {}),
            }
        )

    return chunk_metadata


def _create_chunk_entity(
    file: FileEntity,
    parent: ParentEntity,
    chunk_text: str,
    i: int,
    chunk_metadata: dict,
    FileChunkClass: type,
) -> ChunkEntity:
    """Create a chunk entity."""
    md_parent_url = file.original_url if hasattr(file, "original_url") else None

    return FileChunkClass(
        name=f"{file.name} - Chunk {i + 1}",
        entity_id=file.entity_id,
        sync_id=file.sync_id,
        parent_entity_id=parent.entity_id,
        parent_db_entity_id=parent.db_entity_id,
        md_content=chunk_text,
        md_type="text",
        md_position=i,
        md_parent_title=file.name,
        md_parent_url=md_parent_url,
        metadata=chunk_metadata,
    )


async def _try_chunk_size(
    file: FileEntity,
    text_content: str,
    chunk_size: int,
    entity_context: str,
    logger: ContextualLogger,
    FileParentClass: type,
    FileChunkClass: type,
) -> tuple[bool, list[ChunkEntity]]:
    """Try to chunk with a specific size and validate all chunks fit."""
    logger.debug(f"✂️  CHUNKER_ATTEMPT [{entity_context}] Chunking with size {chunk_size}")

    final_chunk_texts = await _chunk_text_adaptive(text_content, entity_context, logger, chunk_size)

    # Create parent entity
    file_data = file.model_dump()
    file_data.update({"number_of_chunks": len(final_chunk_texts)})
    parent = FileParentClass(**file_data)

    # Test if chunks will fit when serialized
    all_chunks_fit = True
    test_chunks = []

    for i, chunk_text in enumerate(final_chunk_texts):
        if not chunk_text.strip():
            continue

        # Create test chunk entity
        chunk_metadata = _create_chunk_metadata(file, i, len(final_chunk_texts))
        chunk = _create_chunk_entity(file, parent, chunk_text, i, chunk_metadata, FileChunkClass)

        # Check actual serialized size
        actual_size = calculate_entity_token_size(chunk)

        if actual_size > OPENAI_TOKEN_LIMIT:
            logger.warning(
                f"❌ CHUNKER_TOO_LARGE [{entity_context}] Chunk {i + 1} is {actual_size} "
                f"tokens when serialized (limit: {OPENAI_TOKEN_LIMIT}). Need smaller chunks"
            )
            all_chunks_fit = False
            break
        else:
            logger.debug(
                f"✅ CHUNKER_SIZE_OK [{entity_context}] Chunk {i + 1} is {actual_size} "
                "tokens "
                f"({int(actual_size / OPENAI_TOKEN_LIMIT * 100)}% of limit)"
            )
            test_chunks.append(chunk)

    if all_chunks_fit:
        logger.debug(
            f"🎉 CHUNKER_SUCCESS [{entity_context}] All {len(test_chunks)} chunks fit "
            f"within OpenAI's {OPENAI_TOKEN_LIMIT} token limit"
        )
        # Return parent with chunks
        return True, [parent] + test_chunks

    return False, []


@transformer(name="Optimized File Chunker")
async def optimized_file_chunker(
    file: FileEntity, logger: ContextualLogger
) -> list[ParentEntity | ChunkEntity]:
    """Optimized file chunker that ensures chunks fit within OpenAI's token limit.

    This transformer:
    1. Converts files to text
    2. Chunks text with an initial size
    3. Creates entities and checks their ACTUAL serialized size
    4. Re-chunks if any entity exceeds OpenAI's limit
    5. Returns parent and chunk entities that are guaranteed to fit

    Args:
        file: The FileEntity to process
        logger: The contextual logger for logging

    Returns:
        list[ParentEntity | ChunkEntity]: The processed chunks
    """
    entity_context = f"Entity({file.entity_id})"

    logger.debug(
        f"📄 CHUNKER_START [{entity_context}] Starting optimized file chunking for: {file.name} "
        f"(type: {type(file).__name__})"
    )

    file_class = type(file)
    FileParentClass, FileChunkClass = file_class.create_parent_chunk_models()

    try:
        # Process file content
        logger.debug(f"🔍 CHUNKER_PROCESS [{entity_context}] Processing file content")
        start_time = asyncio.get_event_loop().time()

        text_content = await _process_file_content(file, entity_context, logger)
        process_elapsed = asyncio.get_event_loop().time() - start_time

        if not text_content or not text_content.strip():
            logger.warning(f"📭 CHUNKER_EMPTY [{entity_context}] No text content found")
            return []

        content_length = len(text_content)
        logger.debug(
            f"📊 CHUNKER_CONTENT [{entity_context}] Processed {content_length} characters "
            f"in {process_elapsed:.2f}s"
        )

        # Try different chunk sizes until we find one that works
        chunk_size = INITIAL_CHUNK_SIZE
        produced_entities = []

        while chunk_size >= MIN_CHUNK_SIZE:
            success, entities = await _try_chunk_size(
                file,
                text_content,
                chunk_size,
                entity_context,
                logger,
                FileParentClass,
                FileChunkClass,
            )

            if success:
                produced_entities = entities
                break

            # Need smaller chunks
            chunk_size = int(chunk_size * 0.7)  # Reduce by 30%
            logger.debug(
                f"🔄 CHUNKER_RETRY [{entity_context}] "
                f"Retrying with smaller chunk size: {chunk_size}"
            )

        if not produced_entities:
            logger.error(
                f"💥 CHUNKER_FAILED [{entity_context}] Could not create chunks small enough to fit "
                f"within OpenAI's limit even at minimum size {MIN_CHUNK_SIZE}"
            )
            return []

        total_elapsed = asyncio.get_event_loop().time() - start_time
        chunks_created = len(produced_entities) - 1  # Subtract parent
        logger.debug(
            f"✅ CHUNKER_COMPLETE [{entity_context}] Chunking completed in {total_elapsed:.2f}s "
            f"(1 parent + {chunks_created} chunks)"
        )

        # Mark entity as fully processed in storage
        if file.sync_id:
            from airweave.platform.storage import storage_manager

            if not storage_manager._is_ctti_entity(file):
                await storage_manager.mark_entity_processed(
                    logger, file.sync_id, file.entity_id, chunks_created
                )
                logger.debug(
                    f"📝 CHUNKER_MARKED_PROCESSED [{entity_context}] "
                    f"Marked entity as fully processed with {chunks_created} chunks"
                )

        return produced_entities

    except Exception as e:
        logger.error(
            f"💥 CHUNKER_ERROR [{entity_context}] Chunking failed: {type(e).__name__}: {str(e)}"
        )
        raise e
    finally:
        # Clean up temporary file if it exists
        if hasattr(file, "local_path") and file.local_path:
            from airweave.platform.storage import storage_manager

            await storage_manager.cleanup_temp_file(logger, file.local_path)
            logger.debug(
                f"🧹 CHUNKER_CLEANUP [{entity_context}] Cleaned up temp file: {file.local_path}"
            )


# Export for use in default_file_chunker
async def _chunk_text_optimized(
    text_content: str, entity_context: str, logger: ContextualLogger
) -> List[str]:
    """Optimized chunking method for use by default_file_chunker."""
    return await _chunk_text_adaptive(text_content, entity_context, logger)
